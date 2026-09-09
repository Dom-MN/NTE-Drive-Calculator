# 验证用户数据库 v40 收口历史全局优先配置。
"""全局优先移除后的账号偏好迁移回归。"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from src.storage.sqlite.user_data_dao import SCHEMA_VERSION, UserDataDao


def test_v40_migrates_historical_global_priority_to_role_priority() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "legacy_v39.sqlite3"
        with UserDataDao(database, account_id="migration-account") as dao:
            dao.create_optimization_profile(
                "历史配置",
                allocation_strategy="role_priority",
                characters=[],
            )

        connection = sqlite3.connect(database)
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.executescript(
            """
            CREATE TABLE optimization_preference_version_v39 (
                profile_version_id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL
                    REFERENCES optimization_preference_profile(profile_id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL CHECK (version_number >= 1),
                allocation_strategy TEXT NOT NULL
                    CHECK (allocation_strategy IN ('role_priority', 'global_optimal')),
                created_at_utc TEXT NOT NULL,
                UNIQUE (profile_id, version_number)
            );
            INSERT INTO optimization_preference_version_v39
            SELECT * FROM optimization_preference_version;
            DROP TABLE optimization_preference_version;
            ALTER TABLE optimization_preference_version_v39
                RENAME TO optimization_preference_version;
            CREATE INDEX idx_optimization_preference_version_profile
                ON optimization_preference_version(profile_id, version_number DESC);
            UPDATE optimization_preference_version
            SET allocation_strategy = 'global_optimal';
            DELETE FROM schema_migration WHERE version = 40;
            """
        )
        connection.commit()
        connection.close()

        with UserDataDao(database) as migrated:
            strategy = migrated._db().execute(
                "SELECT allocation_strategy FROM optimization_preference_version"
            ).fetchone()[0]
            self_summary = migrated.summary()

        assert strategy == "role_priority"
        assert self_summary["schema_version"] == SCHEMA_VERSION
