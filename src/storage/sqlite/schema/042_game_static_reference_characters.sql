-- 未完整角色只用于资料展示，不关联可计算 character 集合。
CREATE TABLE reference_character (
 character_id INTEGER PRIMARY KEY,
 name_zh TEXT NOT NULL,
 reason_zh TEXT NOT NULL,
 sections_json TEXT NOT NULL,
 source_row_id INTEGER NOT NULL REFERENCES source_row(source_row_id)
);
