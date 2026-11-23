# 验证争锋多阶段由正式刷怪名单读取，各阶段独立匹配并共享挑战选项。
import sqlite3
from types import SimpleNamespace

from src.services.battle_report.targets.encounter.catalog import BattleEncounterCatalogService
from src.services.battle_report.targets.feast_profiles import feast_target_profiles
from src.services.battle_report.targets.profile_snapshot import battle_target_profile_snapshots
from src.storage.sqlite.catalog.static_feast_roster import feast_difficulty_targets


def test_roster_requires_exact_stage_difficulty_and_marks_unknown_extra_profiles():
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            CREATE TABLE clone_activity_difficulty(clone_id TEXT,difficulty_level INT,spawn_id TEXT);
            CREATE TABLE clone_spawn_member(spawn_id TEXT,wave_ordinal INT,entry_ordinal INT,
                monster_template_name TEXT,monster_template_path TEXT,monster_count INT);
            CREATE TABLE monster_instance_profile_variant(static_table TEXT,monster_id TEXT,
                variant_kind TEXT,threshold_level INT,profile_set TEXT,pack_id TEXT);
            INSERT INTO clone_activity_difficulty VALUES('stage',4,'spawn'),('stage',3,'other');
            INSERT INTO clone_spawn_member VALUES('spawn',0,0,'Phase_A','/Game/Phase_A.Phase_A_C',1),
                ('spawn',0,1,'Phase_B','/Game/Phase_B.Phase_B_C',1),
                ('other',0,0,'Unrelated','/Game/Unrelated.Unrelated_C',1);
            INSERT INTO monster_instance_profile_variant VALUES
                ('monster_static_big_world','phase_a','clone_level',77,'standard','a'),
                ('monster_static_big_world','phase_b','clone_level',77,'standard','b'),
                ('monster_static_big_world','phase_b','clone_level',67,'standard','wrong');
        """)
        profiles = {'a': {'health_base': 100}, 'b': {'health_base': 150}}
        dao = SimpleNamespace(
            _rows=lambda sql, args: [dict(r) for r in connection.execute(sql, args)],
            get_enemy_combat_profile=lambda _set, pack: profiles.get(pack),
        )
        difficulty = {'difficulty_id': 4, 'monster_level': 77, 'boss_name_zh': '首领'}
        rows = feast_difficulty_targets(dao, {'stage_id': 'stage'}, difficulty)
        assert [(r['target_id'], r['pack_id']) for r in rows] == [('Phase_A', 'a'), ('Phase_B', 'b')]
        del profiles['b']
        known = feast_difficulty_targets(dao, {'stage_id': 'stage', 'boss_monster_id': 'Phase_A'}, difficulty)
        assert [r['target_id'] for r in known] == ['Phase_A']
        assert difficulty['unresolved_target_ids'] == ['Phase_B']
        assert not difficulty['roster_complete']
        assert feast_difficulty_targets(dao, {'stage_id': 'stage', 'boss_monster_id': 'Phase_B'}, difficulty) == []


def test_candidate_and_manual_profiles_keep_two_phases_and_apply_options_once():
    members = [{
        'target_id': key, 'name_zh': '首领', 'monster_class_path': key,
        'monster_level': 77, 'profile_set': 'standard', 'pack_id': key,
        'profile': {'health_base': hp, 'health_up': 0, 'health_add': 0,
                    'defense_base': defense, 'resistances': {'chaos': 0.2}},
    } for key, hp, defense in [('Phase_A', 100, 900), ('Phase_B', 150, 1000)]]
    options = [
        {'option_id': 'life', 'effect_kind': 'health_up', 'add_value': 0.5},
        {'option_id': 'resist', 'effect_kind': 'resistance_up', 'damage_type': 'chaos', 'add_value': 0.4},
    ]
    difficulty = {'difficulty_id': 4, 'name_zh': '极难', 'targets': members}
    stage = {'stage_id': 'stage', 'name_zh': '挑战', 'boss_monster_id': 'Phase_A',
             'difficulties': [difficulty], 'option_categories': [
                 {'category_ordinal': index, 'options': [option]} for index, option in enumerate(options)]}
    projected = feast_target_profiles(stage, difficulty, options)
    saved = [p for target in projected for p in battle_target_profile_snapshots(target)]
    assert [p['max_hp'] for p in saved] == [150, 225]
    assert [p['defense_base'] for p in saved] == [900, 1000]
    assert all(abs(p['resistances']['chaos'] - 0.6) < 1e-9 for p in saved)
    candidates = BattleEncounterCatalogService._feast_candidates(SimpleNamespace(list_feast_stages=lambda: [stage]))
    selected = next(c for c in candidates if ('0', 'life') in c.feast_options)
    assert [(t.target_id, t.max_hp) for t in selected.targets] == [('Phase_A', 150), ('Phase_B', 225)]
    assert [t.defense_base for t in selected.targets] == [900, 1000]
    assert members[0]['profile']['health_up'] == 0
    assert feast_target_profiles(stage, {**difficulty, 'targets': []}, options) == []
