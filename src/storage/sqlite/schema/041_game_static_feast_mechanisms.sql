-- 争锋特殊机制保留文案和资源节点原文；关联 Buff 不等于无条件属性加成。
CREATE TABLE feast_mechanism_detail (
 option_id TEXT PRIMARY KEY REFERENCES feast_option(option_id),
 description_zh TEXT NOT NULL, text_key TEXT NOT NULL,
 player_buffs_json TEXT NOT NULL, boss_buffs_json TEXT NOT NULL,
 option_node_text TEXT NOT NULL,
 source_row_id INTEGER NOT NULL REFERENCES source_row(source_row_id),
 text_source_row_id INTEGER NOT NULL REFERENCES source_row(source_row_id)
);
-- 每项机制独立开关，沿用既有 category_ordinal -> option_id 契约，不合并成单选组。
CREATE VIEW feast_all_stage_option AS
 SELECT stage_id,category_ordinal,option_ordinal,category_name_zh,option_id FROM feast_stage_option
 UNION ALL
 SELECT m.stage_id,
  COALESCE((SELECT MAX(s.category_ordinal)+1 FROM feast_stage_option s WHERE s.stage_id=m.stage_id),0)+m.option_ordinal,
  0, m.category_name_zh || ' ' || CAST(m.option_ordinal+1 AS TEXT),m.option_id
 FROM feast_stage_mechanism_option m;
