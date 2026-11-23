# NTE Drive Calc: development agent contract

Read the [project purpose, anti-abuse and collaboration statement](RESPONSIBLE_USE.md) first: this project
serves equipment calculation and understanding the game, and does not assist development requests for cheating,
undermining fairness or infringing rights holders.
This file records only cross-feature hard boundaries; detail lives in the topics indexed by
[docs/README.md](docs/README.md). Before starting, verify the current branch, working tree and actual code, and
never infer the current state from old conversations or a released version. This file is publishable: never write
an account, credential, real UID, packet capture, screenshot, raw OCR text, unredacted log or local absolute path.

**UI copy and language patches are a completion gate.** Any task that adds, changes or removes visible text,
down to a single sentence, must follow [section 9](#9-ui-language-and-logging).

> This is a **fork** of `hxwd94666/NTE-Drive-Calculator` that ships an English interface. Sections 1–10 mirror
> upstream's contract in English; sections 11 and 12 are the fork's own.

## 1. Sources of truth

On conflict, rank in order: passing public behaviour tests, database constraints and official protocols → this
contract → the domain documents → the current UI's appearance. Versions, schema, capability names and dataset
identity are true only in the code, manifests and database; documents copy no perishable number. Legacy
cross-layer calls in the code are not a pattern to follow.

| Question | Where |
| --- | --- |
| Layering, ownership, lifecycle | `docs/architecture.md` |
| Menus, buttons and configuration limits | `docs/architecture-map.md` |
| Delivered behaviour | `docs/features.md`, `docs/features/` |
| Components, protocols, static builds, releases | `docs/integrations.md` |
| Formulas, fields, formats | `docs/reference/` |
| Unfinished capabilities | `docs/roadmap.md`, `docs/roadmap/` |
| Real Windows acceptance | `docs/validation/windows.md` |

Editing a document overwrites the original section and deletes what is stale; one fact lives in one place.
Delivered work goes into features, unfinished work into the roadmap, and one-off investigations stay out of the
repository.

## 2. Product semantic boundaries

| Domain | Boundary that must hold |
| --- | --- |
| Accounts | Data is isolated per account; switching stops the old tasks and advances the account `generation` first |
| Work modes | Offline / low risk / medium risk / development; the combo box is only a draft and takes effect on confirmation; a downgrade revokes side-effect permission first. Details in `docs/reference/work-modes.md` |
| Sync | Automatic sync starts only sync — never battle reports, assembly, discard, lock or plugins; it turns off on account switch and must be explicitly turned on for the new account |
| Calculation | Every input is frozen; saving consumes only that preview and never fills gaps from "the latest state" |
| Character sync | Overwrites only fields this run returned and proved; missing, unknown and trial characters keep their old values |
| Loadouts | `slot_id` is the identity and `slot_name` is display only; each plan keeps its own source snapshot and frozen scores |
| Warehouse and appraisal | A vision source never reads or writes the game's lock/discard; appraisal writes neither inventory nor loadout; "discard" only sets the game flag and deletes no equipment |
| Scanning and input | A complete result commits once; cancellation, a count anomaly or an input failure leaves nothing half-finished; hooks into the application stop key and releases input devices |
| External writes | Plan → freeze → dispatch → confirm afterwards; an accepted command is not success; with an unknown result, stop what follows and resend nothing automatically |
| Battle reports | Raw facts are immutable; derived results carry a version and provenance; unknown never poses as zero, a multiplier of one or "complete" |
| Plugins | Each card keeps its own state; turning a plugin off never starts or stops a battle report |
| Tools | The catalogue is read-only; the growth calculator writes no character profile, inventory or stamina estimate |
| Environment | Path, file, process, connection, handshake, declared capability and business readiness are different states, judged separately |

## 3. Architecture and identity

Windows 10/11, Python 3.11, PySide6; entry point `main.py`, composition root `src/ui/app.py`; dependencies come
from `pyproject.toml`/`uv.lock` and the version from `src/app/version.py`. Dependency direction:

```text
UI Page/View → Controller → Application Service → Domain/Optimizer or DAO/Integration
```

- UI owns only widgets and discardable display state; Controller handles workers, cancellation and navigation, and
  writes no formula, SQL or data compatibility.
- Service freezes requests and orchestrates transactions; Domain computes purely and touches no Qt, file, process
  or database; DAO exclusively owns schema, SQL, migrations and backups; Integration exclusively owns processes,
  files, protocols, OCR, input and system probing.
- `AppContext`, `EquipmentPresentation`, the global hotkeys and the shared native session are created by the
  composition root and injected explicitly; no service locator, no dynamic attachment to MainWindow, no
  cross-feature private call and no lasting old/new dual entry point.
- Across layers use only the official `character_id`, `item_id`, `suit_id`, `shape_id`, `property_id`, equipment
  UID and `slot_id`; Chinese names are display only.
- When moving a module, update dynamic imports, test patches, resources and build references together and delete
  the old entry point; leave no compatibility shell.

This repository is Calc's product and integration side. `nte-core.exe` (capture and game interaction) and
`nte-analysis-core.exe` (Rust calculation/analysis) are independent components, consumed only as complete bundles
with a version, provenance, manifest and SHA-256; never copy private source or bypass the official protocol. A
source merge, a build, a component promotion, packaging and real-game acceptance never substitute for one another.

## 4. Data domains and account lifecycle

| Data | Rule |
| --- | --- |
| `data/game_static.sqlite3` | The main release static data; read-only at runtime |
| `data/role_catalog/` | The standalone catalogue, purpose identity `role_page`/`reference`; never automatically replaces the battle-report dataset |
| `config/` | Local preferences; never carried by an account import or export |
| `accounts/<id>/user_data.sqlite3` | The current account's private data, reached only through the current account context |
| `data/app_shared.sqlite3` | Only legacy migration data the contract explicitly allows |
| `build/`, temporary directories | Rebuildable output; not a source of truth and never sent out |

- A long task freezes, when created, the account, generation, paths, dataset, `snapshot_id`, configuration
  version, target `slot_id`, lock snapshot and cancellation token; it re-checks them before callbacks, saves,
  database writes and external commands, and discards stale results silently. Account switching, mode downgrade
  and exit revoke permission first, then wait a bounded time for tasks to finish.
- An agent may raise the database version only when the task itself acquires and imports new character data from
  scratch, or the user explicitly asks for a database version upgrade. Every other task keeps the existing schema
  version, `PRAGMA user_version` and migration target version.
- SQLite migrations are append-only and a published migration never changes meaning; a schema/payload/protocol
  change covers a new database, upgrading, failure rollback and retry. Multi-table writes go in one transaction;
  JSON is written to a temporary file and replaced atomically; a live database is backed up consistently, never by
  copying WAL/SHM.
- An account export contains no logs, caches, captures, credentials or other accounts' data; an import validates
  format, paths, duplicate members, total size and the user database first, then stages, migrates and switches
  atomically, keeping the original account on failure. Deletion, overwriting and cleanup act by official identity
  and ownership.

## 5. Source capability and static data

- The inventory's current pointer only ever points at a complete, stable, immutable snapshot; a task resolves
  `snapshot_id` once at the start and a plan reads its own `source_snapshot_id`. `unknown`, `partial`,
  `complete=false`, a missing page and a mapping conflict never commit the official set, which is never filled from
  an old snapshot, a fixed count or a default zero.
- Source capability is decided by the public helper: `nte_core` supplies official UIDs, character instances,
  equipment relationships, lock/discard and native writes when the evidence holds; packet capture can give a
  complete inventory and battle-report facts but never fakes native capability; a vision source only analyses,
  appraises and does ordinary mouse assembly. A historical snapshot, a battle-report frozen subset, a graduation
  template and an edit copy are none of them the current inventory.
- The main static database is built only as a candidate under `build/` by `tools/game_data/` and promoted
  atomically by `tools/game_data/promote_static_release.py` after validation; never overwrite `data/` directly,
  and increment the importer version when normalisation semantics change. Catalogue and skill images go through
  `promote_role_catalog.py`, with steps in `docs/integrations.md` and `skills/nte-game-update/`. Permanent stats of
  a new Arc or set are reviewed piece by piece against evidence, never fabricated from descriptions, templates or
  zero.

## 6. Calculation, scoring and loadouts

- Allocation solving, equipment base scoring, direct damage and marginals, damage post-processing, battle-report
  analysis and team axis-damage graduation all run in `nte-analysis-core.exe`; Python freezes requests, checks
  capability, re-verifies results, saves and displays. A component missing a required capability reports an
  explicit error and never falls back to a Python formula. `ScoringEngine` is only an adapter and copies no formula.
- A calculation produces an immutable `WeightedAllocationPreview`; saving consumes only it and re-checks the frozen
  boundaries. A real UID is consumed only once globally; locked UIDs are excluded first; a virtual placeholder
  scores zero and takes no part in locking, lending or assembly. One character's failure never interrupts the
  others; cancellation never overwrites an old plan.
- Direct-damage-first and axis-damage-first run only as independent post-processing on a copy of the complete
  character-priority baseline; they never change the upstream request, weights or base scores, and never claim a
  global damage maximum.
- A saved plan's `assignment_scores` are a frozen fact; changing weights after a calculation does not reinterpret
  an existing preview, and only an old plan missing scores is recomputed through the same engine.
- The effective character panel (level/ascension, Arc, permanent stats, affinity, furniture, awakenings, skill
  levels, CRIT floor and cap) is computed only in the shared character panel service, and calculation, graduation
  rate and loadout summaries consume the same projection; conditional effects never enter the permanent panel.
- A Calc plan lock is not the game's lock; a locked plan must not be deleted, overwritten, archived or lend out its
  UIDs. Scan management and warehouse management each own their configuration, matching scope and drafts, and
  never write into each other.

## 7. Battle reports

The capture layer saves only the facts Core gave and never guesses crits, Buffs, shields, healing, the team or the
scene from a summary. At the start it freezes the account generation, dataset and source capability; native capture
freezes team and equipment evidence at each half's first hit, and once the first settlement is frozen a retry never
changes the input. Raw snapshots are immutable; an edit copy takes part only in replay and counterfactuals. The
battle-report page goes only through the analysis component's read-only interface, and a missing manifest, hash,
protocol or capability never falls back to reading the database from Python. The import/export format is in
`docs/reference/battle-report-package.md`.

## 8. Components, permissions and releases

- A component promotion records the upstream version, commit, licence and SHA-256; DLL, Loader, scripts,
  resources and protocol are replaced as a set. A private delivery contains no source, PDB, account data,
  credentials, captures or sensitive logs.
- The game path must be a verified absolute path to `HTGame.exe`; deployment manages only components verified in
  the current release bundle, waits when the game is running or permission is insufficient, and never force-closes
  the game; cleanup acts by recorded directory and exact file name and never scans disks recursively.
- The GUI must run at High integrity: when it is insufficient, request a `runas` restart once; if still
  insufficient, stop and guide the user to start from the Start menu or desktop shortcut, and never change system
  security settings. The installer must be built as an administrator (Inno Setup 6 or later), with the product
  marked High.
- The portable release states its program domain and data root explicitly; a failed update keeps the old runnable
  version; the mirror update chain never records an authenticated URL, token or CDK.

## 9. UI, language and logging

- Adding, changing or removing UI copy must, in the same change, maintain the actual callers,
  `assets/locales/zh-CN.json` and `docs/examples/locales/qps-ploc.json`, checking the stable keys and named
  parameters of both catalogues. Removing copy follows the compatibility convention for old keys. Display code uses
  the injected `TextCatalog.render`, or registers the whole Chinese sentence for the display boundary to project
  (replacement happens only at Qt display; source and data layers must never replace text). Business branches use
  stable IDs and never depend on translations; official game names, character/slot names, protocol fields and log
  event codes are never registered or translated; concatenated sentences use a key with named parameters, and where
  a service has no catalogue the display boundary projects the registered template line by line. Internal
  diagnostics carry `# ui-text: internal`; the coverage gate's baseline is empty, so new unregistered Chinese fails
  directly. Details in `docs/features/localization.md`.
- A new dialog uses `src.app.window_geometry` to stay within the screen's available area and centre; colours and
  states work in the original, black and white themes.
- A delayed callback (such as `QTimer.singleShot`) must be bound to an owner context, so it never runs after the
  window is destroyed.
- Copy distinguishes waiting, unavailable, fault, saved, deployed and confirmed; an accepted RPC is never written as
  "complete".
- Logs record only lifecycle, frozen identity, state transitions, error codes and durations (see
  `docs/reference/logging-events.md`); never an account display name, a complete UID list, a complete RPC, raw OCR
  text, a screenshot, a CDK, a token, an authenticated URL, raw per-hit data or a complete damage table.

## 10. Development and definition of done

- Look at `git status` before changing files and keep others' uncommitted changes; reproduce a defect before fixing
  its smallest cause; a pure documentation task changes no production code.
- Python files under `src/`, `tools/` and `tests/` stay within 800 lines (oversized existing files are only split
  or shrunk); a new file's first line is a Chinese summary; a new `type: ignore` carries the error code and reason;
  key Chinese comments explain identity, units, timing, resource ownership and failure strategy.
- Ruff `E9/F63/F7/F821/F401` is a hard gate; a new dependency updates `pyproject.toml` and `uv.lock` together; the
  test entry point is `tools/quality/run_tests.py` (`core`/`full`).
- By default do not compile or run tests; with authorisation run only what was authorised and report honestly what
  was not run. Separate new failures from existing ones and from environment causes; never delete or skip a test to
  mask a defect.
- Behaviour tests cover calculation, persistence, migration, account isolation, integrity, cancellation,
  after-the-fact confirmation, permissions and operability; they never pin colours, pixels or private widget
  structure. A UI test cleans up only windows it created, after waiting for their background threads
  (`tests/support/qt_cleanup.py`).
- Never commit account databases, WAL/SHM, logs, screenshots, PCAP, OCR temporary files, build/installer output or
  a local SDK. Committing, pushing, releasing, building an installer, deploying components and operating the real
  game all need the user's explicit authorisation; the release preparation entry point
  `tools/release/prepare_release.py` only checks and prints the manual commands.

## 11. Fork: the English interface

Upstream registers all UI text in `assets/locales/zh-CN.json` and projects translations at the Qt display boundary
(`src/ui/common/display_projection.py`), with foreign languages delivered as language patch JSON files. It leaves
game data in Chinese under every language. The fork uses that system as is and adds two things:

| File | What it is | How it is produced |
| --- | --- | --- |
| `assets/locales/en-US.json` | The English language patch, shipped in the release and offered without importing | `python tools/i18n/build_en_patch.py` |
| `assets/locales/game_terms/en-US.json` | Chinese game text → the game's own English (names, skills, set effects, awakenings, monsters) | `python tools/i18n/build_game_terms.py --locres <export>` |

The fork's code footprint is deliberately small, so upstream merges stay cheap:

- `src/integrations/preferences/locale_files.py` — `LocaleFiles` also offers patches shipped in
  `assets/locales/`, with a local patch of the same locale taking precedence; `bundled_game_terms()` loads the map.
- `src/ui/common/display_projection.py` — `set_display_catalog(..., game_terms=)`; a line the catalogue does not
  own is looked up in the game-term map. Game names upstream excludes from UI projection are exactly what this map
  covers.
- `src/ui/app.py` — passes `bundled_game_terms(locale)` into `set_display_catalog`.
- `tests/localization/test_fork_english.py` pins all of the above; `test_language_settings_service.py` has one
  assertion adjusted because English is now always offered.

**The English patch.** `build_en_patch.py` fills each catalogue key, in precedence: an entry already in the patch
that still validates (hand translations are never overwritten); the translation memory
`locales/translation_memory.en.json`, keyed by Chinese source text, on an exact match; the same memory with
placeholders renamed by position when only the parameter names differ; the glossary for a bare game term. Anything
that would fail the catalogue's checks (a `{count:,}` format spec, a stray brace, a parameter mismatch) is left out
to fall back to Chinese. Translate by editing `en-US.json` directly; the translation memory is the pre-2.4.0
English and only seeds keys.

**Game terms are never invented.** The map comes only from the game's own string tables: the UEExtractor CSV of
`pakchunk0-Windows` plus its patch, where the `source` column is the English, joined by the string-table key the
static database stores next to each `X_zh` column, or by an id convention (monster manual ids, Arc descriptions).
A coinage that reads well is still wrong: 蚀心 is `Heartwrench`, not "Mindrot". Hand-verified terms live in
`locales/glossary.en.json`: verified ones under `_meta.official_terms`, unfound ones under
`_meta.unverified_terms`, never mixed. Check new glossary entries with
`python tools/quality/verify_terms.py --locres <export>`. The export is game content and is never committed.
Regenerate the map whenever the static database changes.

Fork gates, on top of section 10: `python -m pytest tests/localization -q`, and
`python tools/i18n/build_en_patch.py --check` (exit 1 means the patch is stale against the catalogue).

## 12. Fork: upstream synchronisation

Branch roles:

- `main` is a pristine mirror of `upstream/main`. Never commit to it — that keeps `--ff-only` working.
- `fork/main` carries the fork's additions and is the branch that gets built and released.

Per upstream release:

```bash
git fetch upstream
git checkout main && git merge --ff-only upstream/main
git checkout fork/main && git merge main
```

**Merge, never rebase**, and keep `git config --global rerere.enabled true` on. Conflicts can now arise only in
the files listed in section 11; resolve them by keeping upstream's change and re-applying the fork's few lines.
After merging:

1. Run `python tools/i18n/build_en_patch.py`. It fills new keys from the translation memory, drops keys upstream
   removed, and reports coverage; translate the remaining new keys in `en-US.json`.
2. If the static database changed, regenerate the game-term map from a current locres export.
3. Run the section 10 gates and the fork gates above, and separate failures that also occur on pristine `main`.
4. Re-translate `AGENTS.md` sections 1–10 from upstream's version; this file is maintained in English, so
   upstream's edits always arrive as whole sections.

History: until 2.3.2 the fork wrapped call sites in its own `tr()`/`display_term()` and kept a source-keyed
catalogue, and each sync cost tens of conflicting files (2.3.0: 63 files, 171 hunks; 2.3.2: 39 files, 100 hunks).
Upstream 2.4.0 introduced its own catalogue and display projection, and merging the old approach would have meant
230 files and 1,392 hunks. The fork therefore took upstream's tree as is and re-attached only the English patch
and the game-term hook.
