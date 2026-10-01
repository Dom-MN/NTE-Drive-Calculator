# 验证帧采样在游戏切换、启动失败、停止和宿主退出时的资源归属。
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from src.integrations.presentmon_lifetime import CollectorJob, _process_identity, stop_session
from src.integrations.presentmon_metrics import PresentMon

NTE_TEST_TIER = 'core'
MODULE = 'src.integrations.presentmon_metrics'


class PresentMonLifetimeTests(unittest.TestCase):
    def source(self, reader=lambda: None):
        source = PresentMon(Path('unused'), reader)
        source._process = Mock(stdout=None, stderr=None)
        source._process.poll.return_value = None
        process = source._process
        def finish(timeout):
            process.poll.return_value = 0
            return 0
        process.wait.side_effect = finish
        source._pid = 42
        source._session = 'NTE-Calc-v2-123-456-' + 'a' * 32
        return source

    def test_game_exit_stops_live_collector_without_waiting_for_presentmon(self):
        source = self.source()
        process = source._process
        with patch(MODULE + '.stop_session') as stop:
            metrics = source.sample()
        self.assertEqual(stop.call_count, 2)
        process.wait.assert_called()
        self.assertIsNone(source._process)
        self.assertIsNone(metrics['fps_milli'])
        self.assertEqual(metrics['frame_error'], '等待游戏')

    def test_new_game_stops_old_collector_and_discards_old_window(self):
        source = self.source(lambda: 43)
        source._window.add({'TimeInSeconds': '1', 'msBetweenPresents': '10', 'SwapChainAddress': 'a'}, 1)
        with patch(MODULE + '.stop_session') as stop:
            metrics = source.sample()  # Missing executable prevents a real new launch.
        self.assertEqual(stop.call_count, 2)
        self.assertEqual(source._pid, 43)
        self.assertIsNone(metrics['fps_milli'])
        self.assertFalse(source._window.frames)

    def test_unverifiable_game_stops_instead_of_keeping_stale_pid(self):
        source = self.source(Mock(side_effect=PermissionError))
        with patch(MODULE + '.stop_session') as stop:
            metrics = source.sample()
        self.assertEqual(stop.call_count, 2)
        self.assertIn('已停止', metrics['frame_error'])
        self.assertIsNone(source._process)

    def test_close_reaps_etw_even_after_child_exits_and_is_idempotent(self):
        source = self.source()
        source._process.poll.return_value = 0
        job = source._job = Mock()
        with patch(MODULE + '.stop_session') as stop, patch(MODULE + '.subprocess.Popen') as spawn:
            source.close()
            source.close()
        self.assertEqual(stop.call_count, 2)
        spawn.assert_not_called()
        job.close.assert_called_once()

    def test_hung_collector_is_killed_and_job_closed_when_etw_stop_fails(self):
        source = self.source()
        process = source._process
        process.wait.side_effect = [subprocess.TimeoutExpired('collector', 1), 0]
        job = source._job = Mock()
        with patch(MODULE + '.stop_session', side_effect=PermissionError):
            source.close()
        process.kill.assert_called_once()
        job.close.assert_called_once()

    def test_failed_job_attachment_does_not_leave_started_child(self):
        source = PresentMon(Path('unused'), lambda: 42)
        source._verified = source._reaped = True
        process = Mock(stdout=None, stderr=None)
        process.poll.return_value = 0
        job = Mock()
        job.attach.side_effect = OSError('job denied')
        with patch.object(Path, 'is_file', return_value=True), \
                patch(MODULE + '.session_name', return_value='NTE-Calc-v2-123-456-' + 'a' * 32), \
                patch(MODULE + '.CollectorJob', return_value=job), \
                patch(MODULE + '.subprocess.Popen', return_value=process), \
                patch(MODULE + '.stop_session'):
            metrics = source.sample()
        self.assertIsNone(source._process)
        job.close.assert_called_once()
        self.assertIn('启动失败', metrics['frame_error'])

    def test_stop_rejects_other_tools_sessions(self):
        for name in ('PresentMon', 'OtherMonitor-123', '', 'NTE-Calc-v2-invalid'):
            with self.assertRaises(ValueError):
                stop_session(name)

    @unittest.skipUnless(os.name == 'nt', 'Windows job API')
    def test_windows_job_close_really_terminates_owned_child(self):
        job = CollectorJob()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job.attach(child)
            job.close()
            self.assertIsNotNone(child.wait(timeout=3))
        finally:
            job.close()
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)

    @unittest.skipUnless(os.name == 'nt', 'Windows job API')
    def test_abrupt_owner_exit_really_terminates_collector(self):
        code = """
import os, subprocess, sys
from src.integrations.presentmon_lifetime import CollectorJob
job = CollectorJob()
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                         creationflags=subprocess.CREATE_NO_WINDOW)
job.attach(child)
print(child.pid, flush=True)
os._exit(0)
"""
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
                                capture_output=True, text=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(_process_identity(int(result.stdout.strip())))
