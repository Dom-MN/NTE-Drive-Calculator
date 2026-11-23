# 导入争锋特殊机制的解包节点与中文文案，不把条件效果投影成常驻加成。
import json

from tools.game_data.static_database_build_support import StaticDatabaseError, asset_path


def option_score(node):
    """只兼容来源已确认的 Score/score；缺失保持未知，冲突或非法积分拒绝导入。"""
    if 'Score' in node and 'score' in node and node['Score'] != node['score']:
        raise StaticDatabaseError('争锋 Score / score 字段冲突')
    value = node.get('score', node.get('Score'))
    if value is not None and (type(value) is not int or value < 0):
        raise StaticDatabaseError('争锋积分不是非负整数')
    return value


def import_mechanisms(builder):
    options = builder.rows['feast_options']
    texts = builder.rows['feast_mechanism_text']
    for option_id, option in options.items():
        if option.get('OptionType') != 'EDiyBossOptionType::MechanismBuff':
            continue
        row = option.get('OptionNode')
        if not isinstance(row, dict):
            raise StaticDatabaseError(f'争锋机制节点缺失，请核对解包使用的补丁全局索引：{option_id}')
        reference = row.get('OptionDesc') or {}
        if reference.get('TableId') != '/Game/Text/ST_UI_hpy.ST_UI_hpy':
            raise StaticDatabaseError(f'争锋机制文本来源未支持：{option_id}')
        key = reference.get('Key')
        description = texts.get(key)
        score = option_score(row)
        if not isinstance(description, str) or not description.strip() or type(score) is not int or score < 0:
            raise StaticDatabaseError(f'争锋机制文案或积分缺失：{option_id}')
        buffs = {}
        for field in ('PlayerBuffs', 'BossBuffs'):
            values = row.get(field)
            if not isinstance(values, list):
                raise StaticDatabaseError(f'争锋机制 Buff 列表缺失：{option_id}/{field}')
            paths = [asset_path(value) for value in values]
            if any(not isinstance(p, str) or not p.startswith('/Game/') for p in paths):
                raise StaticDatabaseError(f'争锋机制 Buff 关联无效：{option_id}/{field}')
            buffs[field] = paths
        builder.connection.execute(
            "UPDATE feast_option SET score=?,effect_kind='mechanism' WHERE option_id=?", (score, option_id),
        )
        builder.connection.execute('INSERT INTO feast_mechanism_detail VALUES (?,?,?,?,?,?,?,?)', (
            option_id, description, key, json.dumps(buffs['PlayerBuffs']), json.dumps(buffs['BossBuffs']),
            json.dumps(row, ensure_ascii=False, sort_keys=True), builder.source_row_id('feast_options', option_id),
            builder.source_row_id('feast_mechanism_text', key),
        ))
