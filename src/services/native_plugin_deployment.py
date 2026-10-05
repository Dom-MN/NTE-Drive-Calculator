# 按正式布局直接替换原生采集组件，不保留旧文件备份，按固定文件名清理。
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Callable

from src.integrations.native_plugin_bundle import (
    NATIVE_PLUGIN_DEPLOYMENT_PATHS, HOT_PLUGIN_DEPLOYMENT_PATHS, PERFORMANCE_DEPLOYMENT_PATHS, HUD_DEPLOYMENT_PATHS, inspect_native_plugin_bundle,
)
from src.integrations.operation_guard import require_operation
from src.integrations.legacy_game_proxy import remove_legacy_game_proxy
from src.services.equipment_plugin_deployment import (
    EquipmentPluginDeploymentError,
    GAME_EXECUTABLE_NAME, game_executable, game_process_running,
)


@dataclass(frozen=True)
class NativePluginDeployment:
    game_executable: Path
    target_path: Path
    deployed_sha256: str
    workspace_path: Path
    backup_path: Path | None
    managed_files: dict[str, str]
    loading_method: str = 'native-capture'
    deployment_layout: str = 'native-capture-v1'


class PluginDeploymentPendingCleanup(EquipmentPluginDeploymentError):
    """Persist partially deployed native files for cleanup after the game exits."""
    def __init__(self, message: str, *, deployment: NativePluginDeployment):
        super().__init__(message)
        self.deployment = deployment


@dataclass(frozen=True)
class NativePluginCleanupResult:
    status: str
    detail: str


@dataclass(frozen=True)
class NativeComponentFilesDeployment:
    directory: Path
    backup_path: Path | None
    managed_files: dict[str, str]


class NativeComponentFilesPendingCleanup(EquipmentPluginDeploymentError):
    def __init__(self, message: str, *, deployment: NativeComponentFilesDeployment):
        super().__init__(message)
        self.deployment = deployment


def _digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _target(directory: Path, relative: str) -> Path:
    if relative not in {*NATIVE_PLUGIN_DEPLOYMENT_PATHS.values(), *HOT_PLUGIN_DEPLOYMENT_PATHS.values(), *PERFORMANCE_DEPLOYMENT_PATHS.values(), *HUD_DEPLOYMENT_PATHS.values()}:
        raise EquipmentPluginDeploymentError('组件记录包含正式布局之外的文件。')
    target = directory / relative
    if target.is_symlink() or not target.resolve().is_relative_to(directory):
        raise EquipmentPluginDeploymentError('组件目标不是可管理的游戏目录普通文件。')
    if target.exists() and not target.is_file():
        raise EquipmentPluginDeploymentError('组件目标位置不是普通文件。')
    return target


def _manual_cleanup_target(directory: Path, relative: str) -> Path:
    target = _target(directory, relative)
    try:
        info = target.lstat()
    except FileNotFoundError:
        return target
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise EquipmentPluginDeploymentError('组件目标不是可管理的游戏目录普通文件。')
    return target


def _replace_file(source: Path, target: Path, digest: str, require_idle, *, suffix: str, expected_target: str | None) -> None:
    require_idle()
    descriptor, temporary_name = tempfile.mkstemp(prefix='.nte-deploy-', suffix=suffix, dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    failure = None
    try:
        shutil.copy2(source, temporary)
        if _digest(temporary) != digest:
            raise EquipmentPluginDeploymentError('组件临时文件校验失败，未替换目标文件。')
        require_idle()
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise EquipmentPluginDeploymentError('组件目标在暂存期间改变类型，未覆盖现场文件。')
        current = _digest(target) if target.exists() else None
        if current != expected_target:
            raise EquipmentPluginDeploymentError('组件目标在暂存期间发生变化，未覆盖现场文件。')
        os.replace(temporary, target)
    except Exception as error:
        failure = error
        if isinstance(error, OSError) and getattr(error, 'winerror', None) in {225, 226}:
            raise EquipmentPluginDeploymentError(
                f'Windows 安全防护阻止部署 {target.name}，请查看系统保护历史并核查组件来源。'
            ) from error
        if isinstance(error, FileNotFoundError):
            raise EquipmentPluginDeploymentError(
                f'部署 {target.name} 时文件消失，写入结果无法核验；请检查系统保护历史和文件占用情况。'
            ) from error
        raise
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            if failure is None:
                raise  # Keep an earlier deployment failure when cleanup is also blocked.

def deploy_native_component_files(
    *, application_root: str | Path, directory_path: str | Path,
    operation_guard: Callable[[str], None] | None,
    game_running: Callable[[], bool | None] | None = None,
    component_roles: tuple[str, ...] | None = None,
    expected_existing_files: Mapping[str, str | None] | None = None,
    cleanup_legacy_proxy: bool = False,
) -> NativeComponentFilesDeployment:
    probe = game_running or game_process_running

    def require_idle() -> None:
        require_operation(operation_guard, 'native_load')
        if probe():
            raise EquipmentPluginDeploymentError('游戏正在运行，整套组件部署需等待游戏完全退出。')

    require_idle()
    root = Path(application_root).expanduser().resolve()
    bundle = inspect_native_plugin_bundle(root)
    if not bundle.ready:
        raise EquipmentPluginDeploymentError('；'.join(bundle.issues))
    directory = Path(directory_path).expanduser().resolve()
    paths = bundle.deployment_paths
    component_roles = tuple(paths) if component_roles is None else component_roles
    if (not component_roles or len(set(component_roles)) != len(component_roles)
            or any(role not in paths for role in component_roles)):
        raise EquipmentPluginDeploymentError('部署请求包含无效的采集组件角色。')
    order = tuple(role for role in paths if role != 'host' and role in component_roles)
    if 'host' in component_roles:
        order += ('host',)
    sources, targets, expected = {}, {}, {}
    for role in order:
        relative = paths[role]
        source = root / bundle.roles[role]
        target = _target(directory, relative)
        if source.resolve() == target.resolve():
            raise EquipmentPluginDeploymentError('随附组件与游戏部署位置相同，无法建立部署事务。')
        sources[relative], targets[relative] = source, target
        expected[relative] = bundle.files[bundle.roles[role]]
    if expected_existing_files is not None:
        if set(expected_existing_files) != set(targets):
            raise EquipmentPluginDeploymentError('自动部署缺少完整的目标文件核对记录。')
        for relative, target in targets.items():
            previous = _digest(target) if target.exists() else None
            if previous != expected_existing_files[relative]:
                raise EquipmentPluginDeploymentError('组件目标在自动检测后发生变化，未覆盖现场文件。')
    require_idle()
    originals: dict[str, str | None] = {}
    written: dict[str, str] = {}

    def result() -> NativeComponentFilesDeployment:
        return NativeComponentFilesDeployment(directory, None, dict(written))

    try:
        for relative, source in sources.items():
            require_idle()
            if _digest(source) != expected[relative]:
                raise EquipmentPluginDeploymentError('随附组件在部署前发生变化，已停止部署。')
            target = targets[relative]
            previous = _digest(target) if target.exists() else None
            if expected_existing_files is not None and previous != expected_existing_files[relative]:
                raise EquipmentPluginDeploymentError('组件目标在自动检测后发生变化，未覆盖现场文件。')
            originals[relative] = previous
        if cleanup_legacy_proxy and 'host' in order:
            remove_legacy_game_proxy(game_directory=directory, require_idle=require_idle)
        for relative, target in targets.items():
            require_idle()
            target = _target(directory, relative)
            previous = originals[relative]
            if (_digest(target) if target.exists() else None) != previous:
                raise EquipmentPluginDeploymentError('游戏目录组件在部署前发生变化，已停止部署。')
            target.parent.mkdir(parents=True, exist_ok=True)
            _replace_file(sources[relative], target, expected[relative], require_idle, suffix='.new', expected_target=previous)
            written[relative] = expected[relative]
            if _digest(target) != expected[relative]:
                raise EquipmentPluginDeploymentError('组件写入后校验失败。')
        require_idle()
        return result()
    except Exception as error:
        if written:
            try:
                require_idle()
                for relative in reversed(tuple(written)):
                    require_idle()
                    target = _target(directory, relative)
                    if not target.is_file() or _digest(target) != written[relative]:
                        raise EquipmentPluginDeploymentError('本次写入的组件已经变化，未覆盖现场文件。')
                    require_idle()
                    target.unlink()
                    written.pop(relative)
            except Exception as rollback_error:
                raise NativeComponentFilesPendingCleanup(
                    '组件部署未完成；已保留本次实际写入记录，等待游戏退出后清理。',
                    deployment=result(),
                ) from rollback_error
        if isinstance(error, (EquipmentPluginDeploymentError, PermissionError)):
            raise
        raise EquipmentPluginDeploymentError('原生组件部署失败，本次已写入的新组件已移除；未恢复旧组件，请重新部署。') from error


def deploy_native_plugin(
    *, application_root: str | Path, game_executable_path: str | Path,
    operation_guard: Callable[[str], None] | None,
    game_running: Callable[[], bool | None] | None = None,
    expected_existing_files: Mapping[str, str | None] | None = None,
    cleanup_legacy_proxy: bool = False,
) -> NativePluginDeployment:
    require_operation(operation_guard, 'native_load')
    executable = game_executable(game_executable_path)
    bundle = inspect_native_plugin_bundle(application_root)

    def wrap(record: NativeComponentFilesDeployment) -> NativePluginDeployment:
        return NativePluginDeployment(
            executable, record.directory / NATIVE_PLUGIN_DEPLOYMENT_PATHS['host'],
            record.managed_files.get(NATIVE_PLUGIN_DEPLOYMENT_PATHS['host'], ''),
            record.directory, record.backup_path, dict(record.managed_files), deployment_layout=bundle.layout,
        )

    try:
        return wrap(deploy_native_component_files(
            application_root=application_root, directory_path=executable.parent,
            operation_guard=operation_guard,
            game_running=game_running,
            expected_existing_files=expected_existing_files,
            cleanup_legacy_proxy=cleanup_legacy_proxy,
        ))
    except NativeComponentFilesPendingCleanup as error:
        raise PluginDeploymentPendingCleanup(str(error), deployment=wrap(error.deployment)) from error


def cleanup_native_component_files(
    *, directory_path: str | Path, managed_files: dict[str, str],
    game_running: Callable[[], bool | None] | None = None,
) -> NativePluginCleanupResult:
    probe = game_running or game_process_running
    if probe():
        return NativePluginCleanupResult('waiting_game_exit', '游戏未关闭，暂时不能清理组件。请完全退出游戏后重新检测。')
    directory = Path(directory_path).expanduser()
    if not directory.is_absolute():
        raise EquipmentPluginDeploymentError('组件清理目录必须是已记录的绝对路径。')
    directory = directory.resolve()
    files = dict(managed_files)
    try:
        # Upgrades may replace a managed DLL without updating an older ownership record.
        # Validate the fixed filenames and paths, not the historical contents.
        for relative in files:
            _target(directory, relative)
        # Remove the automatic loading entry first; never restore transaction backups.
        ordered = sorted(files, key=lambda relative: relative != NATIVE_PLUGIN_DEPLOYMENT_PATHS['host'])
        for relative in ordered:
            if probe():
                return NativePluginCleanupResult('waiting_game_exit', '游戏在清理过程中启动，剩余组件尚未清理。请完全退出游戏后重新检测。')
            target = _target(directory, relative)
            if target.exists():
                target.unlink()
    except EquipmentPluginDeploymentError as error:
        return NativePluginCleanupResult('conflict', str(error))
    except OSError as error:
        raise EquipmentPluginDeploymentError('无法清理已记录组件，请保持游戏关闭并重试。') from error
    if probe():
        return NativePluginCleanupResult('waiting_game_exit', '组件文件已清理，游戏仍需退出以结束已加载会话。')
    return NativePluginCleanupResult('cleaned', '已按固定文件名清理本程序记录的原生组件。')


def cleanup_native_plugin(
    *, game_executable_path: str | Path, managed_files: dict[str, str],
    game_running: Callable[[], bool | None] | None = None,
) -> NativePluginCleanupResult:
    executable = Path(str(game_executable_path).strip().strip('"')).expanduser()
    if not executable.is_absolute() or executable.name.casefold() != GAME_EXECUTABLE_NAME.casefold():
        raise EquipmentPluginDeploymentError('清理记录中的游戏主程序路径无效。')
    return cleanup_native_component_files(directory_path=executable.parent,
                                          managed_files=managed_files, game_running=game_running)


def cleanup_manual_native_plugin(
    *, application_root: str | Path, game_executable_path: str | Path,
    managed_files: dict[str, str], game_running: Callable[[], bool | None] | None = None,
) -> NativePluginCleanupResult:
    """Explicit cleanup removes fixed component filenames in the selected directory."""
    probe = game_running or game_process_running
    if probe():
        return NativePluginCleanupResult('waiting_game_exit', '游戏未关闭，暂时不能清理组件。请完全退出游戏后重新检测。')
    executable = Path(str(game_executable_path).strip().strip('"')).expanduser()
    if not executable.is_absolute() or executable.name.casefold() != GAME_EXECUTABLE_NAME.casefold():
        raise EquipmentPluginDeploymentError('清理记录中的游戏主程序路径无效。')
    directory = executable.parent.resolve()
    recorded = dict(managed_files)
    observed: dict[str, str] = {}
    try:
        for relative in recorded:
            _manual_cleanup_target(directory, relative)
        for relative in {*NATIVE_PLUGIN_DEPLOYMENT_PATHS.values(), *HOT_PLUGIN_DEPLOYMENT_PATHS.values(), *PERFORMANCE_DEPLOYMENT_PATHS.values(), *HUD_DEPLOYMENT_PATHS.values()}:
            target = _manual_cleanup_target(directory, relative)
            if not target.exists():
                continue
            # The explicit cleanup action authorizes these exact names, including
            # unrecorded older versions. Hash only detects changes during this action.
            observed[relative] = _digest(target)
        ordered = sorted(observed, key=lambda relative: relative != NATIVE_PLUGIN_DEPLOYMENT_PATHS['host'])
        for relative in ordered:
            if probe():
                return NativePluginCleanupResult('waiting_game_exit', '游戏在清理过程中启动，剩余组件尚未清理。请完全退出游戏后重新检测。')
            target = _manual_cleanup_target(directory, relative)
            if not target.exists():
                continue
            if _digest(target) != observed[relative]:
                return NativePluginCleanupResult('conflict', f'{relative} 在核对后发生变化，已保留剩余组件。')
            target.unlink()
    except EquipmentPluginDeploymentError as error:
        return NativePluginCleanupResult('conflict', str(error))
    except OSError as error:
        raise EquipmentPluginDeploymentError('无法清理游戏目录原生组件，请保持游戏关闭并重试。') from error
    if probe():
        return NativePluginCleanupResult('waiting_game_exit', '组件文件已清理，游戏仍需退出以结束已加载会话。')
    return NativePluginCleanupResult('cleaned', '已按固定文件名清理游戏目录原生组件。')
