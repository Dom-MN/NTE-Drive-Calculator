# 由发行静态库的字符串表键与游戏导出文本生成“中文原文 → 官方英文”游戏术语映射，供显示边界投影使用。
"""Build ``assets/locales/game_terms/en-US.json``: Chinese game text → the game's own English.

Upstream's display-boundary projection deliberately leaves game data (names,
skills, set effects, awakenings…) in Chinese. The fork translates it, but never
by coining English: every entry comes from the game's own string tables.

Sources, in increasing precedence:

1. ``locales/glossary.en.json`` — hand-verified terms (see ``verify_terms.py``);
2. every static-database column ``X_zh`` that sits next to ``X_text_table`` and
   ``X_text_key``, joined against the locres export by that key;
3. id conventions the database does not store as keys: a monster's manual id
   (``ST_AbyssBattle::<id>``, else ``ST_ActorName::<id without _BP>_Name``) and an
   Arc's description (``ST_Fork::<fork_id>_des``).

Text is matched whole, the way the projection matches. Multi-line text is also
mapped line by line when both languages have the same number of lines, and the
game's inline ``<tag>…</>`` markup is mapped both with and without the tags.

The locres export is game content and is never committed; only the generated
map is. Usage::

    python tools/i18n/build_game_terms.py \\
        --locres path/to/game_pakchunk0-Windows.csv \\
        --locres path/to/game_pakchunk0-Windows_0_P.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data" / "game_static.sqlite3"
GLOSSARY = ROOT / "locales" / "glossary.en.json"
OUTPUT = ROOT / "assets" / "locales" / "game_terms" / "en-US.json"
_MARKUP = re.compile(r"<[^<>]*>")
_CJK = re.compile(r"[一-鿿]")


def load_locres(paths: list[Path]) -> dict[str, str]:
    """Merge exports, lower-casing keys; later files (patch chunks) win."""
    merged: dict[str, str] = {}
    for path in paths:
        with io.open(path, encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                text = (row.get("source") or "").strip()
                if text:
                    merged[row["key"].lower()] = text
    return merged


def _namespace(text_table: object) -> str:
    return str(text_table or "").rsplit(".", 1)[-1]


def _clean(text: str) -> str:
    return _MARKUP.sub("", text.replace("\\n", "\n").replace("\r\n", "\n")).strip()


def _add(terms: dict[str, str], chinese: object, english: str | None) -> None:
    if not english or not isinstance(chinese, str) or not _CJK.search(chinese):
        return
    english = english.replace("\\n", "\n").replace("\r\n", "\n")
    chinese = chinese.replace("\r\n", "\n")
    pairs = [(chinese.strip(), english.strip()), (_clean(chinese), _clean(english))]
    for zh, en in pairs:
        if not zh or not en or "{" in zh:
            continue  # templated text is filled with numbers at display time; no whole-line match
        terms[zh] = en
        zh_lines, en_lines = zh.split("\n"), en.split("\n")
        if len(zh_lines) > 1 and len(zh_lines) == len(en_lines):
            for zh_line, en_line in zip(zh_lines, en_lines):
                if _CJK.search(zh_line) and en_line.strip():
                    terms.setdefault(zh_line.strip(), en_line.strip())


def keyed_columns(connection: sqlite3.Connection):
    """Yield (table, chinese column, text-table column, key column) for every keyed text column."""
    for (table,) in connection.execute("select name from sqlite_master where type='table'"):
        columns = [row[1] for row in connection.execute(f'pragma table_info("{table}")')]
        for column in columns:
            match = re.fullmatch(r"(.*)_text_key", column)
            if not match:
                continue
            prefix = match.group(1)
            chinese = next((name for name in (f"{prefix}_zh", prefix) if name in columns), None)
            text_table = f"{prefix}_text_table" if f"{prefix}_text_table" in columns else None
            if chinese and text_table:
                yield table, chinese, text_table, column


def build(locres: dict[str, str]) -> dict[str, str]:
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    terms: dict[str, str] = {}
    for section, entries in glossary.items():
        if section != "_meta":
            for chinese, english in entries.items():
                _add(terms, chinese, english)
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    try:
        for table, chinese, text_table, key in keyed_columns(connection):
            query = f'select "{chinese}", "{text_table}", "{key}" from "{table}" where "{key}" is not null'
            for zh, namespace, text_key in connection.execute(query):
                _add(terms, zh, locres.get(f"{_namespace(namespace)}::{text_key}".lower()))
        for manual_id, zh in connection.execute("select monster_manual_id, name_zh from monster_catalog"):
            stem = str(manual_id).removesuffix("_BP").removesuffix("_bp")
            english = (locres.get(f"st_abyssbattle::{manual_id}".lower())
                       or locres.get(f"st_actorname::{stem}_name".lower()))
            _add(terms, zh, english)
        for fork_id, description in connection.execute("select fork_id, description_zh from fork_item"):
            _add(terms, description, locres.get(f"st_fork::{fork_id}_des".lower()))
    finally:
        connection.close()
    return dict(sorted(terms.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locres", action="append", required=True, type=Path)
    arguments = parser.parse_args()
    terms = build(load_locres(arguments.locres))
    # Bytes, not write_text: on Windows the latter writes CRLF and the repository is LF-only.
    OUTPUT.write_bytes((json.dumps(terms, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}: {len(terms)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
