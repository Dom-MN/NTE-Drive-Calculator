# 验证同步取消保留停止阶段与固定原因，不把载荷或旧背包当成新数据。
from unittest.mock import patch

from src.services.inventory_capture_wait import InventorySyncCancelled
from src.services.inventory_sync_service import InventorySyncService
from tests.test_inventory_sync_service import FakeCoreClient


def test_native_session_cancellation_logs_owner_reason_without_payload(tmp_path):
    client = FakeCoreClient()
    client.start_capture = lambda **_kw: (_ for _ in ()).throw(InventorySyncCancelled('private-payload'))
    service = InventorySyncService(
        tmp_path / 'user.sqlite3', client_factory=lambda: client,
        capture_source='native', operation_guard=lambda _cap: None, account_id='tester', account_name='fixture',
    )
    with patch('src.services.inventory_sync_runtime.log_event') as events:
        service._run()
    stopped = [call for call in events.call_args_list if call.args[1] == 'inventory_sync.stopped']
    assert len(stopped) == 1
    assert stopped[0].kwargs['stop_reason'] == 'native_session_cancelled'
    assert stopped[0].kwargs['stop_stage'] == 'starting_capture'
    assert 'private-payload' not in str(events.call_args_list)
    assert service.state.phase == 'stopped'
    assert client.closed


def test_explicit_connection_loss_is_exposed_for_bounded_recovery(tmp_path):
    client = FakeCoreClient()
    client.start_capture = lambda **_kw: (_ for _ in ()).throw(
        InventorySyncCancelled('do-not-log', reason='connection_lost'))
    service = InventorySyncService(
        tmp_path / 'user.sqlite3', client_factory=lambda: client, capture_source='native',
        operation_guard=lambda _cap: None, account_id='tester', account_name='fixture',
    )
    with patch('src.services.inventory_sync_runtime.log_event') as events:
        service._run()
    assert service.state.stop_reason == 'connection_lost'
    assert service.state.phase == 'stopped'
    assert 'do-not-log' not in str(events.call_args_list)
