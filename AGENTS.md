# NTE Drive Calc repository development contract

This file governs the whole repository and keeps only the product hard contracts, architectural
boundaries and engineering gates that still hold. System principles, feature detail, external
integrations, unfinished work and real-hardware acceptance live in the documents under
[`docs/README.md`](docs/README.md).

This file must stay publishable: never write an account, token, CDK, private address, real UID,
absolute user path, complete packet capture, full OCR text, screenshot content or unredacted log
into it.

> This is a **fork** of `hxwd94666/NTE-Drive-Calculator` that adds Simplified Chinese / English
> localisation. Upstream declined the localisation, so the fork is maintained indefinitely. Section 14
> defines how to take upstream changes.

## 1. Source of truth and how to maintain it

On conflict, prefer in order:

1. Passing public behaviour tests and database constraints;
2. The product hard contracts and engineering gates in this file;
3. `docs/architecture.md`, `docs/features.md`, `docs/integrations.md`, `docs/reference/`;
4. Public Service/DAO/Integration contracts;
5. The current UI and legacy compatibility implementations.

Unimplemented capabilities go only in `docs/roadmap.md`. Local presentation such as UI copy, colours
and spacing is expressed by code and tests, not piled into this contract.

When maintaining the contract and feature documents, review the relevant sections first and **update
by overwriting**: rewrite the stale passage directly, merge duplicated facts, and delete history,
temporary conclusions and completed plans. Never append "changes in this revision", "compatible up to
version X" or equivalent patch paragraphs at the end. One fact keeps one authoritative location; other
documents reference it by link.

## 2. Development flow and definition of done

Before changing anything, establish:

- Whether the inputs and outputs belong to release static data, the local shared database, application
  global state, the current account, an in-memory result or an external integration;
- Which account, user database path, `AppContext.generation`, `snapshot_id`, static dataset,
  profile/config version, `slot_id`, lock snapshot, token and output directory the task freezes;
- What state Page/View, Controller, Service, Domain/Optimizer and DAO/Integration each own;
- How cancellation, account switching, stale callbacks, failure rollback and external side-effect
  confirmation are handled;
- Which public behaviour tests pin the upstream inputs, downstream saves, failure paths and
  compatibility entry points.

Product semantic changes are completed in this order:

```text
public behaviour tests → contract/docs → Domain/Service → DAO/Integration
→ Controller/UI → migrate callers and delete the old entry point → targeted verification
→ core/full plus static checks
```

Reproduce a defect before fixing it, then fix it within the smallest business scope. Keep
architectural migration separate from changes to scoring, OCR, damage, loadouts, rewind or schema
semantics. Old and new semantics must not dual-write, dual-read or be branched in the UI for any
length of time. A change to schema, payload, error codes or an external protocol must cover old-data
upgrade, transaction rollback and retry.

Done means: behaviour and lifecycle are tested; the documents describe only current facts; no new
compatibility façade, dynamic injection, cross-feature private call or TODO dual entry point; external
actions have a pre-operation baseline, a submission record and a final confirmation; and newly
introduced failures are reported separately from pre-existing ones across targeted, static and
core/full runs.

## 3. Technical baseline and layering

- Windows 10/11, Python 3.11, PySide6; entry point `main.py`, GUI composition root `src/ui/app.py`.
- Dependencies come only from `pyproject.toml`, locked by `uv.lock`; the version comes only from
  `src/app/version.py::__version__`.
- Current schemas: release static v16, public shared v2, account private v22. When upgrading, update
  the constants, append a migration, and update the tests and this file together.
- Quality entry point: `tools/quality/run_tests.py`; `core` covers the critical boundaries, `full`
  runs the whole unittest discovery.

Dependency direction:

```text
UI Page/View
    ↓
Controller + frozen dependencies
    ↓
Application Service
  ↙                 ↘
Domain/Optimizer       DAO/Integration
                           ↓
                 SQLite / nte-core / files / OCR / game input
```

- **UI** owns only widget values, selections and discardable display state; it writes no SQL, parses no
  protocol, and holds no algorithm or other page's state.
- **Controller** owns workers, cancellation tokens, busy state and result projection; it depends on
  narrow Services/Integrations and never proxies another controller.
- **Service** freezes the request and orchestrates rules, transactions and side effects; it returns
  Qt-free results and never looks up MainWindow or the current page.
- **Domain/Optimizer/Solver** compute purely over complete immutable inputs; no SQLite, Qt, logging,
  account or process access.
- **DAO** exclusively owns schema, migrations, SQL and transactions.
- **Integration** exclusively owns nte-core, the plugin, OCR, mouse/gamepad, external processes and
  file formats; it never decides scoring or saving policy.
- **Observability** owns sinks, redaction and operation correlation, and depends on no feature,
  Service, DAO or UI.

`AppContext`, `EquipmentPresentation` and `GlobalHotkeyManager` are created only in the composition
root and injected explicitly. Cross-layer relationships use the official `character_id`, `item_id`,
`suit_id`, `shape_id`, `property_id`, real equipment UIDs and `slot_id`; Chinese names and `slot_name`
are display only. Navigation uses key/`parent_key`, never a stacked-page number or a scan of
MainWindow fields to locate a service.

Legacy boundaries that may be maintained but must not be copied:

- `ScoringEngine` can still fall back to reading SQLite when no catalogue is injected; new callers have
  immutable scoring input injected by a Service.
- The legacy MainWindow dynamic exports in `src.features.inventory.page` keep only the existing
  `__all__`.
- `UserDataDao` is a compatibility façade over several narrow DAO mixins; new work creates a narrow
  DAO/Service instead.
- Some calculation, loadout and scanning controllers still open a DAO directly; local fixes may follow
  the existing path, but new capabilities must not widen that pattern.
- `NAV_ITEMS` binding button properties is limited to the composition-root navigation mixin; features
  must not imitate it to inject business fields.

## 4. AppContext, accounts and async lifecycle

`src.app.context` is the single composition root for paths and account state: `ApplicationPaths` owns
release resources and global paths, `AccountContext` owns the current account's database, config,
screenshot and log directories, `AppContext.generation` identifies the account generation, and
`AccountLifecycle` owns stopping, rebuilding and resuming background capabilities.

A long task freezes everything listed in section 2 at creation and re-checks it before callbacks and
writes; if any value is stale it is discarded silently, never projected onto a new account and never
written to a new account or slot. Account switching always follows: stop account tasks → replace the
context and increment the generation → rebuild narrow services → clear per-page account caches →
resume the services allowed to run automatically.

- A worker may be `None` both before creation and after release; check run state through a local
  reference.
- Cancellation only invalidates the current token; background callbacks still re-check generation,
  path, snapshot and slot.
- Application exit calls each feature's public `close`/`stop` and never mutates worker private state.
- Inventory sync, battle-report capture, scanning, appraisal and game input coordinate exclusive
  resources through the public lifecycle, not by disabling a button.

## 5. Data ownership, migration and snapshots

| Data domain | Path | Ownership |
| --- | --- | --- |
| Release static | `data/game_static.sqlite3` | Official catalogue, growth, skills, enemies, recommended weights, graduation templates; read-only at runtime |
| Public shared | `data/app_shared.sqlite3` | Release baseline and cross-account public overrides for official characters' extra shapes |
| Application global | `config/global_ui_preferences.json` | Cross-account theme and interface language |
| Account private | `accounts/<account_id>/user_data.sqlite3` | Snapshots, character instances, weights, preferences, custom characters, slots, plans, locks, jobs, battle reports |

Read priority is the account's explicit config → public overrides that permit sharing → release
defaults. Official extra shapes may be overridden publicly; custom characters, base weights,
calculation/rewind preferences, loadouts, locks and jobs belong to the current account only. Theme and
language are application-global, and an account switch does not reload a per-account theme. Account
import/export must migrate a complete account as one unit, preserving structured preferences,
slot/plan relationships and referential integrity.

The static database is read-only at runtime. When generating or replacing it, update the dataset,
schema, importer and SHA-256 in `data/manifest.json` together, and verify the database and manifest as
one atomic change. Account and shared migrations are append-only; published SQL is never renamed,
reordered or changed in meaning. Migration tests cover new-database creation, upgrade from each
affected old version, failure rollback, retry after repair, and foreign keys/unique indexes/views.
Pages and Services never assemble SQL; the DAO transaction is the final consistency guard.

Inventory snapshots are immutable and the current pointer only ever points at a complete stable
snapshot. Downstream work resolves `snapshot_id` once at the start and does not follow the latest
pointer while running; an active plan is always read against its own `source_snapshot_id`. Snapshot
cleanup protects the current snapshot, every active/locked plan and slot, and references held by
unfinished jobs, so historical plans stay reproducible. `InventorySnapshotStabilizer` judges stability
by a complete content fingerprint plus a quiet window, never by the historical maximum count;
`inventory.get_latest` only reads the most recent capture and does not force a refresh.

Source capability must be decided through the public capability helper:

- `nte_core` provides real UIDs, character instances, reliable equipment state, warehouse RPC and fast
  assembly.
- `vision` / legacy `gamepad` provide temporary UIDs usable for analysis, warehouse display,
  calculation, rewind and in-game automatic assembly; they never enter fast assembly and never provide
  reliable character ownership.
- Runtime state deltas only overlay the locked, discarded and equipped state of UIDs already known in
  the pinned native full snapshot; a partial event must not add items, replace the inventory set or
  advance the current pointer.

## 6. Calculation, characters and scoring

A calculation freezes the account, generation, snapshot, static dataset, profile, character
order/equal-priority groups, target slot, lock snapshot and all character configuration, and returns
an immutable `WeightedAllocationPreview`. Saving consumes only that preview and never re-reads the
latest state to fill gaps; before saving it re-checks the account, generation, snapshot, profile,
`slot_id` and locks. Single-character, bulk, weighted and every allocation strategy share the same slot
and candidate contract.

Candidate rules:

1. `AllocationLockSnapshot` excludes locked real UIDs together before candidates are built; an invalid
   lock blocks the calculation.
2. The account "filter settings" select no type and no rarity by default. Once Cartridge or Module is
   selected, at least one rarity must be selected; for a selected type only the selected rarities reach
   the character-management filter, while unselected types follow the default rules. Character-priority,
   global-optimum and incremental-update modes share the filter result.
3. The Module sub-stat blacklist is a hard filter by default; with "blacklist means zero weight" on,
   matching Modules are not eliminated and the matched stats are weighted 0 in the Top-K scoring.
   Custom sub-stat selection is not a hard filter: ordered mode prefers the deepest prefix, consistent
   mode prefers the most hits, and when no combination works the pool widens step by step, finally
   returning to the full candidate pool.
4. Cartridges apply the set and main-stat hard filter first, then the same layered sub-stat fallback;
   the main stat takes precedence. The default set is 4-piece, overridden only explicitly.
5. "No grade restriction" only removes the custom sub-stat threshold; it does not remove the set, the
   Cartridge main stat, or the blacklist's current semantics.
6. Equal-priority group CRIT recovery is fixed as: swap the Cartridge only → freeze the required set
   pieces and re-pick the extra pieces → rebuild only the failed characters from scratch. The final
   stage does not release same-tier characters that already succeeded.
7. Real UIDs already assigned to an earlier character do not enter later candidate pools; virtual
   placeholders score 0 and can be neither locked nor fast-assembled.
8. When a character is dragged across a `>>`, every crossed boundary moves back one place; when
   dragging back-to-front forms a new boundary, everything from the previous `>>` (or the first item)
   up to the new boundary is merged into `=`.

Characters and scoring:

- Unless explicitly overridden, official characters use the static graduation template's default set
  and signature weapon; every character defaults to no Cartridge main stat and no sub-stat priority.
  The public effective-config reader merges template defaults with account overrides, and global
  optimum accepts only an explicit global override. An upgrade must never overwrite explicit account
  config; the effective CRIT Rate cap is `100 - the max-level default signature weapon's CRIT Rate`.
- A custom character owns an account-scoped real custom ID, weights, extra shapes, default set and a
  5×5 chassis; the chassis enables a fixed 20 cells and supports per-cell locking. It can take part in
  vision-inventory calculation and in-game automatic assembly, but never enters official details,
  nte-core character instances, in-game loadout import or fast assembly.
- Account base weights are a persistent calculation input; the dynamic final weights come from
  normalising the current panel's direct-damage margin and are used only for analysis and replacement
  ordering, never written to the database.
- Calculation ignores level-1 Cartridge values in the snapshot and uniformly uses the `StatCatalog`
  max-level values: gold/orange 1.0, purple 0.8, blue 0.6.
- A single Cartridge/Module is graded on the ratio `score ÷ (area × 10)`; a complete plan's overall
  grade uses fixed bands: D `<160`, C `>=160`, B `>=180`, A `>=200`, S `>=220`, SS `>=240`,
  SSS `>=260`, ACE `>=280`. Official characters, custom characters and each slot use that overall grade
  independently, and it never changes an individual item's score.
- New plans write `payload.assignment_scores` and `payload.tape_main_values`; the unified helper
  fallback is called only when an older plan lacks those fields.

## 7. Loadout slots, plans and locks

- Each character manages several loadout slots keyed by a stable `slot_id`; `primary` is the
  compatibility default slot and `slot_name` is display only. Creation, rename, archiving and selection
  go through `LoadoutSlotSelectionService`/DAO.
- Several slots on one character are alternatives and may reuse the same real UID; only different
  characters' current slots referencing one UID is a conflict. Character-priority, global-optimum,
  incremental-update and every allocation strategy respect that boundary.
- Calculation results warn only about characters selected in step two whose slots are all locked;
  unselected characters produce no warning.
- An active plan stores the character, slot, source snapshot, assignments, payload, source type and
  lock; `role_loadout_slot.current_plan_id` is transactionally consistent with the active plan.
- The in-game loadout view is a read-only projection of a native stable snapshot; only an explicit
  player import saves it as `game-observed-loadout-v1`. Vision sources are not used for in-game loadout
  import; complete Modules with no Cartridge may be saved as `incomplete/missing_tape`.
- Calculated plans and imported plans both take part in locking, deletion, replacement, assembly and
  rewind recommendation.

A calculation lock belongs to a specific slot plan in the current account and never calls the game's
lock RPC. One real item is enough to lock, a missing Cartridge is allowed; an empty plan or one holding
a virtual placeholder cannot be locked. A locked plan's current slot must not be deleted, overwritten
or archived, and no single item in it may be replaced; a bulk clear skips it and reports. No other
character may borrow its UIDs, and the DAO save transaction checks again. Bulk slots require unique
`slot_id`, a consistent character, a native source and no cross-character UID conflict.

`EquipmentPresentation` is the single shared display component for equipment cards, grades, attribute
gains, differences and result areas; it writes no SQLite, selects no snapshot and starts no worker.
Calculation, loadouts, warehouse and appraisal reuse it only through its public interface.

## 8. Warehouse, scanning, appraisal and hotkeys

The warehouse reads a pinned snapshot. `WarehouseInventoryService` builds the projection, the
state-management Service pins `snapshot_id` and real UIDs to build the plan, and the Integration
performs the action. An accepted command may immediately project the target state, but that is not
final success; a later increasing full snapshot or an official scoped event confirms it. A scoped event
may replace the inventory set only when it covers every target UID; only an action session receiving an
explicit count reduction prompts a re-sync, and background listening never replaces the set on its own.

Warehouse filters use the real `suit_id`, `shape_id` and `property_id`, OR within a group and AND
across groups; states are equipped, locked, discarded and other. Reset clears every condition and never
uses a tab as an implicit condition. The evaluation character scope affects warehouse state-rule
scoring only, isolated from calculation characters, the active loadout and rewind preferences. The
vision warehouse is read-only; immediate write-back belongs to the same mouse-scan session only.

Vision scanning contract:

- Immutable dependencies are created at start, freezing the account, generation, directories, user
  database, management configuration and hotkeys; the OCR/vision Integration only parses, and file
  lifecycle is owned by a separate component.
- Only a complete result commits a snapshot in one transaction; cancellation, an exception or a count
  mismatch commits nothing half-finished. Missing Cartridge values are filled by the unified max-level
  rule.
- Mouse and virtual-gamepad full scans both perform one long top-to-bottom drag before their existing
  navigation to reset the list. The mouse final page maps the entered inventory total onto a
  bottom-aligned viewport and works in both dual-thread and compatibility modes; the virtual gamepad
  keeps its existing pagination/positioning flow.
- Post-scan management positions in reverse frozen-index order and re-checks each item's detail
  identity, pre-operation state and post-operation state. When the pre-operation state disagrees with
  the pinned plan the item is not clicked — it is recorded, the rest continues, and the final dialog
  summarises it; a positioning, identity, confirmation-dialog or post-operation check failure still
  stops all further input. Diagnostics go to `mouse_state_sync_last_report.json`, and a temporary UID is
  never promoted into a writable UID.

Appraisal projects screenshots, the clipboard, manual input and the warehouse single-item entry point
into one unified equipment object, calls only the shared scoring and display, and writes no inventory,
base weights or loadouts. Scanning, appraisal, automatic assembly and rewind input all use the
application-level global stop key from Settings; a running task freezes the binding at start, an owner
stops only its own session, and every stop path releases mouse/gamepad state.

## 9. Rewind recommendation and execution

Rewind analysis reads only the pinned inventory, the current account's `rewind_recommendation` and each
slot's active plan. The preference fields are `target_character_ids`, `main_character_ids`, `strategy`,
`target_grade`, `target_threshold_mode` and `target_custom_percent`. Opening the page or changing an
option does not solve automatically; only an explicit "generate recommendation" runs it.

```text
standard threshold = grade_ratio × max(1, drive_area) × 10
custom threshold   = custom_percent × max(1, drive_area) × 10
shortfall          = max(0, threshold - saved_assignment_score)
grade_ratio: D=0, C=.2, B=.3, A=.4, S=.5, SS=.6, SSS=.7, ACE=.8
```

The custom range is 1.0%–100.0% at 0.1% precision; each item is computed against its own area, and
matching the threshold produces no shortfall. A high score does not offset another Module's shortfall,
and the threshold affects only the rewind shortfall — never the underlying per-item score or the plan's
overall grade. Per-item scores prefer the saved `assignment_scores` and are recomputed uniformly when an
older plan lacks them; custom characters and each active slot of the same character count independently.

- Balanced: every shape with a positive shortfall keeps one slot first, and the remaining slots are
  distributed by `shape shortfall / max(1, shape inventory)`.
- Focused push: only push characters count; every shape with a positive shortfall keeps one slot first,
  and the remaining slots are distributed by shortfall alone, without dividing by inventory.
- More than eight shapes with a positive shortfall shows "所需驱动超过 8 个，建议降低评分等级或使用随机
  倒带抽取。"
- The pool is a fixed eight slots at 12.5% each; when a shape repeats `q` times each slot costs
  `10 + 5 × (q - 1)` and the total is `q × per-slot price`. Difficulty determines only blue/purple/gold
  rarity and never affects shape, probability or price.

An explicit "start rewind" freezes rarity, custom mode and the eight-slot plan. Each rarity switches
difficulty first and then reads its own balance; the beginner random ten-pull is fixed at 600, and
purple/gold custom reads the ten-pull price on the right. "No changes" keeps the existing candidates and
"apply plan" completes the eight-slot configuration. After the prerequisite click it waits 1 second, and
the ten-pull loop is fixed as: click insert-coin 10 times → 1s → Esc → 1s → Esc → 0.5s. Execution obeys
the global stop key; real input remains an experimental capability in `docs/roadmap.md`.

## 10. Assembly, battle reports, settings and updates

Fast assembly consumes only native real UIDs, character instances and saved slot plans; in-game
automatic assembly consumes the vision projection and can support custom characters. Both chains freeze
the account, generation, source snapshot, target slot, character items and token, block account
switching while running, and persist progress.

Fast assembly makes at most three full requests per character. After dispatch it waits 10 seconds for an
increasing full snapshot; an accepted command may immediately project the target character and cells,
but a projection is not a confirmation. A full snapshot is preferred and verifies the character,
instance and complete equipment set, and a Module cell difference alone does not trigger re-assembly; a
scoped event triggers a retry only when the target equipment clearly appears but is not equipped. With
neither a new snapshot nor a scoped event the round simply ends — absence of evidence is not an
omission, and the inventory set is not replaced. A clear mismatch on the first or second attempt
triggers unequip-and-reassemble; only a third mismatch reports a final error. The regular mouse path of
in-game automatic assembly is the public capability; cloud mode is pinned off by the controller, and its
boundaries are in the roadmap.

Battle reports use only nte-core combat aggregate events and summaries and write history to the current
account; inventory sync and battle reports never compete for the capture session. Per-hit data,
buff/debuff intervals, teams, enemy instances and scenes must never be inferred from an aggregate
summary. The live overlay is shown only during the current capture session and only when enabled in
settings; finishing and generating a report, an error, viewing history and a stopped state all hide it,
and only an explicit next start shows it again.

The settings page receives only `AppContext`; the theme and language are written application-global and
every other preference to the current account or an explicit application-level path. The Mirror
controller/integration owns version checking, downloading, cancellation and launching the installer; a
remote version lower than the current one is treated as already up to date and is never downloaded. A
Mirror failure message offers a clickable project page, and logs never record a CDK, token or
authentication URL.

## 11. UI, localisation, external integrations and logging

Top-level navigation is fixed as Dashboard, Calculate, Loadout, Characters, Warehouse, Appraisal,
Battle report, Toolbox and Settings; character blueprints and base weights are character sub-pages that
keep the parent navigation highlighted through `parent_key`. MainWindow owns only composition,
navigation, account switching, page lifecycle and exit.

New and modified dialogs use `src.app.window_geometry` to bound their size by the current screen's
available area and centre them relative to the owner/current screen, covering common and mixed DPI
scaling rather than only 125%. Custom colours, selected states and widget states must work in the
original, black and white themes alike; scroll-wheel browsing must never produce a data change that did
not happen.

All new or modified UI copy goes through `src/i18n`, distinguishing two kinds of text:

- **UI copy** uses `tr("Chinese source string")`, with f-strings rewritten as
  `tr("...{name}...", name=value)`, and that Chinese source string added as a key in `locales/en.json`.
  The catalogue is keyed by the source string, so a missing translation degrades to Chinese rather than
  to a key name.
- **Game terms** use `display_term()`. The Chinese key is simultaneously an OCR match value and a
  `game_static.sqlite3` lookup key, so translating, rewriting or processing it in place is forbidden;
  the display name is substituted only when it is about to be written into a widget, while weights,
  scoring, sorting, filter keys and state checks keep using the Chinese key. The percent suffix is
  derived from the Chinese key and never by testing whether the display name contains `%`.
- Fields for which nte-core already supplies `names`/`suit_names` (`en`/`ja`/`zh_cn`) use
  `display_localized()` instead of a glossary entry.

Logging text stays Chinese: `logger.*`, `log_event` and `operation_scope(message=)` never go through
`tr()`. Exception messages in Services and Integrations that **are shown to a user** go through `tr()`;
pure argument contracts (the `timeout 必须大于 0` kind) stay Chinese.

On first launch — no `language` key in the preferences file — a bilingual chooser is shown once and the
answer is recorded. The question is asked before `set_language()` and is gated on `NTE_GUI_LAUNCH`,
which only `main.py` sets: tests import `src.ui.app`, and a dialog there would hang the suite.

The language is activated while `src/ui/app.py` is imported, so module-level copy must preserve the
order "`set_language()` first, then import UI modules". Tests pin the source language with
`NTE_UI_LANGUAGE`, and assertions must not depend on the local preferences file. English singular forms
use a sibling key `"<source>::one::<field>"`, and the field name must be stated so a second integer in
the same sentence cannot trigger it. Details are in `docs/reference/localization.md`.

nte-core, Npcap, dwmapi, mods, OCR and game input are all Integrations. Local binaries in the root
directory stay ignored; a `third_party` release component is updated only after recording the upstream
commit/version/licence/SHA-256 and passing protocol, packaging and real Windows verification. The
Windows validator is for maintenance only and never enters the installer.

Logging layers: Infrastructure owns sinks, Controller records the operation lifecycle, Service records
business stages, DAO/Integration record storage and external interaction, and Domain returns
diagnostics. Never log a complete RPC/inventory, UID list, account display name, absolute path, full OCR
text, screenshot, CDK, token, authentication URL or recoverable payload; the field specification is in
`docs/reference/logging-events.md`.

## 12. Code, repository and documentation gates

- A new or modified Python file under `src/`, `tools/` or `tests/` must not exceed 800 lines; existing
  oversized files may only shrink, and when touched are split by state ownership rather than evaded by
  compressing the formatting.
- A new `type: ignore` must carry the error code and a reason. Ruff `E9/F63/F7/F821/F401` is a
  repository-wide hard gate.
- New UI copy must pass `tests.test_i18n`: `test_every_tr_key_resolves` parses every `tr()` key under
  `src/` and fails when one is missing from `locales/en.json`; a singular sibling key must correspond to
  a real source string and a real placeholder.
- New UI copy must also pass `python tools/quality/i18n_coverage.py --scope ui`, which finds Chinese
  handed to a widget that was never wrapped — the test suite cannot see those.
- A new dependency updates `pyproject.toml` and `uv.lock` together; tests never rely on a package that
  happens to be installed on a developer machine.
- Features reuse only public components and contracts, never calling another feature's underscore-private
  implementation or touching another page's widget/worker.
- Do not add `setattr(MainWindow, ...)`, `globals()` dynamic exports, module-global scanning, page-index
  navigation or a service locator.
- Releases are built locally by the maintainer and published by hand with `gh`; no automated release
  workflow.
- `accounts/`, WAL/SHM, logs, screenshots, PCAP, OCR temporary files, build/installer output, local
  SDK/dumps, absolute paths and unaudited binaries must never enter Git.

The documentation entry points are fixed: `docs/README.md` (index), `architecture.md` (boundaries and
data flow), `features.md` (current features), `integrations.md` (external capabilities), `roadmap.md`
(unfinished work), `reference/` (formulas and fields), `validation/` (real-hardware evidence). Follow
the overwrite rule in section 1 when changing them, and check every relative link.

The Chinese documents under `docs/` are authoritative and `docs/en/` plus `README.en.md` mirror them:
change the Chinese first, then sync the mirror, and never add a fact to the mirror that the Chinese
lacks. This file is maintained in English only, because the fork's maintainers work in English; see
section 14 for what that costs at merge time.

## 13. Verification requirements

Choose the targeted tests by change scope:

| Scope | At least covers |
| --- | --- |
| AppContext, accounts, workers | app-context, account-user-database, settings-context |
| Sync, snapshots, scanning | inventory-sync, stabilizer, vision/streaming, mouse/gamepad, OCR golden |
| Calculation, candidates, replacement | allocation, weighted-allocation, role-selector, crit, replacement |
| Custom characters, weights, blueprints | custom-role, character-weight, blueprint, graduation |
| Slots, plans, locks | loadout-slot/DAO, lock, game-loadout, equipment display |
| Warehouse, appraisal, hotkeys | warehouse, state-management, identification, hotkey boundary |
| Rewind | rewind recommendation, shape detection, toolbox, saved scores |
| Fast/automatic assembly | equipment-apply, verification, bulk, drive-assembly |
| Battle reports | DAO, persistence, capture lifecycle |
| SQLite/static data | migration, static/shared data, manifest, catalog |
| Docs, dependencies, packaging | Markdown links, module boundaries, repository hygiene, packaging |

Authoritative commands:

```powershell
python tools/quality/run_tests.py core
python tools/quality/run_tests.py full
$mypyFiles = Get-Content tools/quality/mypy_allowlist.txt
python -m mypy $mypyFiles
python -m ruff check .
python tools/quality/i18n_coverage.py --scope ui
python -X pycache_prefix=build/compile-cache -m compileall -q src tests tools
uv lock --check
git diff --check
```

When real game, driver, plugin or update behaviour is involved, additionally run
`tools/windows_validation` and `docs/validation/windows.md`. Before finishing, confirm that the static
database and manifest contain only the expected changes, migrations are retryable, documentation links
resolve, no local data entered Git, and that upstream inputs, failure paths, downstream saves, final
confirmation and rollback all have test or manual acceptance evidence.

## 14. Upstream synchronisation

This fork adds localisation on top of `hxwd94666/NTE-Drive-Calculator`. Upstream declined the change,
so the divergence is permanent and must be managed rather than resolved.

Branch roles:

- `main` is a pristine mirror of `upstream/main`. Never commit to it — that is what keeps `--ff-only`
  working and makes upstream's changes readable on their own.
- The fork trunk carries the localisation and is the branch that gets built and released.

Per upstream release:

```bash
git fetch upstream
git checkout main && git merge --ff-only upstream/main
git checkout <fork trunk> && git merge main
```

**Merge, never rebase.** Rebasing the fork's commits over a moving upstream re-resolves the same
conflicts every time; merging resolves them once. Enable `git config --global rerere.enabled true` so a
resolution is recorded and replayed the next time the same conflict appears — it pays for itself on the
second sync.

Expect conflicts, and budget for them. 96% of the files this fork modifies are files upstream actively
edits, and one measured release produced 21 conflicting files across 38 hunks. Almost every hunk has the
same shape — upstream changed a line the fork had wrapped:

```text
ours   (upstream): self.btn_run.setText("⏳  扫描中... (F12 停止)")
theirs (the fork): self.btn_run.setText(tr("⏳  扫描中... ({key} 停止)", key=...))
```

Resolve by keeping upstream's logic and re-applying the `tr()` wrapper.

After every sync, run the gates in section 13 **and**:

```bash
python tools/quality/i18n_coverage.py --scope ui
```

The test suite fails when a `tr()` key is missing from the catalogue, but it cannot fail on Chinese that
upstream added and nobody wrapped — that just renders untranslated. `i18n_coverage.py` is what finds it.
Its blind spot is text assembled through a helper before reaching a widget, which no static analysis
sees, so a clean report is not proof of full coverage.

`AGENTS.md` is maintained in English, so upstream's edits to it always conflict as whole sections and
need re-translating rather than merging. That is a deliberate trade: the file is read constantly by the
fork's maintainers and merged a few times a year.
