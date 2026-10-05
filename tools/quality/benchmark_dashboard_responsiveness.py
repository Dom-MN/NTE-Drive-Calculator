# 在隔离数据库上对比工作台读取回调、事件循环延迟和重复通知查询数。
"""Dashboard-only benchmark; no live account, native session or full app startup."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace


def summarize(values):
    ordered = sorted(values)
    return {"median_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * .95) - 1], 3),
            "max_ms": round(max(ordered), 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    fixture, source = args.fixture.resolve(), args.source_root.resolve()
    marker = fixture / "ui-benchmark-fixture.json"
    if (args.iterations < 1 or not marker.is_file()
            or not json.loads(marker.read_text(encoding="utf-8")).get("isolated")):
        parser.error("requires a positive iteration count and isolated fixture")
    for name in ("user.sqlite3", "game_static.sqlite3"):
        path = (fixture / name).resolve()
        if path.parent != fixture or not path.is_file():
            parser.error("database must be a physical file inside the isolated fixture")
    sys.path.insert(0, str(source))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["NTE_GAME_STATIC_DB"] = str(fixture / "game_static.sqlite3")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
    from src.features.home.page import refresh_home_page
    from src.services.dashboard_service import DashboardService
    from src.utils.logger import logger

    logger.remove()
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    for name in ("home_account_label", "home_character_sync_detail", "home_last_sync_label"):
        setattr(window, name, QLabel(window))
    window.home_metric_labels = {key: (QLabel(window), QLabel(window)) for key in (
        "inventory", "module", "core", "equipped", "plans", "characters",
    )}
    window.auto_sync_controller = SimpleNamespace(render=lambda: None)
    models, failures, reads, delays, rows = [], [], [], [], []
    original_load = DashboardService.load

    def measured_load(service):
        started = time.perf_counter()
        result = original_load(service)
        reads.append((time.perf_counter() - started) * 1000)
        return result

    DashboardService.load = measured_load

    def apply(model):
        refresh_home_page(window, model)
        models.append(model)

    controller = None
    if (source / "src/ui/controllers/dashboard_controller.py").is_file():
        from src.ui.controllers.dashboard_controller import DashboardController, DashboardDependencies
        controller = DashboardController(
            dependencies=lambda: DashboardDependencies(1, fixture / "user.sqlite3", fixture / "game_static.sqlite3"),
            apply=apply, failed=failures.append, loading=lambda: None, parent=window,
        )
        controller.set_visible(True)

    def refresh(version=None):
        if controller is not None:
            controller.refresh(version=version)
        else:
            apply(DashboardService(fixture / "user.sqlite3", static_database_path=fixture / "game_static.sqlite3").load())

    def pump(predicate, timeout=30):
        deadline = time.perf_counter() + timeout
        while not predicate():
            app.processEvents()
            if failures:
                raise RuntimeError(failures[-1])
            if time.perf_counter() > deadline:
                raise TimeoutError("dashboard did not become ready")
            time.sleep(.001)

    last = time.perf_counter()

    def tick():
        nonlocal last
        now = time.perf_counter()
        delays.append(max(0, (now - last) * 1000 - 10))
        last = now

    timer = QTimer(window)
    timer.timeout.connect(tick)
    timer.start(10)
    for index in range(args.iterations + 1):
        delays.clear()
        last = started = time.perf_counter()
        count = len(models)
        if controller is not None:
            controller.retry()  # Force the same real data read as the synchronous baseline.
        else:
            refresh()
        callback = (time.perf_counter() - started) * 1000
        pump(lambda: len(models) > count)
        ready = (time.perf_counter() - started) * 1000
        end = time.perf_counter() + .03
        pump(lambda: time.perf_counter() >= end)
        rows.append({"callback_ms": round(callback, 3), "ready_ms": round(ready, 3),
                     "max_event_loop_delay_ms": round(max(delays, default=0), 3)})

    refresh(version=("run", 1, 1))
    if controller is not None:
        pump(lambda: not controller._reads.is_running() and not controller._timer.isActive())
    read_count = len(reads)
    for _ in range(args.iterations):
        refresh(version=("run", 1, 1))
    end = time.perf_counter() + .55
    pump(lambda: time.perf_counter() >= end)
    same_version_reads = len(reads) - read_count
    if controller is not None:
        controller.set_visible(False)
    read_count = len(reads)
    for index in range(args.iterations):
        refresh(version=("run", index + 2, 1))
    end = time.perf_counter() + .55
    pump(lambda: time.perf_counter() >= end)
    hidden_reads = len(reads) - read_count
    count = len(models)
    if controller is not None:
        controller.set_visible(True)
        pump(lambda: len(models) > count)
    result = {
        "schema": "calc.dashboard-responsiveness/1", "iterations": args.iterations,
        "scope": "real isolated SQLite dashboard service and summary labels; no full app/native sync/GPU",
        "environment": {"python": sys.version.split()[0], "platform": sys.platform, "qt_platform": "offscreen"},
        "business_digest": hashlib.sha256(json.dumps(models[-1], sort_keys=True, default=str).encode()).hexdigest(),
        "inventory_count": models[-1]["inventory"]["stored_item_count"] if models[-1]["inventory"] else 0,
        "first_enter": rows[0], "repeat_enter": {key: summarize([row[key] for row in rows[1:]]) for key in rows[0]},
        "repeated_same_version_reads": same_version_reads, "hidden_notification_reads": hidden_reads,
        "reads_ms": summarize(reads), "samples": rows,
    }
    if controller is not None:
        controller.close()
        pump(lambda: not controller._reads.is_running())
    timer.stop()
    window.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
