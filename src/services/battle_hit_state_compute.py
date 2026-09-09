# 调度 DOT 与残虹蓄焰状态计算并恢复原有中文证据。
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.native_analysis import BattleComputeBackend


_NAMES = {
    "nightmare": "噩梦", "erosion": "蚀心", "venom": "鸩火",
    "scorch": "浊燃", "cang_field": "判予秋", "adler_skill": "诛恶护持",
}
_STATE_BASIS = {
    "nightmare": (
        "按同一目标逐击正向重放命中后加层；安魂曲除 QTE 与"
        "学习 E 外，每个有效直伤 hit 施加 1 层噩梦；每次噩梦"
        "实际跳伤后再触发残虹浊燃补 1 层；最大 10 层；"
        "每层独立按扣时停时钟计算到期时间；"
    ),
    "erosion": (
        "按同一目标逐击正向重放蚀心施加；幻境形态普通/分支命中"
        "加 1 层，强化技能命中加 5 层；最大 10 层；30 秒持续时间"
        "按扣除时停的有效战斗时钟计算，时停期间不流逝"
    ),
    "venom": (
        "按同一目标逐击正向重放鸩火施加；「血宴入梦时」最终施加点"
        "加 5 层；幻境形态普通攻击扩散只刷新已有鸩火持续时间，"
        "不增加层数；最大 10 层；30 秒持续时间按扣除时停的有效"
        "战斗时钟计算，时停期间不流逝"
    ),
    "cang_field": (
        "优先按判予秋展开直伤划分 Q 批次；同目标第一跳作为该批状态"
        "已施加 1 层的可见证据；缺失展开直伤时按正式 12/16 秒领域"
        "维持保守批次；每个实际可见 DOT 跳伤另触发残虹补 1 层，"
        "中间漏跳不反推"
    ),
    "adler_skill": (
        "优先按诛恶护持初始直伤划分 E 批次；同目标第一跳作为该批状态"
        "已施加 1 层的可见证据；缺失初始直伤时按正式 10 秒持续时间"
        "维持保守批次；每个实际可见 DOT 跳伤另触发残虹补 1 层，"
        "中间漏跳不反推"
    ),
}
_LOWER_BASIS = {
    "nightmare": (
        "本击前未找到施加事件；本跳只证明至少存在 1 份噩梦，"
        "不反推精确层数"
    ),
    "erosion": (
        "；本击前缺少可见施加事件，本跳只证明至少存在 1 份蚀心，"
        "不把观测下限解释成精确 1 层"
    ),
    "venom": (
        "；本击前缺少可见施加事件，本跳只证明至少存在 1 份鸩火，"
        "不把观测下限解释成精确 1 层"
    ),
}


def compute_hit_state(
    kind: str, inputs: dict[str, Any], *, backend: BattleComputeBackend,
    checkpoint: Callable[[], None] | None,
) -> list[dict[str, Any]]:
    if checkpoint:
        checkpoint()
    results = backend.compute_batch("hit_state_v1", ({**inputs, "kind": kind},),
                                    checkpoint=checkpoint)
    if len(results) != 1 or not isinstance(results[0].get("states"), list):
        raise ValueError("invalid_hit_state_result")
    rows = results[0]["states"]
    if not all(isinstance(row, dict) and isinstance(row.get("event_id"), str) for row in rows):
        raise ValueError("invalid_hit_state_result")
    return rows


def _dot_basis(row: dict[str, Any]) -> str:
    kind = row["kind"]
    if row["early"]:
        return (
            "普通攻击终段触发三觉剩余伤害结算；当前尚未逐层重放"
            "剩余结算次数，本击不按普通噩梦跳伤估算"
        )
    if kind == "scorch":
        if row["effect"] == "buff_reaction_5_new_1036":
            return (
                "按半场与目标隔离重放残虹浊燃共享状态；本跳先读取结算前层数；"
                "残虹突破被动把上限改为 3；每次浊燃反应先存入 1 层未激活"
                "浊燃；随后战报每实际出现 1 个非浊燃 DOT 跳伤 hit，浊燃同步"
                "增加 1 层并激活整组伤害；中间漏跳不反推，浊燃自身跳伤不递归"
                "加层。该投影由本机历史战报残差回归约束"
            )
        return (
            "普通浊燃最多 1 层；正式触发只刷新整组 15 秒持续时间，"
            "实际周期跳伤不重置下一跳，也不把层数提升为残虹三层"
        )
    return _STATE_BASIS[kind] + (_LOWER_BASIS.get(kind, "") if row["lower"] else "")


def _dot_final_basis(row: dict[str, Any]) -> str:
    if not row["final_enabled"]:
        return "早雾突破 2 被动「可以吃吗？」未启用；DOT 专属最终乘区固定为 1"
    if not row["final_active"]:
        return (
            "早雾突破 2 被动「可以吃吗？」已启用，但本击结算前"
            "尚未确认目标处于浊燃；DOT 专属最终乘区固定为 1"
        )
    kinds = "、".join(_NAMES[kind] for kind in row["active_kinds"])
    recent = row["recent_only"]
    return (
        "早雾突破 2 被动「可以吃吗？」；目标结算前已处于浊燃；"
        f"活跃 DOT 种类为 {kinds}，共 {row['active_dot_kind_count']} 种；"
        "1 + min(种类数 × 25%, 100%)"
        + ("；其中 " + "、".join(_NAMES[kind] for kind in recent)
           + " 由本击前 1.5 秒内近期正式跳伤确认，不据此刷新其完整持续时间"
           if recent else "")
    )


def restore_dot_states(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from src.services.battle_dot_stack_state_service import BattleDotStackState
    results = {}
    for row in rows:
        kind = row.get("kind")
        if (
            kind not in _NAMES or type(row.get("coefficient")) is not int
            or not 0 <= row["coefficient"] <= 10
            or type(row.get("active_dot_kind_count")) is not int
            or not 0 <= row["active_dot_kind_count"] <= 4
            or row.get("confidence") not in ("未解析", "中", "低")
            or not all(type(row.get(flag)) is bool for flag in ("lower", "early", "final_enabled", "final_active"))
            or type(row.get("dot_final_multiplier")) not in (int, float)
            or row["dot_final_multiplier"] not in (1.0, 1.25, 1.5, 1.75, 2.0)
            or not isinstance(row.get("effect"), str)
            or not all(isinstance(row.get(field), list) and all(value in _NAMES for value in row[field])
                       for field in ("active_kinds", "recent_only"))
        ):
            raise ValueError("invalid_hit_state_result")
        label = (
            "三觉：噩梦提前结算" if row["early"] else
            f"{_NAMES[kind]}观测下限" if row["lower"] else
            "浊燃结算前层数" if kind == "scorch" else
            f"{_NAMES[kind]}当前状态" if kind in ("cang_field", "adler_skill") else
            f"{_NAMES[kind]}当前层数"
        )
        results[row["event_id"]] = BattleDotStackState(
            event_id=row["event_id"], coefficient=row["coefficient"], label=label,
            confidence=row["confidence"], evidence_basis=_dot_basis(row),
            active_dot_kind_count=row["active_dot_kind_count"],
            dot_final_multiplier=row["dot_final_multiplier"], dot_final_multiplier_basis=_dot_final_basis(row),
        )
    return results


def restore_q_final_states(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from src.services.battle_zankou_awakening_state_service import ZankouQFinalDamageEvidence
    results = {}
    for row in rows:
        if row.get("branch") not in ("magic", "force") or row.get("multiplier") != 2.5:
            raise ValueError("invalid_hit_state_result")
        branch = row["branch"]
        name = "血宴入梦时" if branch == "magic" else "焚天烬灭舞"
        results[row["event_id"]] = ZankouQFinalDamageEvidence(
            event_id=row["event_id"], multiplier=row["multiplier"],
            evidence_basis=(
                "觉醒二「渊底之吻」蓄焰：覆纹/浊燃触发后，"
                f"本次{name}独立最终伤害 +150%，即 ×2.5"
                + ("；觉醒四「梦魇生花」使血宴分支独立持有并消费资格" if branch == "magic" else "")
            ),
        )
    return results
