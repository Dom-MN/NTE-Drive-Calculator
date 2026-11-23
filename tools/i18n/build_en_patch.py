# 由译文记忆与游戏术语表为上游中文目录生成英文语言补丁，并保留已人工校订的条目。
"""Build the fork's English language patch, ``assets/locales/en-US.json``.

The upstream catalogue ``assets/locales/zh-CN.json`` is the only base: every key
and every named parameter comes from it. For each key this tool fills English,
in order of precedence:

1. an entry already in ``en-US.json`` that still validates (hand translations
   are never overwritten);
2. the translation memory ``locales/translation_memory.en.json``, keyed by the
   Chinese source text — the fork's English from before upstream adopted
   catalogue keys — when the source text matches exactly;
3. the same memory when the text matches but the placeholder names differ,
   renaming the English placeholders by position;
4. the game-term glossary, for a catalogue entry that is a bare game term.

An entry that would fail the catalogue's own checks (a format spec such as
``{count:,}``, a stray brace, a parameter mismatch) is left out, so it falls
back to Chinese rather than breaking the whole patch. Keys that drop out of the
catalogue upstream are removed. Run after every upstream sync::

    python tools/i18n/build_en_patch.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from string import Formatter

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.localization.catalog import CatalogError, make_catalog, parameter_names  # noqa: E402

BASE = ROOT / "assets" / "locales" / "zh-CN.json"
PATCH = ROOT / "assets" / "locales" / "en-US.json"
MEMORY = ROOT / "locales" / "translation_memory.en.json"
GLOSSARY = ROOT / "locales" / "glossary.en.json"
_FIELD = re.compile(r"\{([^{}]*)\}")


def _fields(text: str) -> list[str]:
    """Placeholder names in order of appearance; None when the text is not a valid template."""
    try:
        return [field for _literal, field, _spec, _conv in Formatter().parse(text) if field is not None]
    except ValueError:
        return []


def _shape(text: str) -> str:
    return _FIELD.sub("{}", text)


def _rename(english: str, source_fields: list[str], target_fields: list[str]) -> str | None:
    """Rename the memory's placeholders to the catalogue's, matched by position."""
    if len(source_fields) != len(target_fields):
        return None
    mapping = dict(zip(source_fields, target_fields))
    try:
        parts = list(Formatter().parse(english))
    except ValueError:
        return None
    out = []
    for literal, field, spec, conversion in parts:
        out.append(literal.replace("{", "{{").replace("}", "}}"))
        if field is None:
            continue
        if spec or conversion or field not in mapping:
            return None
        out.append("{" + mapping[field] + "}")
    return "".join(out)


def _valid(text: str, expected: frozenset[str]) -> bool:
    try:
        return parameter_names(text) == expected and len(text) <= 4096
    except CatalogError:
        return False


def build(check_only: bool = False) -> int:
    base_payload = json.loads(BASE.read_text(encoding="utf-8"))
    base = base_payload["messages"]
    memory = json.loads(MEMORY.read_text(encoding="utf-8"))
    glossary_raw = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    glossary = {k: v for section, entries in glossary_raw.items() if section != "_meta"
                for k, v in entries.items() if isinstance(v, str)}
    existing = {}
    if PATCH.exists():
        existing = json.loads(PATCH.read_text(encoding="utf-8")).get("messages", {})

    by_shape: dict[str, tuple[str, str]] = {}
    for source, english in memory.items():
        if isinstance(english, str) and "::" not in source:
            by_shape.setdefault(_shape(source), (source, english))

    messages: dict[str, str] = {}
    counts = {"kept": 0, "memory": 0, "renamed": 0, "glossary": 0}
    for key, chinese in base.items():
        expected = parameter_names(chinese)
        candidate, origin = None, None
        if key in existing and _valid(existing[key], expected):
            candidate, origin = existing[key], "kept"
        elif chinese in memory and _valid(memory[chinese], expected):
            candidate, origin = memory[chinese], "memory"
        elif _shape(chinese) in by_shape:
            source, english = by_shape[_shape(chinese)]
            renamed = _rename(english, _fields(source), _fields(chinese))
            if renamed is not None and _valid(renamed, expected):
                candidate, origin = renamed, "renamed"
        elif chinese in glossary and not expected:
            candidate, origin = glossary[chinese], "glossary"
        if candidate is not None:
            messages[key] = candidate
            counts[origin] += 1

    payload = {
        "format_version": base_payload["format_version"],
        "catalog_id": base_payload["catalog_id"],
        "locale": "en-US",
        "display_name": "English",
        "messages": dict(sorted(messages.items())),
    }
    make_catalog(payload, base=make_catalog(base_payload))  # the app's own acceptance check
    total = len(base)
    print(f"en-US: {len(messages)}/{total} keys ({len(messages) / total:.0%}); " +
          ", ".join(f"{name} {value}" for name, value in counts.items()))
    dropped = sorted(set(existing) - set(base))
    if dropped:
        print(f"removed {len(dropped)} keys no longer in the base catalogue")
    if check_only:
        return 0 if existing == payload["messages"] else 1
    PATCH.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if the patch is stale")
    return build(check_only=parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
