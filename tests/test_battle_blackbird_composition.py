# 验证黑羽追加黯星按正式来源独立展示且不改变实测伤害。
from dataclasses import replace

import pytest

from src.domain.battle_report import BattleAnalysisHit
from src.services.battle_damage_composition_service import (
    BattleDamageCompositionService,
    classify_battle_hit_channel,
)


def nova_hit(effect: str, damage: float = 100.0) -> BattleAnalysisHit:
    return BattleAnalysisHit(
        event_id="nova:primary", sequence=1, relative_time_us=0,
        character_id=1042, character_name="黑羽", skill_name="环合",
        damage_name="环合", damage_component="", attack_type="环合",
        damage_attribute="psychically", target_id="target", target_name="目标",
        damage=damage, direction="outgoing", is_follow_up=False,
        classification="reaction", gameplay_effect_id=effect,
    )


@pytest.mark.parametrize("effect", [
    "GE_Reaction_4_new_1042_Damage",
    "GE_Reaction_4_new_1042_Damage_C",
    "/Game/Effects/GE_Reaction_4_new_1042_Damage_C",
    "\\Game\\Effects\\ge_reaction_4_new_1042_damage_c",
])
@pytest.mark.parametrize("grouping", ["coarse", "fine"])
def test_extra_nova_stays_separate_from_base_nova_and_unknown(effect, grouping):
    extra = nova_hit(effect, 370_021.0)
    base = replace(nova_hit("Buff_Reaction_4_new", 226_800.0),
                   event_id="base", damage_name="黯星", attack_type="黯星")
    unknown = replace(nova_hit("GE_Reaction_Unresolved_Damage", 100.0),
                      event_id="unknown")
    result = BattleDamageCompositionService.calculate_from_hits(
        roles=(), hits=(extra, base, unknown),
        segment_total_damage=596_921.0, grouping=grouping,
    )
    role, = result.roles
    entries = {entry.label: entry.damage for entry in role.entries}
    assert entries == {
        "鸫歌·追加黯星": 370_021.0,
        "环合·黯星": 226_800.0,
        "环合（未细分）": 100.0,
    }
    assert role.total_damage == 596_921.0
    assert extra.damage_name == "环合"
    assert extra.damage == 370_021.0


@pytest.mark.parametrize("effect", [
    "GE_Reaction_4_new_9999_Damage", "Buff_Reaction_4_new",
    "GE_Reaction_4_new_1042_Damage_Extra", "",
])
def test_other_or_missing_sources_are_not_promoted(effect):
    assert classify_battle_hit_channel(nova_hit(effect))[0] == "reaction_unknown"


def test_incoming_extra_nova_is_not_outgoing_damage():
    hit = replace(nova_hit("GE_Reaction_4_new_1042_Damage"), direction="incoming")
    assert classify_battle_hit_channel(hit) == ("incoming", "承伤")
