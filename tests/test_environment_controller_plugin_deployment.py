# 验证部署装备插件前的游戏进程提示和精简确认文案。
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox

from src.ui.controllers.environment_controller import _deploy_equipment_plugin


def _window():
    return SimpleNamespace(
        _equipment_plugin_consent=SimpleNamespace(isChecked=lambda: True),
        _equipment_plugin_game_executable_edit=SimpleNamespace(
            text=lambda: "C:/game/HTGame.exe",
        ),
        _mod_plugin_loading_service=SimpleNamespace(
            ensure_proxy_deployment_allowed=MagicMock(),
        ),
        app_context=SimpleNamespace(paths=SimpleNamespace(root=Path("."))),
    )


@patch("src.ui.controllers.environment_controller.QMessageBox.warning")
@patch("src.ui.controllers.environment_controller.game_process_running", return_value=True)
def test_deploy_stops_with_clear_message_while_game_is_running(game_running, warning):
    window = _window()

    _deploy_equipment_plugin(window)

    game_running.assert_called_once_with()
    warning.assert_called_once_with(
        window,
        "部署装备插件",
        "检测到游戏正在运行。\n请完全退出游戏后再部署插件。",
    )
    window._mod_plugin_loading_service.ensure_proxy_deployment_allowed.assert_not_called()


@patch("src.ui.controllers.environment_controller.QMessageBox.question")
@patch("src.ui.controllers.environment_controller.packaged_plugin_dll", return_value=Path("plugin.dll"))
@patch("src.ui.controllers.environment_controller.game_process_running", return_value=False)
def test_deploy_confirmation_keeps_only_action_and_backup_information(
    _game_running,
    _plugin,
    question,
):
    question.return_value = QMessageBox.No
    window = _window()

    _deploy_equipment_plugin(window)

    assert question.call_args.args[2] == (
        "将部署装备插件到所选游戏目录。\n"
        "已有同名文件会自动备份。\n\n"
        "是否继续？"
    )
