# 验证失败文案保留暴击证据且页面和日志采用同一说明。
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.services.allocation_failure_text import allocation_failure_text
from src.solver.orchestrator import NTEPipelineOrchestrator


NTE_TEST_TIER = "core"


class AllocationFailureTextTests(unittest.TestCase):
    def test_crit_evidence_and_search_uncertainty_share_one_line(self):
        plan = {
            "valid": False,
            "reason": "本次候选装备暴击率下界 74% 超过上限 70%\n；组级搜索预算耗尽，可行性未定",
            "search_status": "budget_exhausted",
            "group_search": {"members": 6, "completed": 5},
        }
        before = deepcopy(plan)
        text = allocation_failure_text(plan)
        self.assertIn("74% 超过上限 70%", text)
        self.assertIn("可行性未定", text)
        self.assertIn("同级组已完成 5/6 人", text)
        self.assertNotIn("\n", text)
        self.assertEqual(plan, before)

    def test_proven_failure_does_not_gain_an_unproven_search_claim(self):
        text = allocation_failure_text({
            "valid": False, "search_status": "constraint_proven",
            "reason": "暴击率上限 3% 低于基础暴击率 5%",
            "group_search": {"members": 6, "completed": 5},
        })
        self.assertEqual(text, "暴击率上限 3% 低于基础暴击率 5%")

    def test_missing_reason_retains_diagnostic_fallback(self):
        self.assertEqual(allocation_failure_text(None), "本次未生成可保存方案，原因待诊断")

    def test_failure_log_uses_the_same_reason_as_result_rendering(self):
        plan = {
            "valid": False, "reason": "本次候选暴击率上界 60% 低于最小值 70%",
            "search_status": "candidate_truncated",
            "group_search": {"members": 6, "completed": 5},
        }
        with patch("src.solver.orchestrator.logger") as log:
            NTEPipelineOrchestrator._render_results(
                SimpleNamespace(), {"Synthetic": plan}, Mock(), {},
            )
        log.error.assert_called_once_with(
            "角色 [{}] 分配失败: {}\n", "Synthetic", allocation_failure_text(plan),
        )


if __name__ == "__main__":
    unittest.main()
