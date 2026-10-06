# 将检测异常转换为可复制的业务诊断，并在本地故障日志保留组件实际路径。
from __future__ import annotations

from src.i18n import tr

from concurrent.futures import CancelledError
import math
from pathlib import Path

from src.domain.work_mode import CheckState

from src.integrations.nte_core_protocol import (
    NATIVE_CAPTURE_TRANSIENT_REASONS, NteCoreError, NteCoreNotFoundError, NteCoreProcessError,
    NteCoreProtocolError, NteCoreRpcError, NteCoreTimeoutError,
    native_capture_readiness_message,
)


_START_FAILURES = {
    'peer_identity_mismatch': (
        'Core 与游戏的 Windows 登录身份或权限不一致，请以与游戏相同的用户和权限启动 Calc。',
        '确认 Calc 与游戏使用同一 Windows 用户、相同权限级别后，再重新检测。',
    ),
    'native_resources_unavailable': (
        '采集 Core 缺少必需的内置资源，请更新完整的采集组件。',
        '核对当前安装包是否完整，并使用同一发布包中的 Core 与采集 DLL。',
    ),
    'native_context_capability_required_restart_game': (
        '游戏内的采集 DLL 版本过旧，请更新采集组件并重启游戏。',
        '先核对配套组件版本；完全退出游戏后部署，再启动游戏。重复部署同一旧包不会更新版本。',
    ),
}
_METHODS = frozenset({
    'core.hello', 'core.status', 'equipment.status', 'native.snapshot.status',
    'native.snapshot.refresh', 'native.snapshot.page', 'native.snapshot.changes',
    'native.inventory.page', 'native.character.page',
    'native.diagnostics.configure', 'native.snapshot.open',
})
_BUSINESS_FAILURES = {
    'NATIVE_MAPPING_UNSUPPORTED': '原生数据包含当前 Core 无法转换的角色或装备映射，本次读取已停止，已有数据保持不变。',
    'NATIVE_SNAPSHOT_INCOMPLETE': '本次原生快照未通过完整性校验，不能作为完整背包或角色数据。',
    'NATIVE_CAPABILITY_MISSING': '当前 Core 或 DLL 缺少本次操作所需的原生能力。',
    'NATIVE_SNAPSHOT_UNAVAILABLE': '当前配套组件未提供所请求的原生快照能力。',
    'NATIVE_SNAPSHOT_NOT_FOUND': '请求的原生快照已不可用，需要重新读取。',
    'NATIVE_SNAPSHOT_ARCHIVE_WRITE_FAILED': '原生快照诊断文件写入失败，请检查本地日志目录。',
    'PROTOCOL_VERSION_MISMATCH': 'Calc 与采集 Core 的协议版本不匹配。',
    'HANDSHAKE_REQUIRED': '采集 Core 尚未接受本会话的握手，不能执行本次请求。',
    'REQUEST_IN_PROGRESS': '采集 Core 正在处理另一个请求，本次检测未完成。',
}
_TRANSPORT_FAILURES = {
    'connect_timeout': '连接游戏内采集管道超时；请核对是否有其他工具占用连接。',
    'pipe_open_failed': '无法打开游戏内采集管道；请核对进程权限和连接占用。',
    'pipe_disconnected': '游戏内采集管道已断开，本次检测未完成。',
    'pipe_io_failed': '读写游戏内采集管道失败。',
    'pipe_write_failed': '向游戏内采集管道写入请求失败。',
    'pipe_write_timeout': '向游戏内采集管道写入请求超时。',
    'pipe_server_mismatch': '管道服务端与目标游戏进程不匹配，已拒绝连接。',
    'handshake_rejected': '游戏内采集组件拒绝了握手请求。',
    'unsupported_provider': '游戏内采集组件未通过协议或进程身份校验。',
}
_PROCESS_MESSAGES = frozenset({
    '无法读取游戏进程列表。', '读取游戏进程列表失败。',
    '检测到多个游戏进程，请保留一个后再开始增强采集。',
    '无法核对游戏进程身份，未启动本场采集。',
    '无法核对游戏进程创建时间，未启动本场采集。',
    '无法确定增强采集组件状态，未启动本场采集。',
})
_COPY_HINT = '点击“复制检测结果”发送给维护者；无需仅因这条提示反复重装或重启。'


def detection_failure_state(error: Exception) -> CheckState:
    """Classify typed transient evidence, never infer severity from diagnostic text."""
    if isinstance(error, CancelledError):
        return CheckState.WAITING
    if isinstance(error, NteCoreTimeoutError):
        return CheckState.WARNING
    if isinstance(error, NteCoreRpcError):
        if error.domain_code in _BUSINESS_FAILURES:
            return (CheckState.WARNING if error.domain_code in {
                'REQUEST_IN_PROGRESS', 'NATIVE_SNAPSHOT_NOT_FOUND',
            } else CheckState.FAULT)
        if error.domain_code in {'MODS_PLUGIN_BUSY', 'EQUIPMENT_PLUGIN_BUSY'}:
            return CheckState.WARNING
        if error.code == -32001:
            reason = error.data.get('reason')
            if isinstance(reason, str) and reason in {'sdk_unavailable', 'hook_unavailable'}:
                return CheckState.FAULT
            if isinstance(reason, str) and reason in {
                'world_unavailable', 'controller_unavailable', 'pawn_unavailable',
            }:
                return CheckState.WAITING_LOGIN
            if isinstance(reason, str) and reason in NATIVE_CAPTURE_TRANSIENT_REASONS:
                return CheckState.WAITING
            if error.message in {'not_ready', 'source_changed', 'control_busy', 'control_timeout',
                                 'snapshot_not_found'}:
                return CheckState.WARNING
    return CheckState.FAULT


def _failure_location(error: Exception) -> str:
    """Only expose a repository-relative Python location, never an external path."""
    root = Path(__file__).resolve().parents[2]
    location = ''
    trace = error.__traceback__
    while trace is not None:
        try:
            relative = Path(trace.tb_frame.f_code.co_filename).resolve().relative_to(root)
            if relative.parts[0] == 'src' and relative.suffix == '.py':
                location = f'{relative.as_posix()}:{trace.tb_lineno}'
        except (ValueError, OSError):
            pass
        trace = trace.tb_next
    return location


def detection_failure_detail(error: Exception, *, record: bool = False) -> str:
    """Keep typed evidence and known reasons; never forward raw error text or stderr."""
    evidence = [f'异常类型：{type(error).__name__}']
    context = error.request_context if isinstance(error, NteCoreError) else None
    if context is not None:
        method = context.method if context.method in _METHODS else '未识别接口'
        evidence.append(f'失败接口：{method}')
        digest = context.executable_sha256
        if isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdefABCDEF' for c in digest):
            evidence.append(f'Core SHA-256：{digest}')
        if context.handshake_confirmed:
            evidence.append('本次握手：已确认')
    location = _failure_location(error)
    if location:
        evidence.append(f'代码位置：{location}')
    reason = tr('检测发生未识别异常，尚不能确定是连接、组件还是业务数据问题。')
    next_step = tr(_COPY_HINT)
    cause = error.__cause__ if isinstance(error.__cause__, OSError) else error
    winerror = getattr(cause, 'winerror', None)
    if isinstance(winerror, int):
        evidence.append(f'Windows 错误码：{winerror}')

    if isinstance(error, NteCoreProcessError):
        reason = tr('采集 Core 启动或运行失败，未能完成本次检测。')
        if isinstance(error.return_code, int):
            evidence.append(f'Core 退出码：{error.return_code}')
        if str(error) in _PROCESS_MESSAGES:
            reason = str(error)
        for code, (message, action) in _START_FAILURES.items():
            if str(error) == message or any(
                line.strip() == f'error: native capture {code}' for line in error.stderr_lines
            ):
                reason, next_step = message, action
                evidence.append(f'原因码：{code}')
                break
        else:
            for code, message in _TRANSPORT_FAILURES.items():
                if any(line.strip() == f'error: native capture {code}' for line in error.stderr_lines):
                    reason = message
                    evidence.append(f'原因码：{code}')
                    break
    elif isinstance(error, NteCoreTimeoutError):
        reason = tr('等待采集 Core 响应超时，本次检测未完成；超时本身不能证明组件没有加载。')
        method = error.method if error.method in _METHODS else tr('未识别接口')
        evidence.append(f'超时接口：{method}')
        if isinstance(error.timeout, (int, float)) and math.isfinite(error.timeout):
            evidence.append(f'等待上限：{error.timeout:g} 秒')
        next_step = tr('确认已进入可操作角色的场景，并结束其他工具的采集连接；若仍失败，') + tr(_COPY_HINT)
    elif isinstance(error, NteCoreRpcError):
        reason = tr('采集 Core 返回业务错误，本次检测未完成。')
        evidence.append(f'RPC 错误码：{error.code}')
        known_reason = error.data.get('reason')
        if isinstance(known_reason, str) and known_reason in (
            NATIVE_CAPTURE_TRANSIENT_REASONS | {'sdk_unavailable', 'hook_unavailable', 'provider_stopping'}
        ):
            reason = native_capture_readiness_message(error)
            evidence.append(f'原因码：{known_reason}')
        elif error.domain_code in _BUSINESS_FAILURES:
            reason = _BUSINESS_FAILURES[error.domain_code]
            evidence.append(f'原因码：{error.domain_code}')
            if error.domain_code in {'NATIVE_MAPPING_UNSUPPORTED', 'NATIVE_CAPABILITY_MISSING',
                                     'NATIVE_SNAPSHOT_UNAVAILABLE', 'PROTOCOL_VERSION_MISMATCH'}:
                next_step = '核对 Calc、Core、DLL 与内嵌角色/装备资源是否配套；' + _COPY_HINT
        elif error.domain_code in {'MODS_PLUGIN_BUSY', 'EQUIPMENT_PLUGIN_BUSY'}:
            reason = tr('游戏内组件正在处理其他请求。')
            next_step = tr('结束其他工具的采集或操作任务后重新检测；若仍失败，') + tr(_COPY_HINT)
            evidence.append(f'原因码：{error.domain_code}')
        elif error.code == -32001 and error.message in {'control_timeout', 'not_ready'}:
            # Only exact protocol codes are public; arbitrary provider text stays private.
            reason = {
                'control_timeout': '游戏内采集请求等待执行或完成超时，本次检测未完成。',
                'not_ready': '游戏内采集接口尚未就绪，本次检测未完成。',
            }[error.message]
            evidence.append(f'原因码：{error.message}')
            next_step = '确认已进入可操作角色的场景后重新检测；若持续出现，' + _COPY_HINT
        elif error.code == -32601:
            reason = tr('采集 Core 不支持本次检测接口，需要核对 Calc、Core 与 DLL 是否配套。')
    elif isinstance(error, NteCoreNotFoundError):
        reason = tr('未找到可用的采集 Core 执行文件。')
        next_step = tr('核对 Calc 安装是否完整，以及安全软件是否隔离了 nte-core.exe。')
    elif isinstance(error, NteCoreProtocolError):
        reason = tr('采集响应未通过协议或数据格式校验，不能作为有效业务结果。')
        next_step = tr('核对 Calc、Core、DLL 是否来自同一配套发布包，并确认支持当前游戏版本；') + tr(_COPY_HINT)
    elif isinstance(error, CancelledError):
        reason = tr('检测已取消，本次没有完整结果。')
        next_step = tr('等待当前任务结束后重新检测。')
    elif isinstance(error, PermissionError):
        reason = tr('检测所需授权或访问权限被拒绝。')
        next_step = tr('核对已确认的工作模式、暂停状态及 Calc 与游戏的运行权限。')
    if winerror == 5 or (isinstance(cause, OSError) and cause.errno == 13):
        reason = tr('Windows 拒绝访问检测所需的进程、文件或连接。')
        next_step = tr('核对 Calc 与游戏的 Windows 用户和权限，以及文件访问权限。')

    detail = (
        tr('原因：{reason}\n下一步：{next_step}', reason=reason, next_step=next_step)
        + '\n诊断：' + '；'.join(evidence)
    )
    if record:
        from src.utils.logger import logger
        local_detail = detail.replace('\n', ' | ')
        if context is not None and context.executable_path:
            path = context.executable_path.replace('\r', r'\r').replace('\n', r'\n')
            local_detail += f' | Core 路径：{path}'
        logger.warning('environment.detection_failed | {}', local_detail)
    return detail
