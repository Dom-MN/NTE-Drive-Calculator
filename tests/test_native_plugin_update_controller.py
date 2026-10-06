# 验证更新结果先登记再重连，账号切换与登记失败不会恢复错误会话。
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QWidget, QMessageBox

from auto_sync_ui_fixture import application, dispose
from src.features.settings.native_plugin_update_controller import NativePluginUpdateController
from src.services.native_plugin_update import NativePluginUpdateResult


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    application()
    parent = QWidget()
    events = []
    policy = Mock()
    policy.deployment_record = {'workspace_path': str(tmp_path), 'loading_method': 'native-capture'}
    policy.update_deployment.side_effect = lambda _: events.append('save')
    maintenance = Mock(uncertain=False)
    maintenance.finish.side_effect = lambda **kw: events.append(('finish', kw['restore']))
    generation = [1]
    controller = NativePluginUpdateController(context=Mock(), policy=policy, session=Mock(),
        loader=Mock(), generation=lambda: generation[0], maintenance=maintenance, parent=parent)
    controller._target_directory = tmp_path
    controller._request_generation = 1
    monkeypatch.setattr(QMessageBox, 'warning', Mock())
    monkeypatch.setattr(QMessageBox, 'information', Mock())
    yield SimpleNamespace(controller=controller, policy=policy, maintenance=maintenance,
                          generation=generation, events=events)
    dispose(parent)


def test_records_verified_images_before_resuming(scenario):
    s = scenario
    result = NativePluginUpdateResult('updated', 'done', {'plugins/NTE_PluginCombat.dll': 'hash'})
    s.controller._result(result)
    assert s.events == ['save', ('finish', True)]
    s.controller._result(result)
    assert s.events == ['save', ('finish', True)]


def test_completed_deployment_is_recorded_even_if_account_changed(scenario):
    s = scenario
    s.generation[0] = 2
    s.controller._result(NativePluginUpdateResult('updated', 'done', {'plugin': 'hash'}))
    assert s.events == ['save', ('finish', False)]
    QMessageBox.information.assert_not_called()


def test_record_failure_keeps_maintenance_hold(scenario):
    s = scenario
    s.policy.update_deployment.side_effect = OSError('fixture')
    s.controller._result(NativePluginUpdateResult('updated', 'done', {'plugin': 'hash'}))
    assert s.maintenance.uncertain
    QMessageBox.warning.assert_called_once()
    QMessageBox.information.assert_not_called()


def test_loader_update_records_native_workspace_identity(scenario, tmp_path):
    s = scenario
    s.policy.deployment_record = {'loading_method': 'loader', 'native_workspace_root': str(tmp_path),
                                  'workspace_path': str(tmp_path / 'legacy')}
    s.controller._result(NativePluginUpdateResult('updated', 'done', {'plugin': 'hash'}))
    record = s.policy.update_deployment.call_args.args[0]
    assert record['native_workspace_files'] == {'plugin': 'hash'}
    assert not s.maintenance.uncertain


def test_retargeted_directory_does_not_receive_previous_game_hashes(scenario, tmp_path):
    s = scenario
    s.policy.deployment_record = {'workspace_path': str(tmp_path / 'other')}
    s.controller._result(NativePluginUpdateResult('updated', 'done', {'plugin': 'hash'}))
    s.policy.update_deployment.assert_not_called()
    assert s.maintenance.uncertain


def test_missing_game_explains_deployment_without_claiming_migration(scenario, monkeypatch):
    from src.features.settings import native_plugin_update_controller as module
    monkeypatch.setattr(module, 'native_game_pid', lambda: None)
    scenario.controller.request()
    detail = QMessageBox.warning.call_args.args[2]
    assert '游戏尚未启动' in detail
    assert '部署原生组件' in detail
    assert '首次迁移' not in detail
    scenario.maintenance.begin.assert_not_called()


def test_game_target_does_not_require_capture_pipe(monkeypatch):
    from src.integrations import native_capture_process as module
    monkeypatch.setattr(module, '_native_game_identity', lambda: (123, 456))
    monkeypatch.setattr(module, 'native_capture_game_pid', Mock(side_effect=AssertionError('capture pipe not required')))
    assert module.native_game_pid() == 123


def test_game_identity_error_is_not_reported_as_missing_game(scenario, monkeypatch):
    from src.features.settings import native_plugin_update_controller as module
    monkeypatch.setattr(module, 'native_game_pid', Mock(side_effect=RuntimeError('无法核对游戏进程身份')))
    scenario.controller.request()
    detail = QMessageBox.warning.call_args.args[2]
    assert '无法核对游戏进程身份' in detail
    assert '游戏尚未启动' not in detail
