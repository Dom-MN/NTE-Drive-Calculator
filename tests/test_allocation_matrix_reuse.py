# 验证图纸评分行复用保持匹配结果且不跨候选池和配置泄漏。
import unittest
from unittest.mock import patch

import numpy as np

from src.models.equipment import Drive
from src.optimizer.role_priority_strategy import RolePriorityStrategy


def _strategy():
    return RolePriorityStrategy(
        {"A": {"default_set": "Set"}},
        {"Set": {"shapes": ["X"]}},
        {},
    )


def _drive(uid, shape, score, **sub_stats):
    return Drive(
        uid=uid, quality="Gold", area=1, shape_id=shape, set_name="Set",
        main_stats={"a": 1, "b": 1}, sub_stats=sub_stats, role_scores={"A": score},
    )


class AllocationMatrixReuseTests(unittest.TestCase):
    def test_repeated_combos_reuse_scores_and_keep_distinct_uid_columns(self):
        strategy = _strategy()
        drives = [_drive("a", "X", 10), _drive("b", "X", 8), _drive("c", "Y", 7)]
        blueprint = {"set_pieces": ["X"], "extra_pieces": ["X", "Y"]}
        prepared = strategy._prepare_profit_matrix(drives, {})
        with patch.object(strategy, "_rank_score_for_drive", wraps=strategy._rank_score_for_drive) as rank:
            _, first_profit, first_ranking = prepared.build([blueprint], ["A"], {"A": "Set"})
            # Matching callers may mutate returned arrays without corrupting reusable rows.
            first_profit[0, 0] = -999
            first_ranking[0, 0] = -999
            _, profit, ranking = prepared.build([blueprint], ["A"], {"A": "Set"})
        np.testing.assert_array_equal(profit, [[10, 8, -10000], [10, 8, -10000], [-10000, -10000, 7]])
        np.testing.assert_array_equal(ranking, profit)
        assert rank.call_count == 3

    def test_bonus_rows_do_not_leak_into_extra_or_four_piece_slots(self):
        strategy = _strategy()
        drives = [_drive("a", "X", 10), _drive("b", "X", 8)]
        prepared = strategy._prepare_profit_matrix(drives, {})
        two_piece = {"set_pieces": ["X"], "extra_pieces": ["X"], "set_effect_mode": "two_piece"}
        four_piece = {**two_piece, "set_effect_mode": "four_piece"}
        with patch.object(strategy, "_extra_shape_hidden_bonus", return_value=3):
            _, profit, ranking = prepared.build([two_piece], ["A"], {"A": "Set"})
            np.testing.assert_array_equal(profit, [[10, 8], [10, 8]])
            np.testing.assert_array_equal(ranking, [[13, 11], [10, 8]])
            _, _, plain = prepared.build([four_piece], ["A"], {"A": "Set"})
            np.testing.assert_array_equal(plain, profit)
            _, _, disabled = prepared.build([two_piece], ["A"], {"A": "Set"}, include_extra_shape_bonus=False)
            np.testing.assert_array_equal(disabled, profit)

    def test_new_candidate_pool_and_blacklist_get_fresh_rows(self):
        strategy = _strategy()
        a, b = _drive("a", "X", 10, blocked=1), _drive("b", "X", 8)
        blueprint = {"set_pieces": [], "extra_pieces": ["X"]}
        first = strategy._prepare_profit_matrix([a, b], {})
        _, profit, _ = first.build([blueprint], ["A"], {"A": "Set"})
        np.testing.assert_array_equal(profit, [[10, 8]])
        second = strategy._prepare_profit_matrix([b, a], {"A": {"blacklist": ["blocked"]}})
        _, profit, _ = second.build([blueprint], ["A"], {"A": "Set"})
        np.testing.assert_array_equal(profit, [[8, -10000]])
        third = strategy._prepare_profit_matrix([b], {})
        _, profit, _ = third.build([blueprint], ["A"], {"A": "Set"})
        np.testing.assert_array_equal(profit, [[8]])

    def test_blueprint_ranking_builds_shape_buckets_once_per_bonus_mode(self):
        strategy = _strategy()
        drives = [_drive("a", "X", 10), _drive("b", "X", 8), _drive("c", "Y", 7)]
        blueprints = [
            {"set_pieces": ["X"], "extra_pieces": ["Y"]},
            {"set_pieces": ["X"], "extra_pieces": ["X"]},
            {"set_pieces": ["X"], "extra_pieces": ["Y"], "set_effect_mode": "two_piece"},
        ]
        with patch.object(strategy, "_extra_shape_hidden_bonus", return_value=3):
            expected = sorted(
                [(strategy._blueprint_theoretical_score("A", bp, drives, {"A": "Set"}), index, bp)
                 for index, bp in enumerate(blueprints)],
                key=lambda item: (-item[0], item[1]),
            )
            with patch.object(strategy, "_shape_score_buckets", wraps=strategy._shape_score_buckets) as buckets:
                actual = strategy._rank_role_blueprints([blueprints], ["A"], drives, {"A": "Set"})
        assert actual == [expected]
        assert buckets.call_count == 2
