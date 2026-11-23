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


def test_painted_cards_and_bare_set_names_are_projected():
    # 仓库卡片等自绘控件直接调用 QPainter.drawText，且卡带名去掉了数据库里的「」。
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from src.ui.common import display_projection as projection

    QApplication.instance() or QApplication([])
    base = make_catalog(json.loads((LOCALES / "zh-CN.json").read_text(encoding="utf-8")))
    english = make_catalog(json.loads((LOCALES / "en-US.json").read_text(encoding="utf-8")), base=base)

    def painted(text: str) -> QImage:
        image = QImage(200, 30, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        painter.drawText(QRect(0, 0, 200, 30), Qt.AlignLeft, text)
        painter.end()
        return image

    try:
        projection.set_display_catalog(english, game_terms={"「失落光芒」": "Lost Radiance", "暴击率": "CRIT Rate"})
        assert projection.project("失落光芒") == "Lost Radiance"
        assert painted("暴击率") == painted("CRIT Rate")
    finally:
        projection.set_display_catalog(None)


def test_composed_chips_and_labels_are_projected_piece_by_piece():
    # 卡片词条、觉醒序号、技能类型前缀等由代码拼接，整行无法匹配时逐段投影。
    from src.ui.common import display_projection as projection

    base = make_catalog(json.loads((LOCALES / "zh-CN.json").read_text(encoding="utf-8")))
    english = make_catalog(json.loads((LOCALES / "en-US.json").read_text(encoding="utf-8")), base=base)
    terms = {"「守卫王国」": "Kingdom's Guard", "倾陷强度": "Break Intensity", "防御力": "DEF",
             "攻击力": "ATK", "弥散性的朦白": "Diffusive Haze", "鬼郎丸头锤": "Kiroumaru Headbutt",
             "残虹": "Zankou", "黑羽": "Blackbird"}
    try:
        projection.set_display_catalog(english, game_terms=terms)
        assert projection.project("<b>「守卫王国」</b>") == "<b>Kingdom's Guard</b>"
        assert projection.project("倾陷强度 180") == "Break Intensity 180"
        assert projection.project("防御力% <b>17.5</b>") == "DEF% <b>17.5</b>"
        assert projection.project("1. 弥散性的朦白") == "1. Diffusive Haze"
        assert projection.project("普通攻击：鬼郎丸头锤") == "Basic Attack: Kiroumaru Headbutt"
        assert projection.project("好感十级（攻击力 +5%）") == "Affinity level 10 (ATK +5%)"
        assert projection.project("残虹、黑羽") == "Zankou, Blackbird"
        sentence = base.render("auto.features.static_catalog.menu.module.ac95b79d")
        assert projection.project(f"战斗机制  ·  {sentence}").endswith(
            english.render("auto.features.static_catalog.menu.module.ac95b79d"))
        assert projection.project("没有登记 的 文字") == "没有登记 的 文字"
    finally:
        projection.set_display_catalog(None)
