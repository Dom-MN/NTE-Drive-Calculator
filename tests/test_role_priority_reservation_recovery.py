# 验证前序同分回填冲突耗尽搜索后仍保持原优先级和合法图纸。
import unittest
from unittest.mock import patch

from src.models.equipment import Drive
from src.optimizer.role_priority_strategy import RolePriorityStrategy


NTE_TEST_TIER = "core"


class RolePriorityReservationRecoveryTests(unittest.TestCase):
    def test_exhausted_search_jointly_preserves_all_prior_slots(self):
        roles = ["High", "A", "B"]
        shapes = [f"C{index}" for index in range(5)]
        strategy = RolePriorityStrategy(
            {role: {"default_set": "Set", "weights": {"攻击力%": 1.0, "暴击率%": 1.0},
                    "extra_shape_label": "2型", "extra_shape_buffs": {"攻击力%": 10.0}}
             for role in roles},
            {"Set": {"shapes": []}},
            {role: [{"set_pieces": [], "extra_pieces": shapes}] for role in roles},
        )
        drives = [
            Drive(
                uid=f"{shape}-{kind}", quality="Gold", area=2,
                shape_id=shape, set_name="Set", main_stats={"攻击力": 1.0, "生命值": 1.0},
                role_scores={"High": 10.0 if kind in ("a", "b") else 1.0,
                             "A": 100.0 if kind in ("a", "b") else 1.0,
                             "B": 100.0 if kind in ("a", "b") else 1.0},
            )
            for shape in shapes for kind in ("a", "b", "y", "z")
        ]
        with patch.object(strategy, "_find_best_group_fit", wraps=strategy._find_best_group_fit) as solve:
            result = strategy.execute(
                {"drives": drives, "all_drives": drives, "tapes": {}},
                roles, {role: "Set" for role in roles},
                priority_groups=[["High"], ["A", "B"]],
            )
        self.assertEqual(solve.call_count, 25)
        self.assertTrue(all("reservation_candidates" not in call.kwargs for call in solve.call_args_list[:24]))
        self.assertIn("reservation_candidates", solve.call_args_list[-1].kwargs)
        self.assertTrue(all(result[role]["valid"] for role in roles))
        self.assertEqual(result["High"]["score"], 50.0)
        self.assertEqual(sum(result[role]["score"] for role in ("A", "B")), 505.0)
        all_uids = []
        for role in roles:
            assigned = result[role]["assigned_extra_drives"]
            self.assertEqual([drive.shape_id for drive in assigned], shapes)
            self.assertEqual(result[role]["score"], sum(drive.role_scores[role] for drive in assigned))
            all_uids.extend(drive.uid for drive in assigned)
        self.assertEqual(len(all_uids), len(set(all_uids)))


if __name__ == "__main__":
    unittest.main()
