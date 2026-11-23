# 验证本分支随包英文补丁可被应用接受、可选，且游戏术语在显示边界按官方英文投影。
"""Fork-only: the bundled English patch and the game-term projection.

Upstream ships Chinese only and leaves game data Chinese under every language.
The fork ships ``assets/locales/en-US.json`` and maps official game text through
``assets/locales/game_terms/en-US.json``; these tests pin both contracts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.domain.localization.catalog import make_catalog
from src.integrations.preferences.locale_files import LocaleFiles, bundled_game_terms

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ROOT / "assets" / "locales"


def test_bundled_english_patch_passes_the_apps_own_acceptance_check():
    base = make_catalog(json.loads((LOCALES / "zh-CN.json").read_text(encoding="utf-8")))
    english = make_catalog(json.loads((LOCALES / "en-US.json").read_text(encoding="utf-8")), base=base)
    assert english.locale == "en-US"
    assert english.render("common.cancel") != base.render("common.cancel")


def test_bundled_english_is_offered_and_a_local_patch_takes_its_place(tmp_path):
    patch_dir = tmp_path / "config" / "locales"
    files = LocaleFiles(LOCALES, patch_dir)
    assert [c.locale for c in files.available()] == ["zh-CN", "en-US"]
    assert files.load("en-US").render("common.cancel") == "Cancel"

    patch_dir.mkdir(parents=True)
    local = json.loads((LOCALES / "en-US.json").read_text(encoding="utf-8"))
    local["messages"]["common.cancel"] = "Abort"
    (patch_dir / "en-US.json").write_text(json.dumps(local, ensure_ascii=False), encoding="utf-8")
    assert [c.locale for c in files.available()] == ["zh-CN", "en-US"]
    assert files.load("en-US").render("common.cancel") == "Abort"


def test_game_terms_come_from_the_game_and_stay_off_in_chinese():
    terms = bundled_game_terms("en-US")
    assert terms["蚀心"] == "Heartwrench"
    assert terms["明音凛"] == "Akane Rin"
    assert bundled_game_terms("zh-CN") == {}


def test_projection_shows_game_names_in_english_and_leaves_unknown_text_alone():
    from src.ui.common import display_projection as projection

    base = make_catalog(json.loads((LOCALES / "zh-CN.json").read_text(encoding="utf-8")))
    english = make_catalog(json.loads((LOCALES / "en-US.json").read_text(encoding="utf-8")), base=base)
    try:
        projection.set_display_catalog(english, excluded=frozenset({"明音凛"}),
                                       game_terms={"明音凛": "Akane Rin"})
        assert projection.project("明音凛") == "Akane Rin"
        assert projection.project("  明音凛") == "  Akane Rin"
        assert projection.project("这一行没有登记") == "这一行没有登记"
        assert projection.project(base.render("common.cancel")) == english.render("common.cancel")
    finally:
        projection.set_display_catalog(None)
