# 用游戏自带英文字符串表核对术语表，防止自拟译名被当成正式名。
"""Check `glossary.en.json` against the game's own English string tables.

A game term's English must come from the game, not from translating the Chinese.
A coinage that reads well is still wrong, and the failure is silent: nothing in
the test suite can tell `Heartwrench` from `Mindrot`. This compares every term
the glossary claims is official against a locres export and reports the ones
that are not actually there.

The export is game content and is never committed, so this runs manually with
`--locres` rather than as a repository gate. See `docs/reference/localization.md`
for how the export is produced.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GLOSSARY = ROOT / "locales" / "glossary.en.json"
# Sections holding Chinese key -> English display name.
TERM_SECTIONS = ("elements", "reactions", "qualities", "stats", "fork_types",
                 "suits", "characters", "forks", "ui_terms")


def load_string_table(paths: list[Path]) -> tuple[set[str], str]:
    """Every English string the game ships, from one or more UEExtractor CSVs.

    Returns the exact values plus one joined blob, so a term that only ever
    appears inside a longer name can still be evidenced.
    """

    strings: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "source" not in reader.fieldnames:
                raise SystemExit(
                    f"{path.name} has no 'source' column; expected a UEExtractor CSV "
                    f"with key,source,Translation"
                )
            for row in reader:
                value = (row.get("source") or "").strip()
                if value:
                    strings.add(value)
    return strings, "\n".join(strings)


def evidence(term: str, exact: set[str], blob: str) -> str:
    """How strongly the game's own text supports this English name."""

    if term in exact:
        return "exact"
    # "Mental" and "Cycle" are real, but only ever inside "Mental DMG Bonus"
    # and "Cycle Intensity". A whole-word hit is weaker evidence, not absence.
    if re.search(rf"\b{re.escape(term)}\b", blob):
        return "embedded"
    return "absent"


def resolve_inputs(raw: list[str]) -> list[Path]:
    """Accept a directory of exports or individual CSV files."""

    paths: list[Path] = []
    for item in raw:
        path = Path(item).expanduser()
        if path.is_dir():
            paths.extend(
                sorted(
                    candidate for candidate in path.glob("*.csv")
                    # The extractor writes a companion file of lines it could not parse.
                    if not candidate.name.endswith("_skipped_lines.csv")
                )
            )
        elif path.is_file():
            paths.append(path)
        else:
            raise SystemExit(f"not found: {item}")
    if not paths:
        raise SystemExit("no CSV files found in the given path")
    return paths


def glossary_terms(data: dict) -> dict[str, str]:
    """Chinese key -> English display name, across every term section."""

    terms: dict[str, str] = {}
    for section in TERM_SECTIONS:
        body = data.get(section)
        if isinstance(body, dict):
            terms.update(body)
    return terms


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="核对 glossary.en.json 的英文是否出自游戏字符串表",
    )
    parser.add_argument(
        "--locres",
        required=True,
        nargs="+",
        help="UEExtractor 导出的 CSV，或存放它们的目录",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="把未登记来源的术语也算作失败",
    )
    args = parser.parse_args(argv)

    data = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    meta = data.get("_meta", {})
    official = set(meta.get("official_terms") or ())
    unverified = set((meta.get("unverified_terms") or {}).get("terms") or ())
    terms = glossary_terms(data)

    paths = resolve_inputs(args.locres)
    strings, blob = load_string_table(paths)
    print(f"字符串表：{len(strings)} 条，来自 {len(paths)} 个文件")
    print(f"术语表：{len(terms)} 条；official {len(official)}，unverified {len(unverified)}\n")

    graded = {zh: evidence(terms[zh], strings, blob) for zh in terms}
    # An entry claiming to be official whose English the game never uses at all.
    mislabelled = sorted(
        (zh, terms[zh]) for zh in official & set(terms)
        if graded[zh] == "absent"
    )
    # Only ever seen inside a longer name: correct, but not independently attested.
    embedded = sorted(
        (zh, terms[zh]) for zh in official & set(terms)
        if graded[zh] == "embedded"
    )
    # An entry parked as unverified that the game ships verbatim. An embedded
    # hit is not enough to promote on: "Base ATK" occurs inside another name
    # without being the official name for this property.
    promotable = sorted(
        (zh, terms[zh]) for zh in unverified & set(terms)
        if graded[zh] == "exact"
    )
    untracked = sorted(set(terms) - official - unverified)

    if mislabelled:
        print(f"[FAIL] {len(mislabelled)} 条列在 official_terms，但英文不在字符串表中：")
        for zh, en in mislabelled:
            print(f"    {zh}  ->  {en!r}")
        print("    这些要么改用正式名，要么移到 _meta.unverified_terms。\n")
    if embedded:
        print(f"[INFO] {len(embedded)} 条只作为长名称的一部分出现（属正常，非独立词条）：")
        for zh, en in embedded[:10]:
            print(f"    {zh}  ->  {en!r}")
        if len(embedded) > 10:
            print(f"    … 另有 {len(embedded) - 10} 条")
        print()
    if promotable:
        print(f"[INFO] {len(promotable)} 条标为 unverified，但英文确在字符串表中，可提升：")
        for zh, en in promotable:
            print(f"    {zh}  ->  {en!r}")
        print()
    if untracked:
        print(f"[{'FAIL' if args.strict else 'WARN'}] {len(untracked)} 条未登记来源："
              f"{'、'.join(untracked[:12])}"
              f"{' …' if len(untracked) > 12 else ''}\n")

    if not mislabelled and not untracked:
        print("[OK] official_terms 全部能在字符串表中找到")

    failed = bool(mislabelled) or (args.strict and bool(untracked))
    if failed:
        print("提示：整串精确匹配 source 列。正式名嵌在长句里而非单独成条时，"
              "会被误报，请按 docs/reference/localization.md 手工回证后再登记。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
