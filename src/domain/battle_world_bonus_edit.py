# 校验战报修改副本显式保存的家具加成，不读取或改写账号环境。
from collections.abc import Mapping
from math import isfinite


def world_bonus_edit_stats(value):
    if not isinstance(value, Mapping) or set(value) != {"AtkAdd", "CritDamageBase"}:
        raise ValueError("战报家具修改副本必须完整包含攻击力和暴击伤害")
    rows = []
    for ordinal, (key, label, maximum) in enumerate((
        ("AtkAdd", "攻击力", 20.0), ("CritDamageBase", "暴击伤害", 0.04),
    )):
        number = value[key]
        if type(number) not in (int, float) or not isfinite(number) or not 0 <= number <= maximum:
            raise ValueError("战报家具修改副本数值超出正式范围")
        rows.append({"source_group": "world_bonus", "property_id": key,
                     "display_name": label, "value": float(number),
                     "is_percent": key == "CritDamageBase", "ordinal": ordinal})
    return rows
