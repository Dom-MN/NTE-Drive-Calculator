# 验证计算页重复进入复用数据，来源变更与账号切换仍触发刷新。
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QPushButton, QWidget

from auto_sync_ui_fixture import application, dispose
from src.ui import main_window_data_mixin as data_module
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


def test_unrelated_account_write_updates_scoring_without_rebuilding_role_cards():
    events = []
    selector = SimpleNamespace(
        load_roles=lambda *_args, **_kwargs: events.append("cards"),
        load_startup_priority_config=lambda: events.append("priority"),
    )
    window = MainWindowDataMixin()
    window.roles_db = {"role": {"character_id": 1}}
    window.sets_db = {"set": {}}
    window.tape_main_stats = ["attack"]
    window.drive_sub_stats = ["crit"]
    window.weapons_db = {}
    window._allocation_icon_paths = {}
    window.stats_config = {}
    window._shape_areas = {}
    window.scanning_controller = SimpleNamespace(role_selector=selector)
    window.equipment_presentation = SimpleNamespace(
        update_catalog=lambda **_kwargs: events.append("equipment")
    )
    window.identification_controller = SimpleNamespace(
        update_catalog=lambda **_kwargs: events.append("identify")
    )
    window._update_inventory_status = lambda: events.append("inventory")
    scoring = object()
    loaded = ({}, ["attack"], ["crit"], {}, window.roles_db,
              window.sets_db, {}, scoring, {})

    window._apply_allocation_catalog(loaded, reload_priority=False, source_key="new")

    assert "cards" not in events
    assert events == ["inventory"]
    assert window.scoring_engine is scoring
    assert window._allocation_catalog_loaded_key == "new"

    revised_roles = {"role": {"character_id": 1, "weight": 2}}
    window._apply_allocation_catalog(
        ({}, ["attack"], ["crit"], {}, revised_roles,
         window.sets_db, {}, object(), {}),
        reload_priority=False, source_key="changed",
    )
    assert events[-3:] == ["cards", "equipment", "identify"]
    assert window.roles_db == revised_roles


def test_late_catalog_read_is_discarded_after_source_changes(monkeypatch, tmp_path):
    application()
    workers = []

    class Signal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

        def emit(self, value):
            self.callback(value)

    class Worker:
        def __init__(self, target, parent):
            self.result_ready = Signal()
            self.error = Signal()
            self.finished = Signal()
            workers.append(self)

        def start(self):
            pass

        def deleteLater(self):
            pass

    class Window(QWidget, MainWindowDataMixin):
        def __init__(self):
            super().__init__()
            paths = SimpleNamespace(
                config_dir=tmp_path,
                equipment_allocation_database_path=tmp_path / "static.sqlite3",
                equipment_allocation_asset_root=tmp_path,
            )
            self.app_context = SimpleNamespace(
                paths=paths, account=SimpleNamespace(user_database_path=tmp_path / "user.sqlite3"),
            )
            self.source_key = "first"
            self._allocation_catalog_loaded_key = "old"
            self.btn_run = QPushButton()
            self.scanning_controller = SimpleNamespace(
                is_running=lambda: False, role_selector=Mock(),
            )
            self.applied = []

        def _allocation_catalog_source_key(self):
            return self.source_key

        def _apply_allocation_catalog(self, loaded, *, reload_priority, source_key):
            self.applied.append((loaded, source_key))

    monkeypatch.setattr(data_module, "WorkerThread", Worker)
    window = Window()
    try:
        window._refresh_execute()
        assert not window.btn_run.isEnabled()
        window.scanning_controller.role_selector.setEnabled.assert_called_with(False)
        window.source_key = "second"
        workers[0].result_ready.emit("obsolete")
        assert window.applied == []
        assert len(workers) == 2
        workers[1].result_ready.emit("current")
        assert window.applied == [("current", "second")]
    finally:
        dispose(window)
