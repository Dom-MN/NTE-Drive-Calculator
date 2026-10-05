# 验证进程状态未确认时后台自动部署与自动 Loader 不写盘，仍保持等待。
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from src.domain.work_mode import WorkModeProbe
from src.services.work_mode_runtime import WorkModeRuntime
from src.services.work_mode_service import WorkModeService


class UnconfirmedProcessStateGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "HTGame.exe"
        self.game.write_bytes(b"game")
        self.policy = WorkModeService(self.root / "work-mode.json")
        self.policy.set_game_executable(str(self.game))
        self.policy.set_cleanup_pending(False)
        self.process = MagicMock(return_value=None)
        self.runtime = WorkModeRuntime(
            policy=self.policy,
            native_session=SimpleNamespace(battle_active=False, close=MagicMock()),
            loader=SimpleNamespace(
                snapshot=MagicMock(return_value=SimpleNamespace(phase="stopped")),
                start_loader=MagicMock(),
            ),
            application_root=self.root, config_dir=self.root / "config",
            game_running=self.process,
        )
        self.runtime._bundle = SimpleNamespace(ready=True, issues=(), native_capabilities=frozenset())
        self.runtime._native_deployed = SimpleNamespace(files_compatible=False, files={})

    def test_probe_can_report_an_unconfirmed_process_state(self) -> None:
        self.assertFalse(WorkModeProbe().game_running)
        self.assertIsNone(replace(WorkModeProbe(), game_running=None).game_running)

    def test_automatic_deploy_waits_without_a_confirmed_exit(self) -> None:
        for running, expected in ((None, "未能确认"), (True, "游戏运行中")):
            with self.subTest(running=running):
                with patch("src.services.work_mode_runtime.deploy_native_plugin") as deploy:
                    self.runtime._automatic_native_deploy(running)
                deploy.assert_not_called()
                self.assertIn(expected, self.runtime.cleanup_detail)
                self.assertEqual("", self.runtime._auto_error)

    def test_automatic_loader_waits_without_a_confirmed_exit(self) -> None:
        self.runtime.start_native_loader = MagicMock()
        self.runtime._automatic_native_loader(None)
        self.runtime.start_native_loader.assert_not_called()
        self.runtime._automatic_native_loader(True)
        self.runtime.start_native_loader.assert_not_called()
        self.runtime._automatic_native_loader(False)
        self.runtime.start_native_loader.assert_called_once_with(automatic=True)
