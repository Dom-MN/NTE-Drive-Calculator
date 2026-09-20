# UI localisation

*English · [简体中文](../../reference/localization.md)*

UI language is provided by `src/i18n`. The language preference is stored alongside the theme in
`config/global_ui_preferences.json`. `zh_CN` (the source language) and `en` are supported.

## Two kinds of text, two mechanisms

Chinese text in the UI splits into two kinds that must be handled differently:

| Kind | Examples | Mechanism | Why |
| --- | --- | --- | --- |
| UI copy | `保存`, `工作台`, `检查更新` | `tr("...")` | Pure display text; the whole string can be replaced |
| Game terms | `攻击力%`, `环合强度`, `「失落光芒」` | `display_term("...")` | Also an OCR match value and a static-database lookup key |

Game terms **must not** be translated in place. They are compared against OCR output from the game
client and used as lookup keys in `data/game_static.sqlite3`; rewriting them breaks scanning, parsing,
scoring and loadouts at once. `display_term` replaces only the display name — the key itself is
unchanged.

## Catalogues

- `locales/en.json` — UI copy, **keyed by the Chinese source string**.
- `locales/glossary.en.json` — game-term display names, split into `stats`/`elements`/… sections.

Keying on the source string means a missing translation degrades to the original Chinese rather than to
a key name, so the catalogue can be filled in gradually and uncovered screens stay usable. The source
language `zh_CN` needs no catalogue.

The English in `glossary.en.json` comes from the game's own string tables, joined to the static database
on `name_text_key` and `attribute_id`, with `_meta.provenance` recording the source of each tier. When
editing, change only the English value — never the Chinese key.

## When it takes effect

Language, like the theme, takes effect **on next launch**: both change how every widget is built, and
there is no live repaint. `src/ui/app.py` calls `set_language()` before importing any UI module so that
module-level `tr()` resolves against the right catalogue. New module-level copy must preserve that
order.

That call happens at **import time**, so merely importing `src.ui.app` activates the language from the
local preference file. Test assertions are written against source-language strings, so
`tools/quality/run_tests.py` sets `NTE_UI_LANGUAGE=zh_CN`; `app.py` reads that environment variable
first, and test results no longer depend on local preferences.

## The first-launch prompt

No `language` key in the preferences file means "never chosen", so the first launch shows a bilingual
chooser once — the reader has not picked a language yet, so both have to be on screen. The answer is
written to the preferences and the question is not asked again. Explicitly choosing `zh_CN` counts as an
answer and does not re-prompt.

The question must be asked before `set_language()`, which means before any UI module is imported.
`src/ui/first_run_language.py` therefore depends only on PySide6 and the preference service and imports
no feature module. It creates the QApplication, and `run_gui()` reuses it via
`QApplication.instance() or ...`.

Tests import `src.ui.app` too, and a dialog there would hang the suite, so the prompt is gated on
`NTE_GUI_LAUNCH` — only `main.py` sets it, immediately before importing the UI. `NTE_UI_LANGUAGE` takes
precedence and skips the prompt entirely.

## Multilingual names that nte-core already supplies

nte-core inventory items carry `names`/`suit_names` (`en`/`ja`/`zh_cn`) alongside a stable
`property_id`, so equipment names, set names and stat names need **no** glossary entry:
`display_localized(names, chinese_fallback)` takes the game data's own name for the active language and
falls back to `display_term` only when the payload has nothing.

Rows from the `vision` source carry Chinese only, so that fallback path must stay. Note that
`_localized()` still returns Chinese — it is the source of filter keys such as `item_type_id`, so do not
change it to resolve by language.

## Resolve display names only at render time

`display_term` is called only when a value is **about to be written into a widget**. Weight lookups,
scoring, sorting and alias normalisation all keep using the Chinese key. Existing call sites: the set
name, main stat and sub stats in `_equip_card`, the attribute rows in `AttributeSummaryPanel`,
`_display_bonus_stat_label`, character names and set names.

One easy trap: the Chinese key carries the percent sign (`攻击力%`) while the English display name does
not (`ATK Bonus`). The percent suffix must therefore **be derived from the Chinese key**, never by
checking whether the display name contains `%`:

```python
main_key = str(main_stat)
main_text = display_term(main_key)
percent_suffix = "%" if "%" in main_key else ""   # from the key, not the display name
```

`_format_panel_value` decides with `bonus_uses_percent(stat)`, which already operates on the key and is
unaffected.

## Long-form game text

Set effects, awakening effects and Arc skill descriptions are original game text and do not enter
`en.json`. The static database stores their string-table keys (`description_text_key` and friends), and
at runtime `display_text(text_table, text_key, chinese_fallback)` looks them up in
`locales/gametext.<lang>.json`.

That file is generated from a locres export by `tools/game_data/build_game_text_locale.py`; only the
generated result is committed, never the locres export itself. `fork_star_level` has no key column, so
it is derived from the `upgradestar_pack_X` → `buff_X_effect` naming convention. Keys are stored and
read in lower case to avoid missing lookups from case differences between the static database and the
string tables.

The English originals keep the same `{n}` placeholders, so refinement-value substitution holds in both
languages.

**Skill names in battle reports are not translated** — the name nte-core reports is shown verbatim.
nte-core's own skill-name table is already a mix (some English, some Chinese, some raw IDs such as
`GA_Shinku_Melee`), and maintaining a local mapping would mean re-exporting the locres for every
character the game adds, which is not worth the cost. Skill **categories** (`E技能`, `普攻` and so on)
are a small fixed set and still go through `tr()`.

## Singular and plural

Chinese does not inflect for number; English does. Where it matters, add a **sibling key** to the
catalogue whose name states which field decides it:

```json
"{count} 个驱动":              "{count} Modules",
"{count} 个驱动::one::count":  "{count} Module"
```

`tr()` switches to the sibling only when that field equals 1. Naming the field is required: these
sentences often carry a second integer (a snapshot or job number), and a rule like "any integer equals
1" would fire on the wrong one.

The catalogue stays a flat string dictionary — `load_catalog` filters the sibling keys out and
`load_plurals` splits them at load time, so `tr()` remains a single dictionary lookup. This covers
English's one/other split only; it is not full CLDR plural handling.

## Adding new copy

1. Wrap it in code with `tr("Chinese source string")`; convert f-strings to
   `tr("...{name}...", name=value)`.
2. Add that Chinese source string as a key in `locales/en.json`.
3. Game terms use `display_term` instead and never enter `en.json`.

`locales/` is a read-only release resource, located by
`src.integrations.bundled_resources.bundled_locales_dir` and shipped with the package by
`build_exe.py`.

## Verifying a game term

The English for a game term **must** come from the game's own string tables; it is never coined from
the Chinese. A semantically reasonable coinage is still wrong: 蚀心 was coined as "Mindrot" when the
official name is **Heartwrench**, and 鸩火 as "Venomfire" when it is **Vile Ash**. Both were in the
string tables at the time — nobody looked.

The string tables are exported by UEExtractor from `pakchunk0-Windows` and its patch as CSV with
columns `key,source,Translation`, where **`source` is the English** (`Translation` is empty). The
export is never committed; its local path belongs in a personal environment, not in the repository.

There are two ways to look a term up. Prefer the first:

1. **Reverse-lookup by ID.** Find the internal ID from the Chinese in `game_static.sqlite3` (for
   example `equipment_attribute.display_name_zh` → `attribute_id`, or the `feast_*` tables →
   `DiyBoss`), then search the CSV's `key` column for that ID. Mode names especially need this:
   争锋赏宴 lives in the `feast_*` tables, whose mode ID is `DiyBoss`, and only
   `ST_UI_N::DiyBoss_Mainform_Name` gives **Hunter's Crucible**.
2. **Search the English, then corroborate.** Having found a candidate, confirm by ID or context that
   it really names that object and is not the same word used elsewhere. 轨外之境 was misread as
   "Off-Rail" from `ST_AbyssBattle`'s `Off-Rail Resonance - Cosmos` — that is the card's adjective.
   The mode name is in `ST_Common::ui_abyss_enter_clone_failed`: **Beyond the Rails**.

Useful namespaces: `ST_Attribute` (attribute names), `<Character>_SkillDes` (skills, DOTs, states and
stacks — `ZankouDot_name`, `ShinkuRage_name`, `EdgarKey_name`), `CharacterTeachGuide::ReactionName_*`
(Cycle reactions), `ST_UI_N` and `ST_GameplayDec` (mode names and rules), `ST_AbyssBattle`,
`ST_AdventureManual`.

Record the outcome. A term joined to a locres key goes in `glossary.en.json` under
`_meta.official_terms`; one that cannot be found goes in `_meta.unverified_terms` — internal computed
fields (the per-element penetrations, base/extra/total ATK/HP/DEF and so on) have no player-facing
official name at all, so they are the project's own wording and are the first to review. Never let a
coinage sit in `official_terms`.

## Short keys are ambiguous

`en.json` is keyed by the source string, so a one- or two-character key collides across contexts:
`"中"` is already taken by another fragment meaning `"of"`, so translating the confidence value `中`
as a bare key would render High / of / Low. Values like these are translated at the render site under
a disambiguated key instead; never add a bare key for them.

## Values that are compared as keys

Some Chinese values in the service layer are compared with `==` or `in`, so translating them changes
behaviour and they must stay Chinese: the confidence levels `高`/`中`/`低`/`未解析` (a dozen sites of
the `confidence == "低"` shape), `err == "任务已取消"` in `_on_exec_error`,
`"已取消更新下载安装包" in message`, and match specs such as
`PASSIVE_ANY_HIT|...,覆纹,weave`. The rule is the same as for game terms: the data stays Chinese and
only the render site substitutes a display name.

## Related tests

`tests/test_i18n.py` pins the fallback behaviour, term mapping and catalogue completeness, and checks
that the theme and language sharing one preference file do not overwrite each other.
