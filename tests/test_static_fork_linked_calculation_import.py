# 验证直接被弧盘精炼引用的计算目录 Buff 仍进入常驻证据投影。
from __future__ import annotations

import json
import sqlite3
import unittest

from tools.game_data.static_database_buff_imports import BuffImportMixin


NTE_TEST_TIER = "core"


class _Probe(BuffImportMixin):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.available: set[str] = set()

    def _import_buff_modifiers(self, asset_path, semantic_rows) -> None:
        del asset_path, semantic_rows

    def _import_buff_triggers(self, asset_path, semantic_rows) -> None:
        del asset_path, semantic_rows

    def _import_combat_effect_buff_links(self, available) -> None:
        self.available = available


class ForkLinkedCalculationImportTests(unittest.TestCase):
    def test_only_explicitly_linked_calculation_with_modifiers_is_imported(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript("""
            CREATE TABLE fork_star_level(buffs_json TEXT NOT NULL);
            CREATE TABLE combat_blueprint_asset(
                asset_path TEXT, asset_name TEXT, asset_kind TEXT,
                character_id INTEGER, source_file_id INTEGER
            );
            CREATE TABLE combat_blueprint_semantic_property(
                source_asset_path TEXT, property_path TEXT, ordinal INTEGER,
                property_name TEXT, value_json TEXT
            );
            CREATE TABLE buff_definition(
                asset_path TEXT, definition_id TEXT, definition_kind TEXT,
                owner_character_id INTEGER, duration_policy TEXT,
                duration_magnitude_json TEXT, period_json TEXT,
                stacking_type TEXT, stack_limit_count INTEGER,
                source_file_id INTEGER
            );
        """)
        linked = "/Game/Fork/Buff_NewFork_Lv1"
        unlinked = "/Game/Fork/Buff_Unrelated"
        linked_without_modifiers = "/Game/Fork/Calculation_WithoutModifiers"
        connection.execute(
            "INSERT INTO fork_star_level VALUES (?)",
            (json.dumps([
                {"BuffObject": {"AssetPathName": linked + ".0"}},
                {"BuffObject": {"AssetPathName": linked_without_modifiers + ".0"}},
            ]),),
        )
        connection.executemany(
            "INSERT INTO combat_blueprint_asset VALUES (?, ?, 'calculation', NULL, 1)",
            [
                (linked, "Buff_NewFork_Lv1"),
                (unlinked, "Buff_Unrelated"),
                (linked_without_modifiers, "Calculation_WithoutModifiers"),
            ],
        )
        connection.executemany(
            "INSERT INTO combat_blueprint_semantic_property VALUES (?, '$.Modifiers', 0, 'Modifiers', '[]')",
            [(linked,), (unlinked,)],
        )

        probe = _Probe(connection)
        probe._import_buff_definitions()

        self.assertEqual(
            [(linked, "buff")],
            connection.execute(
                "SELECT asset_path, definition_kind FROM buff_definition"
            ).fetchall(),
        )
        self.assertEqual({linked.casefold()}, probe.available)
