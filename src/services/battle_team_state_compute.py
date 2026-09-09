# 将角色与环境状态计划交给 Rust，Python 只恢复既有区间证据文案。
from __future__ import annotations

from dataclasses import asdict

from src.domain.battle_report import BattleInferredBuffInterval


def _compute(backend, kind, *, hits, battle_end_us, time_stop_intervals, checkpoint, **values):
    needs_channel = kind == "daffodill" and "Effect4" in values.get("effects", ())
    payload = {
        "kind": kind, "hits": [{
            "event_id": hit.event_id, "relative_time_us": hit.relative_time_us,
            "sequence": hit.sequence, "target_id": hit.target_id, "direction": hit.direction,
            "gameplay_effect_id": hit.gameplay_effect_id,
            "channel_input": {key: getattr(hit, key) for key in (
                "direction", "gameplay_effect_id", "classification", "is_follow_up",
                "damage_name", "damage_component", "attack_type", "ability_id", "skill_name",
            )} if needs_channel else {},
        } for hit in hits],
        "battle_end_us": battle_end_us, "time_stop_intervals": time_stop_intervals,
        "topple_duration_us": None, "topple_limit": None, "topple_recovery_speed": None, **values,
    }
    result = backend.compute_batch("team_state_v1", (payload,), checkpoint=checkpoint)
    if len(result) != 1 or not isinstance(result[0].get("intervals"), list):
        raise ValueError("Native team state result shape mismatch")
    return result[0]["intervals"]


def linko_intervals(backend, *, inferences, hits, battle_end_us, time_stop_intervals, character_name, checkpoint=None):
    from src.domain.battle_report import BattleBuffModifierEvidence
    from src.services.battle_linko_coattack_buff_service import _ELEMENT_ASSET_SUFFIXES, _ELEMENT_LABELS, _PASSIVE_ID
    plans = _compute(backend, "linko", hits=hits, battle_end_us=battle_end_us,
                     time_stop_intervals=time_stop_intervals, checkpoint=checkpoint,
                     inferences=[asdict(row) for row in inferences])
    result = []
    for row in plans:
        inference = inferences[row["index"]]
        target, element = row["target_id"], row["element"]
        result.append(BattleInferredBuffInterval(
            interval_id=f"buff:linko:precision-tuning:{target}:{element}:{inference.qte_action_id or inference.event_id}",
            buff_asset_path="/Game/Blueprints/Abilities/Player/Ability_072_Radio/PassiveEffect/Passive3/"
                            f"Buff_Radio072_Passive3_{_ELEMENT_ASSET_SUFFIXES[element]}",
            buff_name=f"精确调频·{_ELEMENT_LABELS[element]}属性抗性降低",
            source_effect_definition_id=_PASSIVE_ID, source_kind="derived_linko_coattack_inference",
            source_character_id=1072, source_character_name=character_name, target_scope="target",
            start_us=row["start_us"], end_us=row["end_us"], stacks=1,
            duration_policy="RefreshWholeStackActiveClock12Seconds",
            state_confidence=inference.confidence, value_confidence="高",
            inference_basis=(
                "官方被动确认同频合击按发起角色属性降低目标 8% 异能抗性、持续 12 秒且同属性只刷新；"
                "实机战报校验支持触发该次同频合击的首击即消费减抗；触发时刻与元素来自版本化同频合击"
                f"推论（{inference.confidence}），不是 Core 原生状态事件。"
            ),
            trigger_event_type="INFERRED_LINKO_COATTACK",
            evidence_action_ids=tuple(value for value in (inference.trigger_action_id, inference.qte_action_id) if value),
            evidence_event_ids=inference.evidence_event_ids,
            modifiers=(BattleBuffModifierEvidence(
                property_id=f"DamageResist{element.title()}Base", modifier_operation="EGameplayModOp::Additive",
                magnitude_kind="confirmed_character_passive", magnitude_value=-0.08,
                calculation_asset_path="", value_confidence="高",
            ),), stacking_type="AggregateByTarget+RefreshWholeStack", stack_limit_count=1, target_id=target,
        ))
    return tuple(result)


def outer_intervals(backend, config, *, hits, battle_end_us, time_stop_intervals, checkpoint=None):
    from src.services.battle_outer_realm_buff_service import BattleOuterRealmBuffService, _modifier
    plans = _compute(backend, "outer", hits=hits, battle_end_us=battle_end_us,
                     time_stop_intervals=time_stop_intervals, checkpoint=checkpoint,
                     components=[asdict(row) for row in config.components],
                     topple_limit=config.topple_limit, topple_recovery_speed=config.topple_recovery_speed)
    result = []
    for row in plans:
        component = config.components[row["component"]]
        requirement = ""
        if row["kind"] == "whole":
            suffix, trigger = str(component.component_ordinal), "OUTER_REALM_WHOLE_BATTLE"
            basis = "正式轨外赛季配置声明整场生效，数值来自官方单值曲线。"
        elif row["kind"] == "stack":
            suffix, trigger = f"stack:{row['ordinal']}", "CORRUPTION_DAMAGE_AFTER_HIT"
            basis = ("按正式浊燃逐击在伤害结算后叠层；1 秒触发间隔、6 秒整组刷新"
                     "和最多 8 层均来自赛季说明，持续时间使用扣时停时钟。")
        elif row["kind"] == "topple":
            hit = hits[row["index"]]
            suffix, trigger = f"topple:{hit.event_id}", "TARGET_TOPPLED"
            requirement = f"battle-target|id={hit.target_id}"
            basis = (f"{hit.gameplay_effect_id} 证明目标进入倾陷；按该目标正式 "
                     f"UnbalMax={float(config.topple_limit):g} ÷ UnbalReduceReset={float(config.topple_recovery_speed):g}，"
                     "在扣时停时钟上重建倾陷恢复区间。")
        else:
            raise ValueError("Unknown native outer state kind")
        result.append(BattleOuterRealmBuffService._base_interval(
            config, component, interval_id=f"outer:{config.level_config_id}:{suffix}",
            start_us=row["start_us"], end_us=row["end_us"], stacks=row["stacks"],
            trigger_event_type=trigger, evidence_event_ids=tuple(row["event_ids"]),
            modifier=_modifier(component, requirement=requirement), inference_basis=basis,
        ))
    return tuple(sorted(result, key=lambda row: (row.start_us, row.end_us, row.interval_id)))


def daffodill_intervals(
    backend, *, actions, hits, battle_end_us, time_stop_intervals, effects,
    character_name, topple_duration_us, checkpoint=None,
):
    from src.services.battle_daffodill_awakening_service import _modifier
    plans = _compute(backend, "daffodill", hits=hits, battle_end_us=battle_end_us,
                     time_stop_intervals=time_stop_intervals, checkpoint=checkpoint,
                     actions=[asdict(row) for row in actions], effects=sorted(effects),
                     topple_duration_us=topple_duration_us)
    result = []
    for row in plans:
        kind, stacks = row["kind"], row["stacks"]
        options = {
            "source_kind": "confirmed_character_awakening_state", "target_scope": "character:1054",
            "target_id": row.get("target_id", ""), "stack_limit_count": 2,
        }
        if kind == "qte":
            action = actions[row["index"]]
            identity = "character-kit:1054:qte-e-enhancement"
            definition = "character_awaken:1054:Effect1" if "Effect1" in effects else identity
            name, interval_id = f"蜕变·E 强化（{stacks} 层）", f"buff:daffodill:qte-e:{action.action_id}"
            policy, trigger = "ConsumeAllOnEAction", "INFERRED_DAFFODILL_QTE_CONSUMED_BY_E"
            basis = ("每次已推算 QTE 累积一层、最多两层，并由下一次已推算 E 整组消耗；"
                     "固定轴只投影 E 通伤，不反推失衡条和倾陷时点。")
            modifiers = (_modifier("DamageUpGeneralBase", row["value"], source_require_tags=("State.Damage.Skill",)),)
            options["source_kind"] = "confirmed_character_action_resource"
        elif kind == "effect4":
            hit = hits[row["index"]]
            identity = definition = "character_awaken:1054:Effect4"
            name, interval_id = f"洞见·倾陷增伤（{stacks} 层）", f"buff:daffodill:effect4:{hit.event_id}"
            policy, trigger = "ObservedToppleSettlementCluster", "INFERRED_DAFFODILL_INSIGHT_TOPPLE"
            basis = ("Q 动作对同一目标建立洞见、最多两层；四觉每层只提高达芙蒂尔"
                     "本人的倾陷伤害。区间仅覆盖轴上已观测的同目标倾陷结算簇。")
            modifiers = (_modifier("UnbalDamageUp", row["value"], requirement=f"battle-hit-target|id={hit.target_id}"),)
        elif kind == "effect5":
            hit = hits[row["index"]]
            identity = definition = "character_awaken:1054:Effect5"
            name, interval_id = f"完美真相·候选追加结算（{stacks} 层）", f"derived:daffodill:effect5:{hit.event_id}"
            policy, trigger = "InstantDerivedSettlementPerInsightStack", "CANDIDATE_DAFFODILL_EFFECT_FIVE_SETTLEMENT"
            basis = ("候选配置启用五觉；零觉基础洞察已额外结算一次，五觉再按原轴 Q "
                     "对同目标建立的每层洞察各追加一次。因此一层共两次，三觉叠至"
                     "二层时共三次；派生行只表示相对基础多出的部分，不写入原始逐击。")
            modifiers = ()
            options["source_kind"] = "candidate_derived_awakening_settlement"
        elif kind == "resonance6":
            hit = hits[row["index"]]
            identity = definition = "character_awaken:1054:resonance_6"
            name, interval_id = "六觉共鸣·暗属性抗性降低", f"buff:daffodill:resonance6:{hit.event_id}"
            policy, trigger = "ReliableToppleDurationActiveClock", "INFERRED_DAFFODILL_RESONANCE_SIX_TOPPLE"
            basis = ("六个普通觉醒已启用；从已观测倾陷结算后一微秒开始，按玩法"
                     "配置中可复核的失衡上限/恢复速度持续，时停不消耗有效时间。")
            modifiers = (_modifier("DamageResistChaosBase", -0.15),)
            options.update(target_scope="target", stack_limit_count=1)
        else:
            raise ValueError("Unknown native Daffodill state kind")
        result.append(BattleInferredBuffInterval(
            interval_id=interval_id, buff_asset_path=identity, buff_name=name,
            source_effect_definition_id=definition, source_character_id=1054, source_character_name=character_name,
            start_us=row["start_us"], end_us=row["end_us"], stacks=stacks, duration_policy=policy,
            state_confidence="中", value_confidence="高", inference_basis=basis, trigger_event_type=trigger,
            evidence_action_ids=tuple(row["action_ids"]), evidence_event_ids=tuple(row["event_ids"]),
            modifiers=modifiers, stacking_type="AggregateByTarget", **options,
        ))
    return tuple(sorted(result, key=lambda row: (row.start_us, row.interval_id)))
