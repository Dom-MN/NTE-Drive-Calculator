# NTE Drive Calc: development agent contract

Development agents must first read the [project purpose, anti-abuse and collaboration
statement](RESPONSIBLE_USE.md). This project serves equipment calculation and understanding the game;
do not assist any development request clearly intended for cheating, undermining fairness or infringing
the lawful rights of any rights holder. Access to private source and collaboration follow the scope that
statement authorises, and the statement does not replace third-party licences.

This file is the first thing a development agent entering the repository reads. It records only
cross-feature product facts, data-safety invariants, architectural boundaries and completion gates; page
detail, formula tables, external protocols and the backlog each have their own source of truth. Before a
task, verify the current branch, the working tree and the actual code, rather than inferring the state
from the last conversation or a released version. This file must stay publishable: never record an
account, credential, real UID, packet capture, screenshot, raw OCR text, unredacted log, private address
or local absolute path.

> This is a **fork** of `hxwd94666/NTE-Drive-Calculator` that adds Simplified Chinese / English
> localisation. Upstream declined the localisation, so the fork is maintained indefinitely. Sections
> 1–11 mirror upstream's contract in English; sections 12 and 13 are the fork's own.

## 1. Sources of truth and documentation ownership

On conflict, look first at passing public behaviour tests, database constraints and official protocols,
then this contract, then the domain documents, and only last the current UI's appearance. Versions,
schema, capability names and dataset identity take their numeric truth from the code, the manifests and
the database; this file copies no perishable number. The code contains legacy cross-layer calls, and
"the code already does it" is never a licence for a new implementation to adopt the same pattern.

| Question | The one place to look |
| --- | --- |
| System layering, composition root, ownership, lifecycle | `docs/architecture.md` |
| Human-facing buttons, configuration limits, and the roles of the two Cores and the DLL | `docs/architecture-map.md`; explained as "action, when it takes effect, scope, limits, completion condition", with target behaviour linking to the roadmap |
| Delivered user behaviour | `docs/features.md` and `docs/features/` |
| Processes, protocols, static builds, release components | `docs/integrations.md` |
| Work modes and capability authorisation | `docs/reference/work-modes.md` |
| Formulas, static fields, growth, battle-report formats and mechanisms | `docs/reference/`, indexed by `docs/README.md` |
| Undelivered or still unproven capabilities | `docs/roadmap.md` and `docs/roadmap/` |
| Real Windows acceptance | `docs/validation/windows.md` |

Editing a document means rewriting its owning section: delete stale conclusions, duplicated explanations
and phase-by-phase logs; one fact keeps one authoritative statement and everything else links to it.
Delivered behaviour goes into features, unfinished work into the roadmap, and hard boundaries stay here.
The repository keeps no separate release notes; a release's scope is confirmed jointly by the version,
the commits, the build inputs and that release's publishing-platform information.

## 2. Product capability map and semantic boundaries that must not be crossed

| Domain | Product responsibility | Boundary that must hold |
| --- | --- | --- |
| Accounts and dashboard | Account switching, stable snapshot summary, sync status, shortcuts | Account data is isolated; switching stops the old tasks and advances the account generation first |
| Work modes | Four local modes: offline, low risk, medium risk, development | The combo box is only a draft and takes effect once the user confirms; a downgrade revokes side-effect permission first |
| Game data sync | Collecting inventory and character state by capture or natively | Automatic sync starts only sync, never also battle reports, assembly, discard, lock or plugins |
| Calculation and allocation | Character-priority allocation, preview and save on a fixed inventory | Every input is frozen; saving consumes only that preview and never fills gaps from "the latest state" |
| Characters | Level, ascension, skills, affinity, furniture, awakening, Arc and weights | Native sync overwrites only proven fields; missing and unknown keep the old value |
| Loadouts | Game loadouts, calculated loadouts, multiple slots, locks, replacement, stat summary | `slot_id` is the identity; each plan keeps its own source snapshot |
| Warehouse and appraisal | Fixed-inventory browsing, state management, screenshot/clipboard/manual appraisal | A vision inventory never reads or changes the game's lock/discard; appraisal writes neither inventory nor loadout |
| Scanning and input | Full scan, in-game assembly, rewind and so on | A complete result commits once; cancellation, a count anomaly or an input failure leaves nothing half-finished |
| Fast assembly | Batch assembly from native UIDs, character instances and saved slots | An accepted command is not success; while the result is unknown before a new confirmed state, nothing is resent automatically |
| Battle reports | Raw capture, frozen facts, history and standalone analysis | Raw facts are immutable; derived results carry a version and provenance; unknown is never disguised as zero |
| Plugins | Skill cooldown and enemy status HUD | The two cards keep their state independently; turning a plugin off never starts or stops a battle report |
| Tools and catalogue | Rewind, growth calculator, read-only static catalogue | The dataset is frozen; the growth calculator writes no character profile, inventory or stamina estimate |
| Environment and updates | Paths, components, runtimes, deployment, cleanup, mirror updates | Path, file, process, handshake, capability and business readiness are judged separately |

The exact capability set, prompts and automatic-sync boundary of each work mode are defined in
`docs/reference/work-modes.md`. A high-risk action requires all of: a confirmed mode, no safe pause in
effect, a valid component identity and protocol, the matching business capability being ready, and this
run's complete input evidence. A file existing, a process alive, a connection made, a handshake passed, a
capability declared and the business available are six different states.

## 3. Repository responsibility, layering and identity

This repository is Calc's product and integration side: it owns account data, the interface,
configuration, calculation orchestration, process lifecycle, protocol adapters and result presentation.
Public capture fixes live in the toolkit's public fork; private analysis and dedicated components in
their own integration repositories. This repository consumes only component bundles that carry a version,
provenance, manifest and hash, never copies private source and never substitutes a bypass for the
official protocol. `nte-core.exe` handles capture and game interaction and `nte-analysis-core.exe`
handles battle-report analysis; their identities, capabilities, deployment and verification are
independent.

The platform baseline is Windows 10/11, Python 3.11 and PySide6. `main.py` is the entry point and
`src/ui/app.py` the composition root. Dependencies come from `pyproject.toml` and `uv.lock`, and the
application version from `src/app/version.py`. The intended dependency direction:

```text
UI Page/View → Controller → Application Service → Domain/Optimizer or DAO/Integration
```

- UI owns only widgets and discardable display state; Controller owns workers, cancellation, page
  projection and narrow navigation, and implements no formula, SQL or data compatibility.
- Service freezes the request and orchestrates transactions across DAO/Integration; Domain/Optimizer
  compute purely and read no Qt widget, file, process or database.
- DAO exclusively owns schema, SQL, migrations, transactions and consistent backups; Integration
  exclusively owns processes, files, protocols, OCR, input and system probing.
- `AppContext`, `EquipmentPresentation`, the global hotkeys and the shared native session are created by
  the composition root and injected explicitly. New code adds no service locator, no dynamic attachment
  to MainWindow, no cross-feature private call and no lasting old/new dual entry point. Where legacy code
  violates the layering, converge it within the task's boundary rather than widening the dependency.
- Cross-layer relationships connect through the official `character_id`, `item_id`, `suit_id`,
  `shape_id`, `property_id`, equipment UID and `slot_id`; Chinese names, nicknames and `slot_name` are
  display only. Navigation locates by key/`parent_key`, never by page number or by walking widgets.

The main line and external component branches must both be re-verified against the actual Git ref and
manifest. A source merge, a successful build, a component promotion, a successful package and real-game
acceptance never substitute for one another.

## 4. Data domains, frozen identity and account lifecycle

| Data domain | Ownership and read rules |
| --- | --- |
| `data/game_static.sqlite3` | The main release static: growth, skills, formulas, enemies, offline weights and graduation templates; read-only at runtime |
| `data/role_catalog/` | The standalone character/catalogue directory; its purpose identity is `role_page` or `reference`, carrying a database, images and a manifest, and it never automatically replaces the battle-report dataset |
| `config/` | Local theme, work mode, plugin and environment preferences; never carried by an account import or export |
| `accounts/<account_id>/user_data.sqlite3` | The current account's private snapshots, characters, weights, slots, plans, locks, jobs and battle reports; reached only through the current account context |
| `data/app_shared.sqlite3` | Only the legacy migration data the contract explicitly allows; never overrides official static data or an account's explicit configuration |
| `build/` and temporary directories | Rebuildable runtime/build output; never the current source of truth, and never sent out with an account or a release |

Read priority is the account's explicit configuration → shared data the contract explicitly permits →
release defaults; the local ownership of theme, mode and plugins follows their own documents.
`AppContext` is the single composition root for paths and account state, and `generation` is the
account generation. Switching runs: block new operations, stop the old account's owners, replace the
context and increment the generation, rebuild the narrow services, clear page caches, and resume only
the automatic services explicitly allowed.

Every long task, when created, freezes the account, generation, paths, static dataset, `snapshot_id`,
configuration version, target `slot_id`, lock snapshot and cancellation token, and re-checks them before
callbacks, preview saves, database writes and external commands. A stale result is discarded silently: it
writes nothing to the new account and refreshes no new page. Cancellation invalidates only this token;
the owner winds down through its public `close/stop`. Account switching, a mode downgrade and exit first
revoke permission for new side effects, then wait a bounded time for the task to finish.

SQLite schema and static importers use append-only migrations; a published migration file is never
given a new meaning or reordered. A change to schema, payload, protocol or error codes covers a new
database, upgrading an old one, failure rollback and retry after repair, never kept compatible by a
lasting dual read in the UI. Multi-table business writes go in one transaction; JSON configuration is
written to a temporary file in the same directory and replaced atomically; a live SQLite database is
backed up only by a consistent backup, never by copying an active WAL/SHM.

An account export contains only the account's runtime data, the necessary configuration and the baseline
resources the contract allows; never logs, caches, captures, credentials or another account's data. An
import first validates the format, member paths, duplicate members, total size and the user database,
then stages inside the accounts directory, migrates and switches atomically; a failure keeps the original
account, index and current session. If an existing flow lacks any of these gates, add the gate rather
than treating the existing behaviour as proof of safety. Deletion, overwriting, archiving and cleanup act
by official identity and ownership, never widening scope by display name or a single extension.

## 5. Source capability, inventory integrity and static data

The main static database is built only as a candidate under `build/` by `tools/game_data/`, through
normalisation, any necessary post-processing and validation, then promoted atomically by
`tools/game_data/promote_static_release.py` after it checks, against the local configuration, the source
hashes, schema/importer, foreign keys, integrity, size and the manifest. Never overwrite `data/`
directly and never take unpacked Content wholesale as a normalised result; a change to normalisation
semantics increments the importer version.

When the same version's combat sources are insufficient, a standalone `role_page` or `reference`
catalogue may be built, recording provenance and hash per file in an explicit priority order.
`reference` may serve as one complete static input for equipment scoring and allocation; one calculation
uses only one validated directory and never reads it mixed with an old main database. The catalogue
grants no new damage formula, graduation template, battle report or native sync capability. A catalogue
directory is installed as a set only through the official promotion entry point; after a data update, old
previews have to be started again.

The inventory's current pointer only ever points at a complete, stable, immutable snapshot. Downstream
work resolves `snapshot_id` once at the start; a plan always reads its own `source_snapshot_id`. The
stabiliser checks completeness, official identity, count consistency, UID/character relationships and
the content fingerprint, then waits for a quiet window; it never guesses completeness from a historical
maximum count. A runtime delta only overlays the state of UIDs known in an official complete snapshot,
and a partial event adds nothing to the set and never advances the current pointer.

Source capability is decided by the public helper, which passes coverage and unknown values on to the
consumer:

- `nte_core` supplies official UIDs, character instances, equipment relationships, lock/discard state and
  native writes only when the capability and completeness evidence both hold.
- Packet capture can produce a complete inventory and battle-report facts, but never fakes native
  character instances, equipment writes or DLL business readiness.
- A vision source can analyse, appraise and perform ordinary mouse assembly; while its state is unknown it
  disables lock/discard, never enters fast assembly and never fakes reliable character ownership.
- A historical snapshot, a battle-report frozen subset, a graduation-template assumption and a user edit
  copy are none of them the current complete inventory, and are never promoted to the official inventory
  or given real UIDs.

`unknown`, `partial`, `complete=false`, a missing page, a revision change and a field-mapping conflict
all mean the official set is not committed; native gaps are never silently filled from an old snapshot, a
fixed count, a capture result or a default zero.

## 6. Calculation, characters, scoring and loadouts

A calculation freezes the account, generation, inventory snapshot, static dataset, character
order/equal-priority groups, effective panel, target slot, locks, configuration and combination cap, and
produces an immutable `WeightedAllocationPreview`. Saving consumes only that preview and re-checks the
frozen boundaries before committing. Candidate construction excludes locked real UIDs first; sets, main
stats, rarity, stat priority and the blacklist share one contract. A real UID is consumed only once across
all characters and slots; a virtual placeholder scores zero and takes no part in locking, lending or fast
assembly. Cancellation runs through enumeration, reservation, recovery and submission, and never
overwrites an old plan.

The only allocation strategy is character priority. An equal-priority group is allocated jointly by
actual score; a higher-priority character's strictly equal-scoring candidates defer their ownership with
the slot as the smallest unit. Top-K only detects reservation back-fill conflicts; recovery still does a
one-to-one matching and re-checks shape, set, locks, UID/cartridge uniqueness, the CRIT cap/floor and stat
constraints. A single character's or group's failure only invalidates that result and never interrupts
the following characters.

The only formula entry points for equipment base scoring are `ScoringEngine.calculate_drive_score` and
`ScoringEngine.calculate_cartridge_score`. Calculation, game/calculated loadouts, cards, rewind and
official character base scoring call the same engine or a formula-free adapter, never copying the
formula. A saved plan's `assignment_scores` are the frozen fact behind per-item and cumulative scores;
only an older plan missing them is recomputed through the same engine. A newly generated equipment-change
comparison uses the scoring basis frozen by this calculation on both sides and saves the comparison
scores separately, never overwriting an old plan's historical scores; changing weights after a
calculation does not reinterpret an existing preview. Replacement optimisation may sort by the current
character's direct-damage marginal dynamic weights, while every other case uses base weights; a custom
character without an official model uses base weights too.

Official characters default to the release static graduation template, with the account's explicit
configuration taking precedence. The effective character panel uniformly consumes level/ascension, Arc
level/ascension, unconditional permanent stats, affinity 10, furniture, specific awakenings and skill base
levels. Base CRIT Rate, CRIT DMG, the character CRIT cap and its deductions are computed only in the
shared character panel service; calculation, graduation rate and loadout summaries consume the same
projection. Conditional Arc effects enter neither the permanent panel nor base allocation scoring.

After new or updated Arc data is imported, and before the static candidate is promoted, review each Arc's
refinement curves, effect sources and evidence for unconditional permanent stats. An Arc whose evidence
closes generates its permanent stats at every refinement level and has its projection checked; an Arc
with clearly no permanent stat, only conditional effects, missing evidence or ambiguity has that review
conclusion recorded. Never fabricate permanent stats from description text, a default template or zero;
a new Arc whose review is unfinished must not be promoted as data with complete permanent stats.

`slot_id` is the stable identity across one character's several plans, and `slot_name` is display only.
Each plan keeps its own source snapshot and frozen scores; only different characters' current slots
referencing the same real UID is a conflict. A Calc plan lock is not the game's lock RPC; a locked plan
must not be deleted, overwritten, archived or lend out its UIDs. `EquipmentPresentation` is the shared
display entry point for equipment cards, stat colours, scores, gains and differences.

## 7. Tools, sync, scanning and external writes

The dashboard's automatic sync preference is independent of mode authorisation: stopping the listener
does not stop a manual battle report, manual character sync or authorised component management. Low risk
uses packet capture and medium risk the native DLL; in development mode the official inventory is still
written by the DLL, and capture serves battle-report comparison. Re-syncing keeps the saved inventory and
plans and rebuilds only uncommitted candidates. Not logged in, waiting for the game and initialising are
waiting; protocol or integrity errors are specific faults.

Character sync reuses the running game-data session and opens no second connection. It commits only the
supported permanent fields this run returned; an unreturned character, an unknown field, a trial/temporary
character and a relationship conflict keep the old configuration. An old Arc is cleared only on an
explicit "no Arc equipped"; skills match on the official SkillID, and an awakening level bonus is never
written into the base level again. A field group failing format or relationship validation is skipped and
the other confirmed fields are saved in one transaction; an incomplete read, a cancellation, a stale
generation or a write failure means this update commits nothing at all and never alters a historical
battle report.

The growth calculator reads frozen static data and the user's current input; single/multi-character
targets and the held-materials draft are never written back to the character profile or inventory.
Results distinguish total materials, deductions for what is held, crafting conversion and the stamina
that can be inferred from dungeons; the stamina-only view excludes Fons, whose main sources are not
dungeons. Three-lower-for-one-higher conversion is used only along confirmed same-family material chains,
and character and Arc EXP materials are never converted. Dungeon drops, appraisal level and stamina
inference are expressed within the observable range in
`docs/reference/progression-stamina-calculator.md`, and stay unknown without drop evidence.

Warehouse lock/discard, fast assembly, in-game assembly, rewind and other external writes follow "plan →
freeze → dispatch → confirm afterwards": the plan states the subject, the expected state, the source and
the idempotency boundary; before dispatch it re-checks the account generation, snapshot, capability, game
context and cancellation; only a busy state that definitely did not dispatch is retried, within a bound;
a timeout or an unknown result stops what follows and never resends an action that may already have run.
Success is confirmed by a new complete snapshot or an official scoped event; an accepted RPC, a button
state and a live process are none of them business success. A failure keeps the old persistent facts and
releases temporary files, input state, leases and workers.

The warehouse reads a fixed snapshot; "discard" sets the game's flag and deletes no equipment. Vision
scanning, appraisal, rewind and in-game assembly hook into the application-level stop key and release
mouse, keyboard, gamepad and window state. Fast assembly consumes only native official UIDs, character
instances and saved slots; vision assembly uses the vision projection; both freeze the account, source
and token and block account switching while running. Rewind reads the fixed inventory, each
participating character's explicitly chosen slot with its source plan and frozen per-item scores, and
solves only on an explicit "generate recommendation"; an unchosen backup plan takes no part in
validation or the shortfall total.

## 8. Battle reports: raw facts, derived results and standalone analysis

The capture layer saves only the summary, record, axis, raw per-hit data and explicit observations Core
gave; it never guesses crits, Buffs/Debuffs, shields, healing, a complete team, enemy instances or the
scene from an aggregate summary. A battle report freezes, at its start, the account generation, static
dataset, the fallback inputs the account allows and the source capability. Packet capture freezes the
settlement loadout from the database at the end, for the characters it observed; native capture freezes
the team, characters, equipment and environment evidence independently at each half's first hit. Once
frozen, it does not follow later inventory or configuration changes.

When a battle report ends it saves only the character panels and equipped items that attempt needs,
carries no full inventory and does not rely on the inventory snapshot continuing to exist. Where native
first-hit calculation input is missing, it falls back per character, growth or equipment field group to a
frozen copy from the settlement database, recording the source and the reason; it never overwrites
existing native input, fabricates historical Buffs or alters the first-hit raw evidence. Once the first
settlement is frozen, a retry does not change the input. Edit and marginal candidates are frozen once from
the current stable inventory when the page opens. Without an official native inventory, the release's
graduation template may serve only as a clearly labelled battle-report calculation assumption; it never
enters the official inventory and produces no UID.

The original character/equipment snapshot is immutable. An edit copy is account-private, single-match
and the single active copy; it takes part only in fixed-axis replay and counterfactual analysis, never
changing measured damage, DPS, the timeline or the original facts. Environment inference,
user-confirmed environment, target profiles, Buff audit, healing and marginal results are all derived
data carrying an algorithm version, static identity, confidence and provenance; unknown never becomes
zero, a multiplier of one or "complete". The import/export format is in
`docs/reference/battle-report-package.md`.

Battle-report page analysis goes only through the standalone `nte-analysis-core.exe` read-only database
interface. A missing manifest, hash, protocol, engine version or required page capability means no
fallback to reading the database from Python. Requests freeze the account, battle-report ID,
database/configuration paths, static dataset, analysis range and user candidates; caches belong only to
the current account session, become invalid when the identity changes and write no raw fact. A capture
stop timeout terminates that Core run and discards unfinished staging; an empty battle report never waits
indefinitely for an axis.

## 9. Components, deployment, static promotion and release slimming

Npcap, Core, the standalone analysis component, the native DLL/Loader, OCR, mouse/gamepad and game input
all belong to Integration. Promoting a component records its upstream version, commit, licence and
SHA-256; the DLL, Loader, scripts, resources and protocol are one set of inputs and never replaced
piecemeal. A private delivery contains only verified executables, public scripts/resources, the component
manifest and licence notices; source archives, PDBs, account data, credentials, captures and sensitive
logs go into neither the repository, the installer nor attachments.

The game path must be a verified absolute path to `HTGame.exe`; automatic discovery saves it only when
there is a single valid candidate. Automatic deployment manages only the components verified in the
current release bundle and the local loading method chosen, and never raises work-mode permission. After
the game exits, deployment/upgrade replaces by the exact component file names in the official directory,
without requiring the old file's hash to be recorded; the bundled whole-set identity, write integrity and
the target being unchanged during the operation are still verified. When the program exits explicitly or
runs a recorded safe cleanup, it winds down by the official cleanup contract, by owning directory and exact
program file name. The game running, an unconfirmed path, insufficient permission or a file in use enter
an explicit waiting/fault state, and the game is never force-closed. A stale old deployment path is still
handled from its original recorded absolute directory; the Loader winds down independently. The registry
and common directories serve only limited discovery, never a recursive disk scan or deletion of an
unverified directory. Details are in `docs/reference/game-component-bundle.md`.

The analysis component must be deployed as a set with its executable, `component.json` and licence; the
manifest hash, engine version and page capability together make up compatibility. The mirror update chain
handles version checking, download, cancellation and launching the installer separately; a failure keeps
the old runnable version and a retryable state, and never records an authenticated URL, token or CDK.

Static database size optimisation repacks only in an isolated candidate, verifying logical equivalence
table by table, schema/indexes, foreign keys, provenance and the manifest before promotion; it is never a
runtime `VACUUM` of an account database or a direct edit of release data. Installer resource
de-duplication applies only to byte-identical catalogue images and restores the original paths the
unified catalogue manifest requires. Runtime pruning uses an audited exact manifest and a packaging smoke
test, never fuzzy directory deletion. Packaging inputs, analysis component capability, the three themes and
a real Windows regression all need verifying before a release; size figures never substitute for
functional acceptance.

## 10. UI, logging and observability

A new dialog uses `src.app.window_geometry` to stay within the current screen's available area and centre
relative to its owner/screen, covering mixed DPI. An important prompt is organised as "state → cause →
next step"; a warning has a clear hierarchy, defaults to cancel and uses the system alert sound. Custom
colours, selected/disabled/focus states and widget sizes work in the original, black and white themes
alike. A status label belongs to the operation's owner, and unrelated features never share a transient
state such as "applying".

User-facing text distinguishes waiting, unavailable, fault, saved, deployed and confirmed; "not
detected" is never written as "missing", and an accepted RPC is never written as "complete". Help copy
keeps only what a decision needs, and detailed diagnostics go into the check detail or structured logs.
Logs record only lifecycle, frozen identity, state transitions, error codes and durations, handled per
`docs/reference/logging-events.md`; a local fault log may keep the absolute file paths needed to locate a
problem and does not redact paths. Never log an account display name, a complete UID list, a complete RPC,
a recoverable payload, raw OCR text, a screenshot, a CDK, a token, an authenticated URL, raw per-hit data
or a complete damage table. The persistent log belongs to the current account; switching accounts ends the
old session, and the verbose log uses its own timestamped file. Logs, screenshots and captures are not a
source of account truth and enter neither the default export nor a release artefact.

## 11. Development order, tests and the definition of done

Before starting, establish the input/output data domain, source capability, frozen identities, external
side effects, failure rollback and verification evidence. A product semantic change proceeds as "public
behaviour tests → contract/docs → Domain/Service → DAO/Integration → Controller/UI → migrate every caller
and delete the old entry point → targeted verification → core/full plus static checks"; reproduce a defect
first and fix the smallest business cause. A pure documentation task does not take the opportunity to
change production code. Before changing any file, look at `git status` and keep other developers'
uncommitted state.

- A new or modified Python file under `src/`, `tools/` or `tests/` does not exceed 800 lines; touching an
  existing oversized file only splits or shrinks it. A new Python file's first line is a Chinese summary
  comment; a new `type: ignore` carries the error code and a reason.
- Ruff `E9/F63/F7/F821/F401` is a hard gate; a new dependency updates `pyproject.toml` and `uv.lock`
  together. The quality entry point is `tools/quality/run_tests.py`, where `core` covers the critical
  boundaries and `full` is the complete discovery.
- Behaviour tests cover calculation, persistence, migrations, account isolation, source/integrity,
  concurrent cancellation, after-the-fact confirmation, permissions, visible data semantics, keyboard
  reachability and windows staying on screen. Long-lived regressions never pin colours, pixels,
  decorative images, margins or private widget structure; responsive layout is part of the behaviour
  contract only as far as widget operability and content not being obscured. A stale test is rewritten
  or deleted, never kept alive by a compatibility layer for a retired entry point.
- By default do not compile and do not run tests; with the user's explicit authorisation, run only what
  was authorised. Report honestly what was not run. Static checks, targeted tests, `core`, `full`,
  packaging and real Windows acceptance are different evidence; separate new failures from existing ones,
  from optional components missing and from an insufficient environment, and never mask a production
  defect by deleting or skipping a test.
- Never commit the account database, WAL/SHM, logs, screenshots, PCAP, OCR temporary files, build or
  installer output, a local SDK or a dump. Committing, pushing, releasing, building an installer,
  deploying an external component and operating the real game each happen only with the user's explicit
  authorisation.

The release preparation entry point is `tools/release/prepare_release.py`, which only outputs local checks
and the maintainer's manual commands and never pushes or uploads by itself. Before an official release,
verify the unified version, dataset, component manifest, upgrade and rollback, a clean install, the three
themes, account switching, inventory/character sync, the key calculation/save/assembly paths, component
deployment and cleanup, and a real Windows smoke test. A release build should refuse an analysis
component that is missing, mismatched or lacks a required page capability; a capability whose
verification is unfinished must never be marked stable.

## 12. Localisation

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

Localisation gates, on top of section 11:

- `tests.test_i18n` — `test_every_tr_key_resolves` fails on a `tr()` key missing from `locales/en.json`.
- `python tools/quality/i18n_coverage.py --scope ui` finds Chinese handed to a widget that was never
  wrapped at all. The test suite cannot see that.
- `tests.test_i18n_sync_status` covers the sync status line, which renders `tr(state.message)` fed by
  `_publish` literals, native status dicts and the text of every `NativeSnapshotPending` raised anywhere.
  Those exceptions stay Chinese because they are logged; a new one only needs its `en.json` entry.
- A new game term in `locales/glossary.en.json` is checked with
  `python tools/quality/verify_terms.py --locres <export>`. The export is game content and is never
  committed, so this is a manual check; nothing else can tell a coined name from a real one.

## 13. Upstream synchronisation

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
produced 12 across 22, 2.3.0 produced 63 across 171, and 2.3.2 produced 39 across 100. Almost every hunk
has the same shape, upstream
having changed a line the fork had wrapped:

```text
ours   (the fork): setText(tr("⏳  扫描中... ({key} 停止)", key=...))
theirs (upstream): setText("⏳  扫描中... (F12 停止)")
```

Resolve by taking upstream's text and re-applying the `tr()` wrapper, then adding the new Chinese source
string to `locales/en.json`. Resolve **hunk by hunk**, never with `git checkout --theirs`: that replaces
the whole file and silently drops the fork's localisation in every region that merged cleanly. In 2.3.0
the difference was 1306 lost translator calls versus 353.

Four failure modes recur and none of them is caught by `git`:

- **A dropped import.** Upstream's hunk replaces the import line and the fork's `from src.i18n import …`
  goes with it, while the usages elsewhere in the file merged cleanly. Audit every conflicted file for a
  translator used but not imported; in 2.3.0 that was 8 files.
- **An orphaned parenthesis.** A `tr(` opener living outside the conflict hunk leaves its closing
  parenthesis behind when our side is discarded. `compileall` catches it; `ast.parse` does not.
- **A broken fork-only invariant.** 2.3.0's hunk for `equipment_presentation.py` dropped `main_key` but
  kept the line deriving the percent suffix from it — the section 12 rule, silently undone.
- **A call site lost with a moved function.** When upstream moves code, the fork's translator call goes
  with the old copy and only an *unused* `display_term`/`tr` import is left behind. In 2.3.2 the English
  name search vanished this way when `match_pinyin` moved to `src/domain/name_search.py`. Treat a newly
  unused translator import as a lost call site, not as a stray import to delete.

After every sync, run the gates in section 11 **and** `i18n_coverage.py --scope ui`.

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
2.3.2 rewrote it again into 11; each time the English version was re-translated from scratch with the
fork's two sections re-attached and renumbered. That is the
deliberate trade: the file is read constantly by the fork's maintainers and merged a few times a year.
