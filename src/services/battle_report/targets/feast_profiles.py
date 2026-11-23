# 为争锋的全部阶段目标应用同一次冻结挑战选项，保留各自属性包。
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def feast_target_profiles(
    stage: Mapping[str, Any], difficulty: Mapping[str, Any], options: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    # 旧目录没有 roster 字段时只保留已知主目标；显式空名单表示读取不完整，不能回填。
    sources = difficulty.get("targets", ({
        "target_id": stage.get("boss_monster_id"),
        "monster_class_path": stage.get("boss_monster_id"),
        "name_zh": difficulty.get("boss_name_zh"),
        "monster_level": difficulty.get("monster_level"),
        "profile_set": difficulty.get("profile_set"), "pack_id": difficulty.get("pack_id"),
        "profile": difficulty,
    },))
    result = []
    for source in sources:
        profile = dict(source["profile"])
        resistances = {
            key: float(value.get("resistance_base") or 0.0) if isinstance(value, Mapping) else float(value or 0.0)
            for key, value in (profile.get("resistances") or {}).items()
        }
        for option in options:
            if option.get("effect_kind") == "health_up":
                profile["health_up"] = float(profile.get("health_up") or 0.0) + float(option.get("add_value") or 0.0)
            elif option.get("effect_kind") == "resistance_up" and option.get("damage_type"):
                key = str(option["damage_type"])
                resistances[key] = resistances.get(key, 0.0) + float(option.get("add_value") or 0.0)
        profile["resistances"] = resistances
        result.append({**source, "profile": profile})
    return result
