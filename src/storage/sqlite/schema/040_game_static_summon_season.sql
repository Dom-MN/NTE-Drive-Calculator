-- 静态库 v40：保留召唤物伤害的独立赛季条件，禁止投影为全队通用增伤。
ALTER TABLE outer_realm_season_buff_component RENAME TO outer_realm_season_buff_component_v39;
CREATE TABLE outer_realm_season_buff_component (
    level_config_id TEXT NOT NULL REFERENCES outer_realm_season_buff(level_config_id) ON DELETE CASCADE,
    component_ordinal INTEGER NOT NULL CHECK (component_ordinal >= 0),
    trigger_kind TEXT NOT NULL CHECK (trigger_kind IN (
        'whole_battle', 'corruption_damage_stack', 'while_target_toppled',
        'whole_battle_qte', 'observed_recipient_effect', 'whole_battle_summon')),
    property_id TEXT NOT NULL,
    property_value REAL NOT NULL,
    duration_seconds REAL CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    trigger_cooldown_seconds REAL CHECK (trigger_cooldown_seconds IS NULL OR trigger_cooldown_seconds >= 0),
    stack_limit_count INTEGER NOT NULL DEFAULT 1 CHECK (stack_limit_count >= 1),
    curve_id TEXT NOT NULL,
    curve_source_row_id INTEGER NOT NULL REFERENCES source_row(source_row_id),
    effect_asset_path TEXT,
    PRIMARY KEY (level_config_id, component_ordinal)
);
INSERT INTO outer_realm_season_buff_component SELECT * FROM outer_realm_season_buff_component_v39;
DROP TABLE outer_realm_season_buff_component_v39;
CREATE INDEX idx_outer_realm_buff_component_trigger ON outer_realm_season_buff_component(level_config_id, trigger_kind);

-- 新争锋导出存在未知机制节点，分数保持 NULL；多预览目标和机制选择分别保留。
CREATE TABLE feast_option_v40 (
 option_id TEXT PRIMARY KEY, option_type TEXT NOT NULL, effect_kind TEXT NOT NULL,
 damage_type TEXT, add_value REAL, limit_seconds INTEGER, score INTEGER,
 buff_asset_path TEXT, source_row_id INTEGER NOT NULL REFERENCES source_row(source_row_id));
INSERT INTO feast_option_v40 SELECT * FROM feast_option;
CREATE TABLE feast_stage_option_v40 (
 stage_id TEXT NOT NULL REFERENCES feast_stage(stage_id),
 category_ordinal INTEGER NOT NULL CHECK(category_ordinal>=0),
 option_ordinal INTEGER NOT NULL CHECK(option_ordinal>=0), category_name_zh TEXT NOT NULL,
 option_id TEXT NOT NULL REFERENCES feast_option_v40(option_id),
 PRIMARY KEY(stage_id,category_ordinal,option_ordinal));
INSERT INTO feast_stage_option_v40 SELECT * FROM feast_stage_option;
DROP TABLE feast_stage_option;
DROP TABLE feast_option;
ALTER TABLE feast_option_v40 RENAME TO feast_option;
ALTER TABLE feast_stage_option_v40 RENAME TO feast_stage_option;
CREATE TABLE feast_stage_member (
 stage_id TEXT NOT NULL REFERENCES feast_stage(stage_id), member_ordinal INTEGER NOT NULL,
 monster_id TEXT, preview_asset_path TEXT NOT NULL,
 PRIMARY KEY(stage_id,member_ordinal));
CREATE TABLE feast_stage_mechanism_option (
 stage_id TEXT NOT NULL REFERENCES feast_stage(stage_id), option_ordinal INTEGER NOT NULL,
 option_id TEXT NOT NULL REFERENCES feast_option(option_id), category_name_zh TEXT,
 score_limit INTEGER, PRIMARY KEY(stage_id,option_ordinal));
