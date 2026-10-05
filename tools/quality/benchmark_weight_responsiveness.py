# 在隔离账号副本中比较真实权重页面加载、保存和重置的前后响应性。
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace


def summarize(values):
    values = sorted(values)
    return {"median_ms": round(statistics.median(values), 3),
            "p95_ms": round(values[math.ceil(len(values) * .95) - 1], 3),
            "max_ms": round(max(values), 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    fixture, source = args.fixture.resolve(), args.source_root.resolve()
    marker = fixture / "ui-benchmark-fixture.json"
    if args.iterations < 1 or not marker.is_file() or not json.loads(marker.read_text()).get("isolated"):
        parser.error("requires a positive iteration count and explicitly isolated fixture")
    for name in ("user.sqlite3", "game_static.sqlite3", "shared.sqlite3"):
        path = (fixture / name).resolve()
        if path.parent != fixture or not path.is_file():
            parser.error("databases must be physical files inside the isolated fixture")
    sys.path.insert(0, str(source))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["NTE_GAME_STATIC_DB"] = str(fixture / "game_static.sqlite3")
    os.environ["NTE_WORKSHOP_WEIGHT_TEMPLATE_FILE"] = str(fixture / "config/workshop_weight_template.json")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget
    from src.features.configuration import page
    from src.storage.sqlite.user_data_dao import UserDataDao
    from src.ui.main_window_data_mixin import MainWindowDataMixin
    from src.utils.logger import logger

    logger.remove()
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = lambda *_args: None
    QMessageBox.question = lambda *_args: QMessageBox.Yes
    errors = []
    QMessageBox.warning = lambda *_args: errors.append(str(_args[-1]))
    with tempfile.TemporaryDirectory(prefix="weights-benchmark-", dir=fixture) as temporary:
        working = Path(temporary) / "user.sqlite3"
        assert fixture in working.resolve().parents
        with sqlite3.connect((fixture / "user.sqlite3").as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(working) as clone:
            original.backup(clone)
        original.close()
        clone.close()
        assets = json.loads(marker.read_text()).get("asset_root")
        window = QWidget()
        paths = SimpleNamespace(config_dir=fixture / "config", static_database_path=fixture / "game_static.sqlite3",
                                equipment_allocation_database_path=fixture / "game_static.sqlite3",
                                shared_database_path=fixture / "shared.sqlite3")
        window.app_context = SimpleNamespace(generation=1, paths=paths,
            account=SimpleNamespace(active_account_id="isolated", user_database_path=working))
        window._go = lambda _key: None
        for method in ("_reset_current_config_weights", "_reset_all_config_weights", "_save_config_form"):
            setattr(window, method, lambda: None)
        catalog_reads, notifications = [], []

        def reload_catalog(*_args, **_kwargs):
            started = time.perf_counter()
            MainWindowDataMixin._read_allocation_catalog(paths.config_dir, working, paths.static_database_path, Path(assets))
            catalog_reads.append((time.perf_counter() - started) * 1000)

        # The baseline synchronously prepares the real catalog here, but no game or full-app UI is created.
        window._load_data = reload_catalog
        window.on_configuration_changed = lambda: notifications.append(1)
        QVBoxLayout(window).addWidget(page.build_config_page(window))
        window.resize(1200, 800)
        window.show()
        delays, samples = [], {"enter": [], "save": [], "reset": []}
        last_tick = time.perf_counter()

        def tick():
            nonlocal last_tick
            now = time.perf_counter()
            delays.append(max(0, (now - last_tick) * 1000 - 10))
            last_tick = now

        timer = QTimer(window)
        timer.timeout.connect(tick)
        timer.start(10)

        def ready():
            controller = getattr(window, "_basic_weight_controller", None)
            return (not getattr(getattr(controller, "_reads", None), "is_running", lambda: False)()
                    and not getattr(controller, "is_writing", lambda: False)()
                    and bool(getattr(window, "_config_form_data", None)))

        def pump(predicate):
            deadline = time.perf_counter() + 60
            while not predicate():
                app.processEvents()
                if errors:
                    raise RuntimeError(errors[-1])
                if time.perf_counter() > deadline:
                    raise TimeoutError("weight operation did not become ready")
                time.sleep(.001)
            if errors:
                raise RuntimeError(errors[-1])

        def measure(kind, action):
            nonlocal last_tick
            delays.clear()
            last_tick = started = time.perf_counter()
            action()
            callback = (time.perf_counter() - started) * 1000
            pump(ready)
            elapsed = (time.perf_counter() - started) * 1000
            end = time.perf_counter() + .03
            pump(lambda: time.perf_counter() >= end)
            samples[kind].append({"callback_ms": round(callback, 3), "ready_ms": round(elapsed, 3),
                                  "max_event_loop_delay_ms": round(max(delays, default=0), 3),
                                  "widget_count": len(window.findChildren(QWidget))})

        for _ in range(args.iterations + 1):
            measure("enter", lambda: page.switch_config_form(window, config_dir=paths.config_dir))
        role_name = next(name for name, row in window._config_form_data.items() if int(row["character_id"]) == 1051)
        digests = []
        for index in range(args.iterations):
            window._config_form_data[role_name]["weights"]["CritBase"] = 2 + index / 1000
            window._config_dirty = True
            window._config_dirty_character_ids = {1051}
            measure("save", lambda: page.save_config_form(window, paths.config_dir, None))
            with UserDataDao(working) as dao:
                weights = dao.get_character_weight_preferences(1051)
            digests.append(hashlib.sha256(json.dumps({key: weights[key] for key in ("source_kind", "property_weights", "main_property_weights")}, sort_keys=True).encode()).hexdigest())
        for _ in range(args.iterations):
            window._config_active_role = role_name
            measure("reset", lambda: page.reset_current_config_weights(window, paths.config_dir))
        result = {
            "schema": "calc.weight-responsiveness/1", "iterations": args.iterations,
            "scope": "real weight page, isolated SQLite writes and baseline catalog preparation; no full app/native/game",
            "environment": {"python": sys.version.split()[0], "platform": sys.platform, "qt_platform": "offscreen"},
            "role_count": len(window._config_form_data), "save_result_digests": digests,
            "final_model_digest": hashlib.sha256(json.dumps(window._config_form_data, sort_keys=True, default=str).encode()).hexdigest(),
            "first_enter": samples["enter"][0],
            "repeat_enter": {key: summarize([row[key] for row in samples["enter"][1:]]) for key in ("callback_ms", "ready_ms", "max_event_loop_delay_ms")},
            "save": {key: summarize([row[key] for row in samples["save"]]) for key in ("callback_ms", "ready_ms", "max_event_loop_delay_ms")},
            "reset": {key: summarize([row[key] for row in samples["reset"]]) for key in ("callback_ms", "ready_ms", "max_event_loop_delay_ms")},
            "synchronous_catalog_read_count": len(catalog_reads), "change_notification_count": len(notifications),
            "samples": samples,
        }
        controller = getattr(window, "_basic_weight_controller", None)
        if hasattr(controller, "close"):
            controller.close()
        pump(lambda: not getattr(getattr(controller, "_reads", None), "is_running", lambda: False)())
        timer.stop()
        window.close()
        window.deleteLater()
        app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"samples", "save_result_digests"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
