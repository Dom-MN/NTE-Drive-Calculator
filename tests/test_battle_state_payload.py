# 验证状态浅投影保留冻结值和证据引用，同时排除内核不消费的展示字段。
from dataclasses import asdict, replace
import json
import unittest

from src.services.battle_state_payload import (
    ACTION_FIELDS, HIT_FIELDS, RULE_FIELDS, fadia_character, finalize_rows, state_rows,
)
from tests.test_battle_buff_inference_service import _action, _hit
from tests.test_battle_buff_state_compute import _rule
from tests.test_battle_buff_attribute_projection_service import _interval


class StatePayloadTests(unittest.TestCase):
    def test_rows_preserve_optional_values_order_and_frozen_evidence_references(self):
        action = _action()
        hit = replace(_hit(1), character_id=None)
        for original, fields in ((hit, HIT_FIELDS), (action, ACTION_FIELDS), (_rule(), RULE_FIELDS)):
            actual = state_rows((original, original), fields)
            expected = {key: asdict(original)[key] for key in fields}
            self.assertEqual((expected, expected), actual)
            self.assertEqual(tuple(expected), tuple(actual[0]))
        self.assertIsNone(state_rows((hit,), HIT_FIELDS)[0]["character_id"])
        self.assertIs(state_rows((action,), ACTION_FIELDS)[0]["evidence_event_ids"], action.evidence_event_ids)
        self.assertNotIn("inference_basis", state_rows((action,), ACTION_FIELDS)[0])

    def test_finalize_sends_only_required_modifier_tags_and_preserves_tuple(self):
        interval = _interval("sample", start_us=0)
        wire, = finalize_rows((interval,))
        self.assertEqual({"start_us", "end_us", "source_character_id", "buff_asset_path", "modifiers"}, set(wire))
        self.assertEqual({"target_require_tags"}, set(wire["modifiers"][0]))
        self.assertIs(interval.modifiers[0].target_require_tags, wire["modifiers"][0]["target_require_tags"])

    def test_fadia_keeps_missing_null_and_falsy_values_without_materializing_equipment(self):
        character = {
            "awakening_level": "0", "equipment": object(),
            "profile": {"awakening_level": 0, "selected_awaken_effect_ids": (), "unused": object()},
            "stats": [{"source_group": "resolved", "property_id": "PanelHP", "value": None, "unused": object()}],
        }
        actual = fadia_character(character)
        self.assertEqual("0", actual["awakening_level"])
        self.assertEqual({"awakening_level": 0, "selected_awaken_effect_ids": ()}, actual["profile"])
        self.assertIsNone(actual["stats"][0]["value"])
        self.assertNotIn("equipment", actual)
        json.dumps(actual)
        self.assertEqual({}, fadia_character({}))
        self.assertEqual({"profile": None, "stats": None}, fadia_character({"profile": None, "stats": None}))
