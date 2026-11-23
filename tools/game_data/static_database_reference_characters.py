# 将显式排除计算的角色已知资料保存在独立只读参考表。
from __future__ import annotations

from tools.game_data.static_database_build_support import canonical_json, text_parts


def import_reference_character(builder, key, row, reason):
    """仅消费同版来源；占位文本保留，缺项不生成属性或可计算角色。"""
    name = text_parts(row.get('ItemName'))[0]
    element = row.get('ElementData') or {}
    element_labels = {'CHAOS': '暗', 'COSMOS': '光', 'NATURE': '灵',
                      'INCANTATION': '咒', 'LAKSHANA': '相', 'PSYCHE': '魂'}
    token = str(element.get('CharacterElementType') or '').rsplit('_', 1)[-1]
    sections = [{'title': '已知身份', 'fields': [
        ['名称', name or '未提供'], ['角色 ID', key],
        ['属性', element_labels.get(token, token or '未提供')],
        ['说明', text_parts(row.get('Description'))[0] or '未提供'],
    ]}]
    abilities = builder.rows['character_abilities'].get(key, {}).get('CharacterAbilityList', [])
    for entry in abilities:
        ability_id = entry.get('Key')
        if not ability_id:
            continue
        tip = builder.rows['gameplay_ability_tips'].get(ability_id, {})
        # 按表内实际 FText 字段展示；不从资源名或相似角色补写技能说明。
        fields = [['技能 ID', ability_id]]
        def visit(value):
            if isinstance(value, dict):
                if 'TableId' in value or 'SourceString' in value:
                    text = text_parts(value)[0]
                    if text:
                        fields.append([str(value.get('Key') or '说明'), text])
                    return
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(tip)
        sections.append({'title': '技能参考', 'fields': fields})
    awakening = builder.awaken_rows.get(int(key))
    if awakening:
        for effect in awakening[0].get('AwakenEffectStructList', []):
            sections.append({'title': text_parts(effect.get('Title'))[0] or str(effect.get('EffectID')),
                             'fields': [['觉醒／共鸣说明', text_parts(effect.get('Desc'))[0] or '未提供']]})
    builder.connection.execute('INSERT INTO reference_character VALUES (?,?,?,?,?)',
                               (int(key), name or key, reason, canonical_json(sections),
                                builder.source_row_id('character', key)))
