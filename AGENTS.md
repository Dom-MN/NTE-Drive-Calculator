# NTE Drive Calc repository development contract

This file keeps only the current product hard contracts, architectural boundaries and engineering
gates. Feature detail is in `docs/features.md`, external capabilities in `docs/integrations.md`,
unfinished capabilities in `docs/roadmap.md`, formulas and fields in `docs/reference/`, and
real-hardware acceptance in `docs/validation/windows.md`. This file must stay publishable: never
record an account, token, CDK, private address, real UID, absolute user path, complete packet capture,
full OCR text, screenshot or unredacted log.

> This is a **fork** of `hxwd94666/NTE-Drive-Calculator` that adds Simplified Chinese / English
> localisation. Upstream declined the localisation, so the fork is maintained indefinitely. Section 11
> defines how to take upstream changes; sections 1–10 mirror upstream's contract in English.

## 1. Source of truth and documentation maintenance

On conflict, prefer in order: passing public behaviour tests and database constraints, this file, the
architecture/feature/integration documents, public contracts, and the current UI. Unfinished
capabilities go only in the roadmap; current capabilities only in the feature document; one fact keeps
one authoritative location and every other document references it by link.

Updating a document means overwriting the relevant section: delete stale conclusions, duplicated
explanations, phase-by-phase logs and completed plans, and never append a "changes in this revision"
style patch paragraph at the end. Documents must not become an archive for implementation detail,
personal environments or test output.

## 2. Development and definition of done

Before starting, establish which data domain the inputs and outputs belong to, which account,
generation, snapshot, static dataset, config version, `slot_id`, lock snapshot and cancellation token
are frozen, and how failure rollback and external side-effect confirmation work. Product semantic
changes are completed in this order:

```text
public behaviour tests → contract/docs → Domain/Service → DAO/Integration
→ Controller/UI → migrate callers and delete the old entry point → targeted verification
→ core/full plus static checks
```

Reproduce a defect before making the smallest business fix. Old and new semantics must not dual-read,
dual-write or be branched in the UI for any length of time. A change to schema, payload, error codes or
an external protocol must cover a new database, upgrading an old one, failure rollback and retry after
repair. Done requires behaviour/lifecycle tests, current documentation, no new compatibility façade or
cross-feature private call, and newly introduced failures reported separately from existing ones.

## 3. Technical baseline and layering

- Windows 10/11, Python 3.11, PySide6; entry point `main.py`, composition root `src/ui/app.py`.
- Dependencies come only from `pyproject.toml` and `uv.lock`; the version only from
  `src/app/version.py::__version__`.
- Quality entry point is `tools/quality/run_tests.py`: `core` covers the critical boundaries, `full`
  runs the complete discovery.

```text
UI Page/View → Controller → Application Service → Domain/Optimizer or DAO/Integration
```

UI owns only widgets and discardable display state; Controller owns only workers, cancellation and
projection; Service freezes the request and orchestrates transactions; Domain/Optimizer perform
immutable pure computation; DAO exclusively owns schema/SQL/transactions; Integration exclusively owns
processes, files, protocols, OCR and input. Service, Domain, DAO and Integration must not import
`src.features` or look up MainWindow. `AppContext`, `EquipmentPresentation` and the global hotkeys are
created only in the composition root and injected explicitly.

Cross-layer relationships always use the real `character_id`, `item_id`, `suit_id`, `shape_id`,
`property_id`, equipment UID and `slot_id`; Chinese names and `slot_name` are display only. Navigation
uses key/`parent_key`, never a page number or a scan of MainWindow fields to locate a feature.

## 4. Context, async work and data domains

`AppContext` is the single composition root for paths and account state: `ApplicationPaths` owns release
resources and application paths, `AccountContext` owns the current account, and `generation` identifies
the account generation. Account switching always follows: stop account tasks → replace the context and
increment the generation → rebuild narrow services → clear page caches → resume the services allowed to
run automatically.

A long task freezes the account, generation, paths, snapshot, static dataset, config and target slot at
creation; it re-checks them before callbacks and writes, and stale results are discarded silently.
Cancellation only invalidates the current token; exit closes the owner through the public `close`/`stop`
and never mutates worker private state.

| Data domain | Path / responsibility |
| --- | --- |
| Release static | `data/game_static.sqlite3`; official catalogue, growth, skills, enemies, offline weights and graduation templates; read-only at runtime. |
| Application global | `config/global_ui_preferences.json`, `config/workshop_weight_template.json`; theme, interface language and the public workshop template. |
| Account private | `accounts/<account_id>/user_data.sqlite3`; snapshots, characters, preferences, slots, plans, locks, jobs, battle reports. |
| Public shared | `data/app_shared.sqlite3`; legacy migration data only, never overriding official static facts. |

Read priority is the account's explicit config → data that permits sharing → release defaults. Theme and
interface language are application-global; a new install defaults to the black theme, and only an
explicit legacy theme is migrated. The current release static schema is v31, with code and candidate at
v32; static and account migrations are append-only and a published migration never changes meaning.

## 5. Static database, snapshots and source capability

The static database is only ever generated as a candidate under `build/` by `tools/game_data`. After
post-processing such as graduation templates, only `tools/game_data/promote_static_release.py` may
promote it, reading local configuration outside the repository and atomically verifying source hashes,
schema/importer, foreign keys, integrity, and the database against the manifest; overwriting `data/`
directly or bulk-copying unpacked Content is forbidden. An importer that changes normalised output must
increment the importer version. Unconditional permanent Arc attributes are projected automatically from
the real static relationships; conditional effects continue to use the combat state path.

Inventory snapshots are immutable and the current pointer only points at a complete stable snapshot.
Downstream work resolves `snapshot_id` once at the start and does not follow the latest value while
running; a plan is always read against its own `source_snapshot_id`. The stabiliser judges stability by a
complete content fingerprint plus a quiet window and does not retain the historical maximum count. A
runtime delta may only overlay the state of UIDs already known in a native full snapshot; a partial event
must not add items, replace the set or advance the pointer.

Source capability is decided through the public helper: `nte_core` provides real UIDs, character
instances and reliable equipment state; a vision source supports analysis and regular mouse assembly but
must not enter fast assembly or fake reliable character ownership.

## 6. Calculation, characters and loadouts

A calculation freezes the account, generation, snapshot, static dataset, character order/equal-priority
groups, target slot, locks and character configuration, and produces an immutable
`WeightedAllocationPreview`. Saving consumes only that preview and re-checks the frozen boundaries
before saving, never reading "the latest state" to fill gaps. Candidate construction removes locked real
UIDs first; sets, main stats, rarity and the blacklist use one shared contract; real UIDs already
assigned to an earlier character do not enter later candidates. Virtual placeholders score 0 and can be
neither locked nor fast-assembled. Character drag ordering and the `=`/`>` semantics are defined by the
shared priority-group tests and must not be rewritten in the UI.

The only source of the NTE Workshop weight equipment formulas is `ScoringEngine.calculate_drive_score`
and `ScoringEngine.calculate_cartridge_score`. Calculation, in-game loadouts, card display, rewind and
official character base scoring may only compute through that engine or a formula-free adapter over it,
and must never copy the formula. A saved plan's complete `assignment_scores` is the frozen fact behind
single-item cards, grades, cumulative scores and replacement deltas; only an older plan missing that
field may be recomputed through the same engine. The replacement dialog may sort and display by the
current character's direct-damage margin weights, but a saved plan must write frozen per-item scores
under the same workshop scoring contract.

Official characters default to the static graduation template, with explicit account configuration
taking precedence. The effective character panel uniformly consumes level/ascension, Arc
level/ascension, unconditional permanent attributes, affinity 10, furniture bonuses and specific
awakening and skill levels. Base CRIT Rate is 5% and base CRIT DMG is 54%; the character CRIT cap
subtracts the signature weapon, unconditional Arc CRIT and affinity CRIT, and a manual cap may only
tighten it; global optimum does not consume the CRIT minimum/cap from character management. Conditional
Arc effects do not enter the permanent panel, the graduation rate or allocation scoring.

`slot_id` is the stable identity of one character's several plans and `slot_name` is display only. The
current slot plan is saved against its own source snapshot; only different characters' current slots
referencing the same real UID is a conflict. A lock is an account-scoped plan lock, not the game's lock
RPC; a locked plan must not be deleted, overwritten, archived, or lend out its UIDs.
`EquipmentPresentation` is the single shared display component for equipment cards, scores, gains and
differences.

## 7. Scanning, warehouse, assembly and rewind

The warehouse reads a pinned snapshot; a state operation builds a plan first, the Integration executes
it, and a later full snapshot or an official scoped event confirms it. A vision scan commits only a
complete result in one transaction; cancellation, an exception or a count mismatch commits nothing
half-finished. Scanning, appraisal, rewind and automatic assembly all use the application-level stop
key, and every stop path must release input state.

Fast assembly consumes only native real UIDs, character instances and saved slots; in-game automatic
assembly may consume the vision projection. Both freeze their context and token and block account
switching while running. Rewind recommendation reads only the pinned inventory, the selected characters'
current saved plans and their frozen per-item scores; only an explicit "generate recommendation" solves,
using the score shortfall and the user's chosen balanced/focused strategy; rarity and the eight-slot
plan are frozen before execution.

## 8. Battle reports

Battle-report capture saves only the Core's summary, record, axis and raw per-hit data; it must never
guess crits, buffs/debuffs, shields, healing, the complete team, enemy instances or the scene from an
aggregate summary. When capture ends it materialises a copy once from the then-latest complete native
inventory and effective character growth, and does not read the active loadout. The original
character/equipment snapshot is immutable; a battle-report edit copy is a single-match account-private
copy whose equipment override copies the complete calculated equipment and keeps no active pointer. The
copy only takes part in fixed-axis per-hit damage replay and counterfactual margin calculation, and never
rewrites the measured damage, DPS, timeline or original facts on the battle-report main page.

Environment inference, user-confirmed environment, enemy profiling, buff auditing and margin calculation
are versioned derived results and must stay separate from the Core's original facts and confidence. A
confirmed environment stores the player-facing Chinese environment name; the original class path may
serve only as an internal matching field or diagnostic and must never be a main-interface label. Unknown
must never be disguised as zero, a multiplier of one, or a complete gain. A capture stop exceeding 12
seconds must abort that Core run, discard unfinished staging and enter error; an empty battle report must
not wait indefinitely for a final axis. While battle reports are still iterating, a failing
battle-report regression must be listed separately and never rewritten as a general pass.

## 9. External integrations, UI, localisation and logging

nte-core, Npcap, mods, OCR, mouse/gamepad, binaries and game input are Integrations. Before promoting a
third-party component, record the upstream version, commit, licence and SHA-256 and complete protocol,
packaging and real Windows verification; local binaries in the root directory are never committed.

New dialogs use `src.app.window_geometry`, bounded by the current screen's available area and centred
relative to the owner/screen, covering mixed DPI; custom colours, selected states and widget states must
work in the original, black and white themes alike. Logs record lifecycle and diagnostics per layer and
never record a complete RPC, UID list, account display name, absolute path, full OCR text, screenshot,
CDK, token or recoverable payload.

All new or modified UI copy goes through `src/i18n`, distinguishing two kinds of text:

- **UI copy** uses `tr("Chinese source string")`, with f-strings rewritten as
  `tr("...{name}...", name=value)`, and that Chinese source string added as a key in `locales/en.json`.
  The catalogue is keyed by the source string, so a missing translation degrades to Chinese rather than
  to a key name.
- **Game terms** use `display_term()`. The Chinese key is simultaneously an OCR match value and a
  `game_static.sqlite3` lookup key, so translating or rewriting it in place is forbidden; the display
  name is substituted only when it is about to be written into a widget, while weights, scoring, sorting,
  filter keys and state checks keep using the Chinese key. The percent suffix is derived from the Chinese
  key, never by testing whether the display name contains `%`.
- Fields for which nte-core already supplies `names`/`suit_names` (`en`/`ja`/`zh_cn`) use
  `display_localized()` instead of a glossary entry.

Logging text stays Chinese: `logger.*`, `log_event` and `operation_scope(message=)` never go through
`tr()`. Exception messages in Services and Integrations that **are shown to a user** go through `tr()`;
pure argument contracts (the `timeout 必须大于 0` kind) stay Chinese.

On first launch — no `language` key in the preferences file — a bilingual chooser is shown once and the
answer recorded. The question is asked before `set_language()` and is gated on `NTE_GUI_LAUNCH`, which
only `main.py` sets: tests import `src.ui.app`, and a dialog there would hang the suite. The language is
activated while `src/ui/app.py` is imported, so module-level copy must preserve the order
"`set_language()` first, then import UI modules". Tests pin the source language with `NTE_UI_LANGUAGE`.
English singular forms use a sibling key `"<source>::one::<field>"` with the field named, so a second
integer in the same sentence cannot trigger it. Details are in `docs/reference/localization.md`.

## 10. Code, test and release gates

- A new or modified Python file under `src/`, `tools/` or `tests/` must not exceed 800 lines; an existing
  oversized file may only be split or shrunk when touched.
- A new Python file's first line must be a Chinese summary comment; a new `type: ignore` must carry the
  error code and a reason.
- Ruff `E9/F63/F7/F821/F401` is a hard gate; a new dependency updates `pyproject.toml` and `uv.lock`
  together.
- New UI copy must pass `tests.test_i18n` — `test_every_tr_key_resolves` fails on a `tr()` key missing
  from `locales/en.json` — and `python tools/quality/i18n_coverage.py --scope ui`, which finds Chinese
  handed to a widget that was never wrapped at all. The test suite cannot see the latter.
- Do not add `setattr(MainWindow, ...)`, `globals()` dynamic exports, a service locator, cross-feature
  private calls or page-index navigation.
- Never commit the account database, WAL/SHM, logs, screenshots, PCAP, OCR temporary files,
  build/installer output, local SDK/dumps or unaudited binaries.

Before a release, at minimum complete: static checks, `core`, `full`, packaging-input review, the
upgrade/rollback path, a clean install with theme default verification, account switching, inventory
sync, and a real smoke test of the key calculation/save/assembly paths. A known failure must have clear
ownership and a user-visible boundary; an unverified feature must never be marked stable.

## 11. Upstream synchronisation

This fork adds localisation on top of `hxwd94666/NTE-Drive-Calculator`. Upstream declined the change, so
the divergence is permanent and must be managed rather than resolved.

Branch roles:

- `main` is a pristine mirror of `upstream/main`. Never commit to it — that is what keeps `--ff-only`
  working and makes upstream's changes readable on their own.
- `fork/main` carries the localisation and is the branch that gets built and released.

Per upstream release:

```bash
git fetch upstream
git checkout main && git merge --ff-only upstream/main
git checkout fork/main && git merge main
```

**Merge, never rebase.** Rebasing the fork's commits over a moving upstream re-resolves the same
conflicts every time; merging resolves them once. Keep `git config --global rerere.enabled true` on so a
resolution is recorded and replayed the next time the same conflict appears.

Expect conflicts and budget for them. 96% of the files this fork modifies are files upstream actively
edits. The 2.2.0 sync — 45 upstream commits — produced 27 conflicting files across 81 hunks. Almost every
hunk has the same shape, upstream having changed a line the fork had wrapped:

```text
ours   (the fork): setText(tr("⏳  扫描中... ({key} 停止)", key=...))
theirs (upstream): setText("⏳  扫描中... (F12 停止)")
```

Resolve by taking upstream's text and re-applying the `tr()` wrapper, then adding the new Chinese source
string to `locales/en.json`. Watch for a `tr(` opener that lives outside the conflict hunk: discarding
our side leaves its closing parenthesis behind, which `compileall` catches but `git` does not.

After every sync, run the gates in section 10 **and**:

```bash
python tools/quality/i18n_coverage.py --scope ui
```

The test suite fails when a `tr()` key is missing from the catalogue, but it cannot fail on Chinese that
upstream added and nobody wrapped — that just renders untranslated. `i18n_coverage.py` is what finds it.
Its blind spot is text assembled through a helper before reaching a widget, which no static analysis
sees, so a clean report is not proof of full coverage.

Two follow-on costs arrive with every sync and are tracked separately from the merge itself:

- Upstream's new UI arrives unwrapped, so `i18n_coverage.py` reports a backlog to localise.
- `docs/en/` mirrors only the Chinese documents that existed when it was written; upstream's new
  documents stay unmirrored until someone translates them.

`AGENTS.md` is maintained in English, so upstream's edits to it always conflict as whole sections and
need re-translating rather than merging. That is a deliberate trade: the file is read constantly by the
fork's maintainers and merged a few times a year.
