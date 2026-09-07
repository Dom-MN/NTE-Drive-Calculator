# 验证战报真实计数、未知阶段与新请求之间的进度切换。
from __future__ import annotations

import unittest

from PySide6.QtWidgets import QApplication

from src.features.battle_report.analysis_progress_bar import BattleAnalysisProgressBar
from src.services.battle_analysis_progress import BattleAnalysisProgress


class BattleProgressFooterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_counts_are_stage_local_and_unknown_stage_returns_to_busy(self):
        footer = BattleAnalysisProgressBar()
        self.addCleanup(footer.close)
        footer.update_progress(BattleAnalysisProgress('buff_remove', '正在计算 Buff', 7, 7))
        self.assertEqual((footer.progress.value(), footer.progress.maximum()), (7, 7))
        self.assertEqual(footer.progress.text(), '本阶段 7 / 7')
        footer.update_progress(BattleAnalysisProgress('core_baseline', '正在建立对照基线…'))
        self.assertEqual(footer.progress.maximum(), 0)
        self.assertFalse(footer.progress.isTextVisible())
        footer.update_progress(BattleAnalysisProgress('core_candidates', '正在比较空幕', 1, 15))
        self.assertEqual((footer.progress.value(), footer.progress.maximum()), (1, 15))
        self.assertIn('1/15', footer.message_label.text())
        footer.finish()
        self.assertTrue(footer.isHidden())

    def test_new_request_clears_previous_complete_count(self):
        footer = BattleAnalysisProgressBar()
        self.addCleanup(footer.close)
        footer.update_progress(BattleAnalysisProgress('core_candidates', '正在比较空幕', 15, 15))
        footer.show_for('marginal')
        self.assertEqual(footer.progress.maximum(), 100)
        self.assertEqual(footer.progress.value(), 1)
        self.assertEqual(footer.progress.text(), '1%')
        self.assertNotIn('15', footer.message_label.text())

    def test_overall_percentage_keeps_actual_stage_count_in_message(self):
        footer = BattleAnalysisProgressBar()
        self.addCleanup(footer.close)
        footer.update_progress(BattleAnalysisProgress('buff_remove', '正在计算 Buff', 7, 27, 14))
        self.assertEqual(footer.progress.text(), '14%')
        self.assertIn('7/27', footer.message_label.text())
        footer.update_progress(BattleAnalysisProgress('core_baseline', '正在建立基线', overall_percent=40))
        self.assertEqual(footer.progress.text(), '40%')
        self.assertEqual(footer.progress.maximum(), 100)


if __name__ == '__main__':
    unittest.main()
