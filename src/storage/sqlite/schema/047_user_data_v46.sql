-- 账号私有四人队伍；名称仅用于展示，成员按正式角色 ID 和队内位置关联。
CREATE TABLE team (
    team_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    revision INTEGER NOT NULL CHECK (revision > 0),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);
CREATE TABLE team_member (
    team_id TEXT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 0 AND 3),
    character_id INTEGER NOT NULL CHECK (character_id > 0),
    PRIMARY KEY (team_id, ordinal),
    UNIQUE (team_id, character_id)
);
