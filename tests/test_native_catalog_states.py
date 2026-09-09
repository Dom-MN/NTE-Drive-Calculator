# 对照公开状态回归验证原生最终证据组装，测试过程不调用 Python 元数据适配器。
from dataclasses import asdict, is_dataclass
import inspect
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from src.services.battle_zankou_form_buff_service import BattleZankouFormBuffService
from src.services.battle_shinku_rage_buff_service import BattleShinkuRageBuffService
from src.services.battle_fadia_hp_stack_service import BattleFadiaHpStackService
from src.services.battle_daffodill_awakening_service import BattleDaffodillAwakeningService
from src.services.battle_outer_realm_buff_service import BattleOuterRealmBuffService
from src.services.battle_linko_coattack_buff_service import BattleLinkoCoattackBuffService
from src.services.battle_treatment_event_service import BattleTreatmentEventService
from src.services.battle_treatment_buff_service import BattleTreatmentBuffService
from src.services.battle_buff_inference_service import BattleBuffInferenceService
from tests import test_battle_zankou_form_buff_service as zankou
from tests import test_battle_shinku_rage_buff_service as shinku
from tests import test_battle_fadia_hp_stack_service as fadia
from tests import test_battle_daffodill_awakening_service as daffodill
from tests import test_battle_outer_realm_buff_service as outer
from tests import test_battle_linko_formula_projection as linko
from tests import test_battle_treatment_event_service as treatment
from tests import test_battle_buff_inference_service as buff
from tests import test_battle_fork_refinement_service as fork
from tests import test_battle_fork_state_refinement_service as fork_state
from tests import test_battle_fork_damage_completion_service as fork_damage
from tests import test_battle_fork_trigger_refinement_service as fork_trigger
from tests import test_battle_fork_periodic_refinement_service as fork_periodic


def normalize(value):
    return json.loads(json.dumps(value, default=lambda v: asdict(v) if is_dataclass(v) else list(v)))


class _Compare:
    def setUp(self):
        original = self.service.infer
        signature = inspect.signature(original)

        def compare(*args, **kwargs):
            expected = original(*args, **kwargs)
            binding = signature.bind(*args, **kwargs)
            binding.apply_defaults()
            values = binding.arguments
            request = {"operation": "state", "kind": self.kind, "build": values.get("build"),
                       "config": values.get("config"), "topple_duration_us": values.get("topple_duration_us"),
                       "state_buff_intervals": values.get("state_buff_intervals", ()),
                       "recover_ratio": values.get("zankou_effect_three_recover_ratio"),
                       "infer_buffs": self.kind == "treatment",
                       "analysis": {"hits": values.get("hits", ()), "inferred_actions": values.get("actions", ()),
                                    "battle_end_us": values.get("battle_end_us", 1),
                                    "time_stop_intervals": values.get("time_stop_intervals", ()),
                                    "max_hp_events": values.get("max_hp_events", ()),
                                    "linko_coattack_inferences": values.get("inferences", ())}}
            if self.kind == "buff":
                request = {"operation": "intervals", "input": {key: value for key, value in values.items()
                           if key not in {"compute_backend", "checkpoint"}}}
            completed = subprocess.run([os.environ["NTE_CATALOG_PROBE"]], input=json.dumps(normalize(request), ensure_ascii=False),
                                       text=True, encoding="utf-8", capture_output=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            actual = json.loads(completed.stdout)["events" if self.kind == "treatment" else "intervals"]
            self.assert_json(normalize(expected), actual)
            if self.kind == "treatment":
                expected_buffs = BattleTreatmentBuffService.infer(
                    build=values.get("build"), treatment_events=expected,
                    battle_end_us=values["battle_end_us"],
                    time_stop_intervals=values.get("time_stop_intervals", ()),
                )
                self.assert_json(normalize(expected_buffs), json.loads(completed.stdout)["buff_intervals"])
            return expected

        patcher = patch.object(self.service, "infer", side_effect=compare)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_json(self, expected, actual, path="result"):
        if isinstance(expected, dict):
            self.assertEqual(set(expected), set(actual), path)
            for key in expected:
                self.assert_json(expected[key], actual[key], f"{path}.{key}")
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), path)
            for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
                self.assert_json(left, right, f"{path}[{index}]")
        elif isinstance(expected, float):
            self.assertAlmostEqual(expected, actual, places=9, msg=path)
        else:
            self.assertEqual(expected, actual, path)


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogZankou(_Compare, zankou.BattleZankouFormBuffServiceTests):
    service, kind = BattleZankouFormBuffService, "zankou"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogShinku(_Compare, shinku.BattleShinkuRageBuffServiceTests):
    service, kind = BattleShinkuRageBuffService, "shinku"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogFadia(_Compare, fadia.BattleFadiaHpStackServiceTests):
    service, kind = BattleFadiaHpStackService, "fadia"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogDaffodill(_Compare, daffodill.BattleDaffodillAwakeningServiceTests):
    service, kind = BattleDaffodillAwakeningService, "daffodill"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogOuter(_Compare, outer.BattleOuterRealmBuffServiceTests):
    service, kind = BattleOuterRealmBuffService, "outer"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogLinko(_Compare, linko.BattleLinkoPrecisionTuningTests):
    service, kind = BattleLinkoCoattackBuffService, "linko"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogTreatment(_Compare, treatment.BattleTreatmentEventServiceTests):
    service, kind = BattleTreatmentEventService, "treatment"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogBuff(_Compare, buff.BattleBuffInferenceServiceTests):
    service, kind = BattleBuffInferenceService, "buff"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogFork(_Compare, fork.BattleForkRefinementServiceTests):
    service, kind = BattleBuffInferenceService, "buff"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogForkState(_Compare, fork_state.BattleForkStateRefinementServiceTests):
    service, kind = BattleBuffInferenceService, "buff"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogForkDamage(_Compare, fork_damage.BattleForkDamageCompletionServiceTests):
    service, kind = BattleBuffInferenceService, "buff"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogForkTrigger(_Compare, fork_trigger.BattleForkTriggerRefinementServiceTests):
    service, kind = BattleBuffInferenceService, "buff"


@unittest.skipUnless(os.environ.get("NTE_CATALOG_PROBE"), "independent catalog probe required")
class CatalogForkPeriodic(_Compare, fork_periodic.BattleForkPeriodicRefinementServiceTests):
    service, kind = BattleBuffInferenceService, "buff"
