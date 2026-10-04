# NTE Drive Calc: development agent contract

This file is the set of cross-cutting hard boundaries — not a page guide, a version table or a todo
list. On entering the repository, look at the current branch, `git status`, the actual code, the
manifests and the database; never infer the implementation from conversation history, an old installer
or a UI screenshot. This file must stay publishable: never record a real account or UID, a credential,
a packet capture, raw screenshot/OCR text, an unredacted log, a private address or a local absolute
path.

> This is a **fork** of `hxwd94666/NTE-Drive-Calculator` that adds Simplified Chinese / English
> localisation. Upstream declined the localisation, so the fork is maintained indefinitely. Sections
> 1–7 mirror upstream's contract in English; sections 8 and 9 are the fork's own.

## 1. Source of truth and documentation ownership

On conflict, the strongest evidence is a passing public behaviour test, a database constraint or an
official protocol; then this contract, then the owning domain document, and only last the UI's
appearance. Versions, schema, capabilities and dataset identity take their numeric truth from the code,
the manifests and the database — never copy a perishable number into this file. An existing cross-layer
call is a legacy fact, not design permission for a new one.

| Topic | Sole owning document |
| --- | --- |
| Layering, composition root, data domains, lifecycle, snapshots | `docs/architecture.md` |
| Delivered user behaviour | `docs/features.md`, `docs/features/` |
| Core, the analysis component, deployment, static builds and other external integrations | `docs/integrations.md` |
| Work modes and capability authorisation | `docs/reference/work-modes.md` |
| Formulas, catalogue fields, growth, battle-report formats and mechanisms | `docs/reference/`, indexed by `docs/README.md` |
| Unfinished capabilities and unverified sources | `docs/roadmap.md`, `docs/roadmap/` |
| Real Windows acceptance | `docs/validation/windows.md` |

Editing a document means overwriting its owning section: delete stale conclusions, duplicated
explanations and phase-by-phase logs. One fact keeps one authoritative statement and every other place
links to it. Delivered behaviour belongs in features, pending work in the roadmap, and hard boundaries
here. The repository keeps no separate release notes; the scope of a release is verified jointly by the
version, the commits, the build inputs and the publishing platform's own information.

## 2. Ownership, layering and account isolation

This repository owns Calc's accounts, interface, configuration, calculation orchestration, process
lifecycle, protocol adapters and presentation. Public capture fixes live in the public fork, and private
analysis and dedicated components in their own integration repositories; here we only consume component
bundles that carry a version, provenance, manifest and hash — never copied private source, never
bypassing the official protocol. `nte-core.exe` and `nte-analysis-core.exe` have independent identities,
capabilities and acceptance. The platform baseline is Windows 10/11, Python 3.11 and PySide6; the entry
point is `main.py`, the composition root is `src/ui/app.py`, and dependencies come from
`pyproject.toml` and `uv.lock`.

The intended dependency direction is
`UI Page/View → Controller → Application Service → Domain/Optimizer or DAO/Integration`. UI holds only
widgets and discardable display state; Controller holds workers, cancellation and narrow navigation;
Service freezes the input and orchestrates transactions; Domain/Optimizer compute purely; DAO
exclusively owns schema, SQL, migrations and consistent backups; Integration exclusively owns external
processes, files, protocols, OCR, input and probing. Shared context, equipment presentation, hotkeys and
the native session are injected explicitly by the composition root. New code adds no service locator, no
dynamic attachment to MainWindow, no cross-feature private call and no lasting old/new dual entry point.
Official IDs, equipment UIDs and `slot_id` are the cross-layer identity; names, nicknames and
`slot_name` are display only. Navigation uses key/`parent_key`.

| Data domain | Ownership and read rules |
| --- | --- |
| `data/game_static.sqlite3` | The main release static; read-only at runtime, owning the complete model calculation needs plus graduation templates |
| `data/role_catalog/` | Standalone `role_page`/`reference` catalogue entries and images; usable for display, read-only browsing and the growth tool, but never a substitute for the full database's character direct damage, equipment scoring, Rust allocation or battle-report input |
| `config/` | Local theme, work mode, plugin and environment preferences; never carried by an account import or export |
| `accounts/<account_id>/user_data.sqlite3` | The current account's snapshots, characters, weights, plans, locks, jobs and battle reports; reached only through the current account context |
| `data/app_shared.sqlite3` | Only the legacy migration data the contract explicitly allows; never overrides official static facts or an account's explicit settings |
| `build/` and temporary directories | Rebuildable output; never a runtime source of truth, account data or release data |

Read priority is the account's explicit configuration → shared data the contract permits → release
defaults. `AppContext.generation` is the account generation. Switching accounts first blocks new
operations and stops the old owners, then replaces the context and advances the generation, rebuilds the
narrow services, clears page caches, and finally resumes only the automatic services explicitly allowed.
Every long task freezes the account, generation, paths, static dataset, inventory `snapshot_id`,
configuration version, target `slot_id`, locks and cancellation token; it re-checks them before
callbacks, preview saves, database writes and external commands, and discards stale results.
Cancellation invalidates only that token, and an owner winds down through the public `close`/`stop`;
exit and mode downgrade first revoke permission for new side effects, then finish within a bound.

Schema and static importer migrations are append-only; a published migration never changes meaning or is
reordered. A change to schema, payload, protocol or error codes must cover a new database, upgrading an
old one, failure rollback and retry, and must not leave a lasting dual read. Multi-table writes go in one
transaction; JSON is replaced atomically through a temporary file in the same directory; a live SQLite
database is only ever copied through a consistent backup, never by copying an active WAL/SHM. An account
export carries only that account's runtime data and the necessary configuration it is allowed — never
another account, logs, caches, captures or credentials. An import validates format, paths, duplicate
members, total size and the user database first, then stages inside the accounts directory, migrates and
switches atomically; a failure keeps the original account, index and session. Deleting, overwriting and
cleaning act on official identity and ownership, never widening scope by display name or extension.

## 3. Source capability, sync and inventory integrity

Offline, low-risk, medium-risk and development are locally confirmed modes; a combo-box draft does not take
effect, and a downgrade revokes side effects first. A first run or an upgraded old configuration defaults
automatic sync to off; before enabling it, check read-only, enable when the conditions hold, and
otherwise offer the matching entry point for handling the problem. Automatic sync only starts and stops
inventory/character listening — it never also starts battle reports, assembly, discard, lock or plugins,
and stopping the listener does not stop an authorised manual battle report, manual character sync or
component management. A high-risk action requires all of: a confirmed mode, no safe pause in effect,
component identity and protocol, that business being ready, and this run's own input evidence. A path, a
file, a process, a connection, a handshake, a declared capability and business readiness never
substitute for one another; waiting, unknown, missing a condition, failed and complete are never written
interchangeably. The details are in `docs/reference/work-modes.md`.

The official inventory's current pointer only ever points at a complete, stable, immutable snapshot. A
candidate must be checked for source, official identity, page/item counts, UID and character
relationships, content fingerprint and a quiet window; it is never completed from a historical maximum
count, a default zero, an older snapshot or a different source. `unknown`, `partial`, `complete=false`,
a missing page, a revision change or a field conflict all mean no commit. Downstream work resolves
`snapshot_id` once at the start and every plan keeps its own `source_snapshot_id`; a runtime delta only
changes the state of UIDs already known in a complete native snapshot, never adding to the set or
advancing the pointer.

Source capability is decided by the public helper: native `nte_core` supplies official UIDs, character
instances, equipment relationships, state and native writes only when the business capability and
completeness evidence both hold; packet capture can supply a complete inventory and battle-report facts
but never fakes native character instances, equipment writes or DLL readiness; a vision source supports
analysis, appraisal and ordinary mouse assembly, and while its state is unknown it performs no
lock/discard and no fast assembly. A historical snapshot, a battle-report frozen subset, a
graduation-template assumption and a user edit copy are none of them the current complete inventory.
Re-syncing keeps the saved inventory and plans and discards only uncommitted candidates; not logged in,
waiting for the game and initialising are waiting, while protocol and integrity errors are failures.

Character sync reuses the existing game-data session and only overwrites the permanent fields this run
supports and has confirmed; a missing character, an unknown field, a trial/temporary character and a
relationship conflict all keep the old value. An old Arc is cleared only on an explicit "no Arc
equipped"; skills match on the official SkillID; and an awakening level bonus is never written back into
the base level. A failing field group is skipped; an incomplete read, a cancellation, a stale generation
or a write failure means this run commits nothing at all and never alters a historical battle report.
The details are in `docs/features.md`.

## 4. Calculation, characters and external side effects

A calculation freezes the account, generation, complete inventory, main static dataset, character
order/equal-priority groups, effective panel, target slot, locks, configuration and the combination
budget, and produces an immutable preview. Saving consumes only that preview and re-checks the
boundaries, never filling gaps from "the latest state". The only allocation strategy is character
priority; a real UID is never consumed twice across characters and slots, locked UIDs are excluded
first, and a virtual placeholder scores zero. Cancellation runs through enumeration, recovery and
submission, and a failure never overwrites an existing plan. Equipment base scoring goes only through
`ScoringEngine.calculate_drive_score` / `calculate_cartridge_score` or a formula-free adapter over them;
the per-item `assignment_scores` is a plan's frozen fact, recomputed through the same engine only when an
older plan lacks it. Conditional Arc effects do not enter the permanent panel; the shared character panel
uniformly handles level/ascension, Arc, affinity, furniture, awakenings, skills and the CRIT boundaries.
`slot_id` is the stable identity across a character's several plans, and a locked plan must not be
deleted, overwritten, archived or lend out its UIDs; a Calc plan lock is not the game's lock RPC.
Graduation rates and formula conventions are in `docs/features.md` and `docs/reference/`.

External writes (warehouse state, fast or in-game assembly, rewind and so on) follow "plan → freeze →
dispatch → confirm afterwards". The plan carries the subject, the expected state, the source and the
idempotency boundary; before dispatch it re-checks the account generation, snapshot, capability, game
context and cancellation. Only a busy state that definitely did not dispatch may be retried, within a
bound; a timeout or an unknown stops, and an action that may already have run is never re-sent. An
accepted RPC, a button state and a live process are none of them business success — success is confirmed
by a new complete snapshot or an official scoped event. A failure keeps the old persistent facts and
releases temporary files, input state, leases and workers. A vision scan commits a complete result in one
transaction, and cancellation, a count anomaly or an input failure leaves nothing half-finished; the
global stop key is responsible for releasing game input. Fast assembly uses only official native UIDs,
character instances and saved slots; vision assembly uses only the vision projection.

The growth calculator reads frozen static catalogue data and the page's draft, and never writes back to
the character profile, the inventory or a stamina estimate. Total materials, what is already held,
crafting and confirmed dungeon stamina are expressed separately; only confirmed same-family materials
combine 3:1 upwards, experience materials are not converted, Fons is not a stamina target, and missing
drop evidence stays unknown. See `docs/features/tools-and-catalog.md` and
`docs/reference/progression-stamina-calculator.md`.

Raw battle-report capture saves only the summary, record, axis, per-hit data and explicit observations
Core actually provided; it never guesses crits, buffs, teams, targets or the scene from an aggregate, and
the raw facts are immutable. Settlement freezes this match's character and equipment subset, carries no
full inventory, and does not follow later configuration changes. An edit copy serves only that match's
replay and counterfactuals and never changes measured damage, DPS or the timeline; derived results carry
an algorithm version, static identity, confidence and provenance, and unknown is never disguised as zero.
Battle-report page analysis goes only through the standalone `nte-analysis-core.exe` read-only interface,
and a missing manifest, hash, protocol, version or page capability means no fallback to reading the
database from Python; requests and caches bind to the account generation and the frozen input. See
`docs/features/battle-report.md`.

## 5. Components, static builds and releases

Npcap, Core, the analysis component, the DLL/Loader, OCR and game input are managed by Integration.
Promoting a component records its upstream version, commit, licence and SHA-256; the DLL, Loader,
scripts, resources and protocol are one set of inputs and are never replaced piecemeal. A delivery
contains no private source, PDB, account, credential, capture or sensitive log. The game path must be a
verified absolute path to `HTGame.exe`, and automatic discovery saves only a single valid candidate; the
game running, an unknown path, a file in use or insufficient permission is waiting or failure, and the
game is never force-closed. Deployment and cleanup judge by the exact file, the owning directory, the
official record, whole-bundle identity, write integrity and the target being unchanged for the duration;
a manual cleanup missing its record file still requires a hash match against a verified component, and
unknown files and links are kept. A stale old path is handled from its original record, the Loader winds
down independently, and the registry serves only limited discovery and cleanup of already-registered old
workspaces. The details live only in `docs/reference/game-component-bundle.md`.

The main static database is built only as a candidate under `build/` by `tools/game_data/`, through
normalisation, post-processing and validation, and is promoted only by `promote_static_release.py` after
it verifies provenance, schema/importer, hashes, foreign keys, integrity and the manifest; never
overwrite `data/` directly and never treat unpacked Content as a normalised result, and a semantic change
increments the importer. When combat sources are insufficient, a standalone `role_page` or `reference`
catalogue may be built, recording provenance and hash per file; that standalone directory may serve
display and growth but must never fill in fields the main database's calculation or battle reports are
missing. Catalogue entries are promoted as a set and old previews are recomputed when the dataset
changes. Static compression is proven table by table to be logically equivalent, inside an isolated
candidate only; installer resource de-duplication applies only to byte-identical catalogue images; and
runtime pruning follows an exact manifest plus a packaging smoke test. A build, a component promotion, an
installer, real-hardware acceptance and a release are distinct states and never substitute for one
another.

## 6. UI, logging and observability

A new dialog is bounded by `src.app.window_geometry` to the current screen's available area and centred
relative to its owner, covering mixed DPI. An important prompt reads "state → cause → next step"; a
problem offers only the matching entry point for handling it, a ready state is not pushed with heavy
guidance, and synonymous buttons and piled-up diagnostics in the body are avoided. A warning defaults to
cancel and uses the system alert sound; colours, disabled/selected/focus states and widget operability
are checked in all three themes. A status label belongs only to the operation's owner. User-facing text
distinguishes waiting, missing a condition, failed, saved, deployed and confirmed afterwards; "not
detected" is never written as "missing", and an accepted RPC is never written as "complete". Diagnostic
detail and structured logs keep the troubleshooting evidence rather than dumping a raw exception into the
user's prose. The rules are in `docs/reference/logging-events.md`.

Logs record lifecycle, frozen-identity categories, state transitions, error codes and durations first.
Local fault diagnosis may keep the file paths, exception types and call sites it needs, and that is not a
licence to record an account display name, a complete UID list, a complete RPC/payload, OCR, a
screenshot, raw per-hit data, authentication material or a complete damage table. File paths help a user
troubleshoot, but copying or sending a log onward should prompt a check first. The persistent log belongs
to the current account and switching accounts ends the old session; the verbose log carries its own
timestamp. Logs, screenshots and captures are not a source of account truth and never enter the default
export or a release artefact.

## 7. Development order and completion gates

Before starting, establish the input/output data domain, the source capability, the frozen identities,
the external side effects, failure rollback and the verification evidence. Reproduce a defect first and
fix the smallest business cause; a product semantic change proceeds as "public behaviour tests →
contract/docs → Domain/Service → DAO/Integration → Controller/UI → close off the old entry point →
targeted verification → core/full plus static checks". A pure documentation task does not take the
opportunity to change production code. Look at `git status` before moving files, and protect other
people's uncommitted work.

A new or modified Python file under `src/`, `tools/` or `tests/` must not exceed 800 lines; an existing
oversized file may only be split or shrunk when touched. A new Python file's first line is a Chinese
summary comment; a new `type: ignore` carries the error code and a reason. Ruff `E9/F63/F7/F821/F401` is
a hard gate, and a new dependency updates `pyproject.toml` and `uv.lock` together. The quality entry
point is `tools/quality/run_tests.py`, where `core` covers the critical boundaries and `full` is the
complete discovery; long-lived behaviour tests verify identity, integrity, concurrent cancellation,
after-the-fact confirmation, account isolation, visible semantics and operability, and never pin colours,
pixels or private widgets. A stale test is rewritten or deleted rather than kept alive by a compatibility
shim for a retired entry point. By default do not compile and do not run tests; with the user's explicit
authorisation, run only what was authorised, distinguishing targeted checks, core/full, static checks,
packaging and real Windows acceptance. Separate new failures from existing ones, from optional-component
causes and from environment causes, and never mask a defect by deleting or skipping a test.

Never commit the account database, WAL/SHM, logs, screenshots, PCAP, OCR temporary files,
build/installer output, a local SDK or a dump. Committing, pushing, releasing, building an installer,
deploying an external component and operating the real game each need explicit authorisation. The release
preparation entry point `tools/release/prepare_release.py` only performs local checks and prints the
manual commands for a maintainer; before an official release, verify the version, dataset, component
manifest, upgrade and rollback, a clean install, all three themes, account switching, both kinds of sync,
calculation/save/assembly, deployment and cleanup, and a real Windows smoke test. A release build refuses
a missing or incompatible analysis component, and a capability not verified on real hardware must never
be marked stable.

## 8. Localisation

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
- **Long-form game text** uses `display_text(text_table, text_key)`, which resolves the string-table key
  the static database stores against `locales/gametext.en.json`. That catalogue is generated by
  `tools/game_data/build_game_text_locale.py` from a locres export, so skill names, skill descriptions
  and awakening text need no hand translation and a newly released character arrives on its own.
- Fields for which nte-core already supplies `names`/`suit_names` (`en`/`ja`/`zh_cn`) use
  `display_localized()` instead of a glossary entry.

A game term's English is never invented. Look it up in the game's own string tables — the UEExtractor
CSV of `pakchunk0-Windows` plus its patch, where the `source` column is the English — and reverse-look
it up by the internal id from `game_static.sqlite3` rather than by meaning. A coinage that reads well is
still wrong: 蚀心 is `Heartwrench`, not "Mindrot"; 争锋赏宴 is `Hunter's Crucible`, not "Contest Feast".
A term joined to a locres key is recorded in `glossary.en.json` under `_meta.official_terms`; one that
cannot be found goes in `_meta.unverified_terms` and never sits with the verified ones. The procedure
and the namespaces worth searching are in `docs/reference/localization.md`.

Two values must stay Chinese even though they reach a widget. A short source string is an ambiguous
catalogue key — `"中"` is already `"of"` from another fragment — so a one-character value is translated
at the render site under a disambiguated key, never as a bare key. And a value the code compares with
`==` or `in` is a key, not copy: the confidence levels `高`/`中`/`低`/`未解析`, `err == "任务已取消"`,
and match specs such as `PASSIVE_ANY_HIT|...,覆纹,weave`.

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

Localisation gates, on top of section 7:

- `tests.test_i18n` — `test_every_tr_key_resolves` fails on a `tr()` key missing from `locales/en.json`.
- `python tools/quality/i18n_coverage.py --scope ui` finds Chinese handed to a widget that was never
  wrapped at all. The test suite cannot see that.
- `tests.test_i18n_sync_status` covers the sync status line, which renders `tr(state.message)` fed by
  `_publish` literals, native status dicts and the text of every `NativeSnapshotPending` raised anywhere.
  Those exceptions stay Chinese because they are logged; a new one only needs its `en.json` entry.
- A new game term in `locales/glossary.en.json` is checked with
  `python tools/quality/verify_terms.py --locres <export>`. The export is game content and is never
  committed, so this is a manual check; nothing else can tell a coined name from a real one.

## 9. Upstream synchronisation

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
edits, and the cost grows with the release: 2.2.0 produced 27 conflicting files across 81 hunks, 2.2.1
produced 12 across 22, and 2.3.0 produced 63 across 171. Almost every hunk has the same shape, upstream
having changed a line the fork had wrapped:

```text
ours   (the fork): setText(tr("⏳  扫描中... ({key} 停止)", key=...))
theirs (upstream): setText("⏳  扫描中... (F12 停止)")
```

Resolve by taking upstream's text and re-applying the `tr()` wrapper, then adding the new Chinese source
string to `locales/en.json`. Resolve **hunk by hunk**, never with `git checkout --theirs`: that replaces
the whole file and silently drops the fork's localisation in every region that merged cleanly. In 2.3.0
the difference was 1306 lost translator calls versus 353.

Three failure modes recur and none of them is caught by `git`:

- **A dropped import.** Upstream's hunk replaces the import line and the fork's `from src.i18n import …`
  goes with it, while the usages elsewhere in the file merged cleanly. Audit every conflicted file for a
  translator used but not imported; in 2.3.0 that was 8 files.
- **An orphaned parenthesis.** A `tr(` opener living outside the conflict hunk leaves its closing
  parenthesis behind when our side is discarded. `compileall` catches it; `ast.parse` does not.
- **A broken fork-only invariant.** 2.3.0's hunk for `equipment_presentation.py` dropped `main_key` but
  kept the line deriving the percent suffix from it — the section 8 rule, silently undone.

After every sync, run the gates in section 7 **and** `i18n_coverage.py --scope ui`.

A clean coverage report is not proof. The scan follows a Chinese literal only while it is a direct
argument of a known sink, and three shapes escape it, all of them found in shipped code rather than by
the gate:

- **Display metadata.** The copy is a field of a frozen dataclass — `NavItem`, `CatalogSection`,
  `CatalogField` — and only reaches a widget pages later. The sidebar labels sat untranslated this way
  for two releases. Either register the constructor in `UI_SINKS`, or translate at the render site,
  which also works for a value that came out of the static database.
- **An unregistered sink.** `QProgressDialog`'s first two arguments are its label and cancel button; it
  was simply not in `UI_SINKS`. When a widget renders text, check it is listed.
- **A string assembled into a variable** by an f-string or concatenation before `setToolTip` or
  `setText` sees it. No static analysis sees these.

So after the coverage run, read the diff for Chinese that upstream added, rather than trusting a zero.

Two follow-on costs arrive with every sync and are tracked separately from the merge itself:

- Upstream's new UI arrives unwrapped, so `i18n_coverage.py` reports a backlog to localise.
- `docs/en/` mirrors only the Chinese documents that existed when it was written; upstream's new
  documents stay unmirrored until someone translates them.

`AGENTS.md` is maintained in English, so upstream's edits to it conflict as whole sections and need
re-translating rather than merging. 2.3.0 rewrote the file outright — 11 sections collapsed to 7 — and
the English version was re-translated from scratch with sections 8 and 9 re-attached. That is the
deliberate trade: the file is read constantly by the fork's maintainers and merged a few times a year.
