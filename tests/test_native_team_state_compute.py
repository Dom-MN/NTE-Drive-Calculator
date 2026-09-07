# 对公共角色与环境状态回归执行完整结果差分，保留时停、目标、刷新及觉醒证据。
from __future__ import annotations

import math
import os
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from src.integrations.nte_analysis_core import NteAnalysisCoreClient
from src.services.battle_daffodill_awakening_service import BattleDaffodillAwakeningService
from src.services.battle_linko_coattack_buff_service import BattleLinkoCoattackBuffService
from src.services.battle_outer_realm_buff_service import BattleOuterRealmBuffService
from tests import test_battle_daffodill_awakening_service as public_daffodill_tests
from tests import test_battle_linko_formula_projection as public_linko_tests
from tests import test_battle_outer_realm_buff_service as public_outer_tests
from tests.test_battle_linko_formula_projection import (
    _build, _hit, _inference,
)


class _NativeStateDifferential:
    @classmethod
    def setUpClass(cls):
        cls.native = NteAnalysisCoreClient.from_executable(
            Path(os.environ["NTE_ANALYSIS_CORE_TEST_EXE"]), "public-team-state-test",
        )
        if not cls.native.supports_battle_compute:
            raise AssertionError("native battle compute capability required")

    def setUp(self):
        original = self.service.infer

        def compare(*args, **kwargs):
            expected = original(*args, **kwargs)
            actual = original(*args, **kwargs, compute_backend=self.native)
            self.assert_equivalent(tuple(map(asdict, expected)), tuple(map(asdict, actual)))
            return actual

        patcher = patch.object(self.service, "infer", side_effect=compare)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_equivalent(self, expected, actual):
        if isinstance(expected, dict):
            self.assertEqual(expected.keys(), actual.keys())
            for key in expected:
                self.assert_equivalent(expected[key], actual[key])
        elif isinstance(expected, (tuple, list)):
            self.assertEqual(len(expected), len(actual))
            for left, right in zip(expected, actual, strict=True):
                self.assert_equivalent(left, right)
        elif isinstance(expected, float):
            self.assertTrue(math.isclose(expected, actual, rel_tol=1e-11, abs_tol=1e-11))
        else:
            self.assertEqual(expected, actual)


@unittest.skipUnless(os.environ.get("NTE_ANALYSIS_CORE_TEST_EXE"), "explicit isolated executable not configured")
class NativeDaffodillStateTests(_NativeStateDifferential, public_daffodill_tests.BattleDaffodillAwakeningServiceTests):
    service = BattleDaffodillAwakeningService


@unittest.skipUnless(os.environ.get("NTE_ANALYSIS_CORE_TEST_EXE"), "explicit isolated executable not configured")
class NativeOuterStateTests(_NativeStateDifferential, public_outer_tests.BattleOuterRealmBuffServiceTests):
    service = BattleOuterRealmBuffService


@unittest.skipUnless(os.environ.get("NTE_ANALYSIS_CORE_TEST_EXE"), "explicit isolated executable not configured")
class NativeLinkoStateTests(_NativeStateDifferential, public_linko_tests.BattleLinkoPrecisionTuningTests):
    service = BattleLinkoCoattackBuffService

    def test_stop_plateaus_refresh_and_missing_inference_targets(self):
        hits = (
            _hit("1:primary", relative_time_us=1_000_000),
            _hit("2:primary", relative_time_us=7_000_000),
            replace(_hit("3:primary", relative_time_us=7_000_000), target_id="second"),
            replace(_hit("4:primary", relative_time_us=8_000_000), target_id=""),
        )
        inferences = tuple(
            _inference(hit.event_id, time_us=hit.relative_time_us) for hit in hits
        )
        inferences = (
            *inferences, inferences[1],
            replace(inferences[0], event_id="missing"),
            replace(inferences[0], damage_attribute="unknown"),
        )
        rows = self.service.infer(
            build=_build(), inferences=inferences, hits=hits, battle_end_us=30_000_000,
            time_stop_intervals=((2_000_000, 5_000_000), (4_000_000, 6_000_000)),
        )
        self.assertEqual(3, len(rows))
        self.assertEqual(7_000_000, rows[0].end_us)
        self.assertEqual({"target-1", "second"}, {row.target_id for row in rows})
