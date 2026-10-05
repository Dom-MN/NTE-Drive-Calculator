# 验证计算目录后台校验、有界请求、失败门禁和过期回调隔离。
from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from src.ui.controllers.allocation_catalog_controller import allocation_catalog_controller


def wait(predicate):
    until = time.monotonic() + 5
    while not predicate() and time.monotonic() < until:
        QTest.qWait(5)
    assert predicate()


@pytest.fixture
def page(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.app_context = SimpleNamespace(generation=1, account=SimpleNamespace(active_account_id="fixture", user_database_path=tmp_path / "user.sqlite3"),
        paths=SimpleNamespace(config_dir=tmp_path, equipment_allocation_database_path=tmp_path / "static.sqlite3", equipment_allocation_asset_root=tmp_path))
    window.btn_run = QPushButton(window)
    window.selector = QWidget(window)
    running = [False]
    window.scanning_controller = SimpleNamespace(is_running=lambda: running[0], role_selector=window.selector)
    window._read_allocation_catalog = lambda *_args: None
    applied = []
    def apply(loaded, *, reload_priority, source_key):
        applied.append((loaded, reload_priority, source_key))
        window._allocation_catalog_loaded_key = source_key
    window._apply_allocation_catalog = apply
    window._apply_inventory_status = lambda _summary: None
    controller = allocation_catalog_controller(window)
    monkeypatch.setattr(controller.service, "inventory_summary", lambda: None)
    yield window, controller, applied, running
    controller.close()
    wait(lambda: not controller.lane.is_running())
    window.close()
    window.deleteLater()
    app.processEvents()


def test_read_is_background_and_calculation_waits_for_current_catalog(page, monkeypatch):
    window, owner, applied, _running = page
    release, entered, threads, started = threading.Event(), threading.Event(), [], []
    def read(**_args):
        threads.append(threading.get_ident())
        entered.set()
        release.wait(2)
        return "loaded", "semantic", True
    monkeypatch.setattr(owner.service, "read", read)
    owner.refresh(continuation=lambda: started.append("started"), verify=True)
    wait(entered.is_set)
    assert not window.btn_run.isEnabled() and not window.selector.isEnabled()
    assert not applied and not started
    release.set()
    wait(lambda: bool(started))
    assert threads == [threads[0]] and threads[0] != threading.get_ident()
    assert applied == [("loaded", False, "semantic")] and window.btn_run.isEnabled()


def test_cancelled_result_cached_by_service_still_applies_to_current_request(page, monkeypatch):
    window, owner, applied, _running = page
    release, entered, calls = threading.Event(), threading.Event(), []
    def read(**_args):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            release.wait(2)
        return "latest", "changed", len(calls) == 1
    monkeypatch.setattr(owner.service, "read", read)
    window._allocation_catalog_loaded_key = "old"
    owner.refresh()
    wait(entered.is_set)
    owner.invalidate()
    owner.refresh()
    release.set()
    wait(lambda: not owner.lane.is_running())
    assert len(calls) == 2 and applied == [("latest", False, "changed")]


def test_same_revision_validation_does_not_reapply_cards(page, monkeypatch):
    window, owner, applied, _running = page
    window._allocation_catalog_loaded_key = "semantic"
    monkeypatch.setattr(owner.service, "read", lambda **_kwargs: ("same", "semantic", False))
    owner.refresh()
    wait(lambda: not owner.lane.is_running())
    assert applied == [] and window.selector.isEnabled()


def test_failure_keeps_old_catalog_and_does_not_start_calculation(page, monkeypatch):
    window, owner, applied, _running = page
    window._allocation_catalog_loaded_key = "old"
    started = []
    def read(**_kwargs):
        raise RuntimeError("fixture failed")
    monkeypatch.setattr(owner.service, "read", read)
    owner.refresh(continuation=lambda: started.append(1), verify=True)
    wait(lambda: not owner.lane.is_running())
    assert applied == [] and not started and not window.btn_run.isEnabled()
    assert window._allocation_catalog_loaded_key == "old"


def test_account_change_and_close_discard_old_results(page, monkeypatch):
    window, owner, applied, _running = page
    release, entered = threading.Event(), threading.Event()
    def read(**_kwargs):
        entered.set()
        release.wait(2)
        return "obsolete", "obsolete", True
    monkeypatch.setattr(owner.service, "read", read)
    owner.refresh()
    wait(entered.is_set)
    window.app_context.generation += 1
    release.set()
    wait(lambda: not owner.lane.is_running())
    assert not applied


def test_running_calculation_keeps_its_frozen_catalog(page, monkeypatch):
    _window, owner, applied, running = page
    running[0] = True
    monkeypatch.setattr(owner.service, "read", lambda **_kwargs: pytest.fail("running request must not reload"))
    owner.refresh()
    assert not applied and not owner.lane.is_running()


def test_leaving_page_while_validation_pending_does_not_start_hidden_task(page, monkeypatch):
    window, owner, _applied, _running = page
    window.stack = SimpleNamespace(currentIndex=lambda: 1)
    window._nav_key_for_index = lambda _index: "home"
    started = []
    monkeypatch.setattr(owner.service, "read", lambda **_kwargs: ("same", "same", True))
    owner.refresh(continuation=lambda: started.append(1), verify=True)
    wait(lambda: not owner.lane.is_running())
    assert not started
