# 验证计算页重复进入复用数据，来源变更与账号切换仍触发刷新。
from __future__ import annotations

from types import SimpleNamespace

from src.ui.main_window_data_mixin import MainWindowDataMixin


class _NavigationHarness(MainWindowDataMixin):
    def __init__(self, root):
        paths = SimpleNamespace(
            config_dir=root,
            workshop_weight_template_file=root / 'workshop_weight_template.json',
            equipment_allocation_database_path=root / 'static.sqlite3',
        )
        account = SimpleNamespace(user_database_path=root / 'user.sqlite3')
        self.app_context = SimpleNamespace(paths=paths, account=account, generation=1)
        self.loads = []
        self._allocation_catalog_loaded_key = self._allocation_catalog_source_key()

    def _load_data(self, reload_priority=True):
        self.loads.append(reload_priority)
        self._allocation_catalog_loaded_key = self._allocation_catalog_source_key()


def test_reenter_calculation_skips_unchanged_catalog_but_reloads_changed_sources(tmp_path):
    window = _NavigationHarness(tmp_path)
    window._refresh_execute()
    assert window.loads == []

    (tmp_path / 'user.sqlite3-wal').write_bytes(b'new account data')
    window._refresh_execute()
    assert window.loads == [False]
    window._refresh_execute()
    assert window.loads == [False]

    window.app_context.generation += 1
    window._refresh_execute()
    assert window.loads == [False, False]
