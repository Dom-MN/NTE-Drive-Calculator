# External integrations and extensions

*English · [简体中文](../integrations.md)*

This document defines the boundary external capabilities cross when entering the project. Business
ownership and lifecycle are in [Architecture](architecture.md); real-environment steps are in
[Windows acceptance](validation/windows.md).

## 1. nte-core

`src/integrations/nte_core.py` owns the stdio protocol, the process, events and error adaptation. It
does not own scoring, loadouts or UI. The capabilities the product currently uses are:

- `capture.detect`;
- `capture.start(profile="inventory"|"combat")` and `capture.stop`;
- `inventory.get_latest`;
- warehouse state write-back and fast-assembly RPCs;
- `event.battle.summary`, `battle.get_summary`, `battle.reset`.

`inventory.get_latest` reads the most recent capture result — it is not a forced refresh. Full inventory
events feed snapshot stabilisation; partial state events only update UIDs already known in the pinned
full snapshot. An accepted RPC means submitted, nothing more: the final state is confirmed by a later
stable snapshot or an official scoped event.

The nte-core capture diagnostic on the settings page calls only `capture.detect`, then supplements it
with read-only Windows probes summarising the Npcap driver service, enabled adapters, Npcap installation
traces and the usual `wpcap.dll`/`Packet.dll` locations. It does not create a capture session, does not
read or write network configuration, and does not output MAC addresses, IPs, remote addresses, full
local paths or the core capability list. When `capture.detect` returns zero devices, the report gives a
next step based on missing installation, driver service, no active adapter, or "driver/filter/runtime to
be investigated". When the core supplies no libpcap enumeration error text or per-adapter filter reason,
the report must state that boundary explicitly rather than invent a cause.

Per-hit pagination, buff/debuff intervals, complete growth/weapon snapshots, four-player and dual-team
setups, enemy instances, official scene IDs and historical per-hit export are not yet product contracts.
Debug samples do not substitute for a public CLI capability.

### 1.1 nte-analysis-core

`nte-analysis-core.exe` is a standalone Rust analysis component, built, deployed and process-managed
separately from the capture `nte-core.exe`. It neither links nor starts the capture Core and never
touches the game, packet capture or the network. The official battle-report page consumes the component's
declared `battle_page_v1` capability: updating the Python source alone does not enable a capability that
is not deployed, and a missing capability or a version or hash mismatch must be reported as a component
error.

The whole-page protocol is UTF-8 JSON over stdin/stdout, with one short-lived process per page request.
The request freezes the account, generation, record number, account and static database paths, semantic
configuration, analysis range, characters and user candidates, and never passes Python-precomputed
per-hit or buff data. The semantic configuration `gameplay_effect_semantics.json` is read only from the
configuration directory shipped with the app, never from a same-named file in the user-writable
configuration directory. A missing release asset is reported as an incomplete installation and can be
retried once the asset is repaired; analysis must never continue with empty rules. Rust verifies the
account database identity, the static schema and the bound dataset, and takes the shared facts in a
read-only transaction, releasing the account connection as soon as reading finishes so a long calculation
does not hold the account WAL. The static catalogue and rule cache belong to that request alone;
candidates apply their frozen edits separately and never follow the active loadout or share a mutable
panel between candidates. Public rule declarations are generated from official static sources by the
build tooling and bound to the dataset — the runtime never calls a Python builder, and unrecognised
characters, mechanisms and evidence stay unknown.

Rust owns raw axis parsing and source pairing, action and time-stop projection, target mapping and
fitting, panel and skill evidence, character and Arc state, healing and buffs, complete per-hit replay,
composition, counterfactual comparison and marginal candidate orchestration. The response carries the
page analysis, the target catalogue, candidate display axes, marginal gains and the dynamic panel. On a
non-overview response, `hit_details` uses `interned_v1` shared string, attribute, decision and projection
tables referenced by analysis/candidate, raw-attribution/formula-source and event ID. Python validates
the table indexes and event bindings and, on click, only assembles existing read-only objects with
explanatory copy; a missing detail stays ungenerated rather than falling back to computing buff rules.
Counterfactual damage composition and its character and damage entries are decoded recursively into
official domain types — an unvalidated JSON dictionary is never handed to the page for drawing.

`detail_level: editor` is a separate narrow entry point on the same protocol, needing only the frozen
account, generation, record number and account database path. Rust reads the necessary columns from the
final per-hit data and returns the character inference facts and half-scope attribution in
`editor_facts`, loading no static configuration and running no whole-match replay. Python still prepares
the editor's growth configuration, inventory candidates and equipment selection, and generates the
explanatory copy through the shared display service.

A component declaring `battle_page_identity_v1` supports `detail_level: identity`, which reuses the
official page's read-only fact loading and returns only a SHA-256 digest of the ordered inputs without
creating a replay engine. Keyed on that digest, the complete calculation request, the account generation,
and the component, static database and semantic configuration identities, Python reuses at most two
compressed raw responses within a total compressed budget of 32 MiB; a single raw response over 64 MiB is
not cached. The cache belongs to one history service and is cleared when the report changes, and every
hit re-decodes the domain objects. A digest that changes across a cold calculation cancels the result,
and failed or incomplete responses are never cached; a component without that capability simply
calculates normally. Persisting a purely presentational selection does not change the native digest,
while a real input change such as a target-inference snapshot does invalidate the cache.

A component declaring `battle_parallel_v1` may compute buff-removal groups and Console candidates in
parallel inside the one process. The owner prepares the database input, each worker owns its mutable
projection state exclusively, and the complete result is assembled in the original order, leaving per-hit
floating-point operations and summation order unchanged. By default it picks at most four workers from
the available CPUs, a frozen memory budget and the task size, reducing concurrency or going serial when
resources are low, memory cannot be queried or thread creation fails. Progress is still sent by the owner
per actually completed candidate, and cancellation still ends the whole standalone analysis process.
`--threads auto|1|2|4` exists only for explicit performance comparison; Python never dispatches per-hit
work itself or starts several core processes.

The response re-checks the version, dataset, account, generation and record identity; cancellation or an
invalidated frozen context ends and reclaims that analysis process without affecting the capture process,
and never silently turns a failure into a Python-calculated success. Account and static configuration are
validated again before returning and before saving. A component declaring `battle_progress_v1` can emit
bounded NDJSON stage events on stderr under `--progress`, while stdout still returns exactly one complete
page result. Buff removal and Console candidates count actually completed items; other stages report only
stage status. Python validates and forwards progress on the calling thread while continuously draining
both pipes, and progress shares the cancellation and request-identity boundary with the final result.
From the stages the frozen request contains, Python maps core events to a monotonic overall workload
percentage and sends 100% only once everything has succeeded. An older component without the progress
capability can only advance at start, assembly and success, and never grows with elapsed time. Events
carry no character, account or raw report content. Rust does not write the account database: automatic
target inference is returned as a complete versioned `derived_snapshot`, which Python saves on a
best-effort basis through the existing DAO — an identical result skips the write, a user-confirmed
condition wins, and a failure never discards a finished page result. The snapshot belongs to the derived
layer only and does not change the original report.

The lower-level `direct_v1`, `buff_projection_v1`, `buff_projection_plan_v1` and `battle_compute_v1`
remain in use for standalone algorithm calls, older component boundaries and differential verification.
A projection keeps half-open time boundaries, source and target labels, interval order, duplicate
evidence, stack coverage and complete adopt/exclude decisions; shared string and interval tables compress
transport only and never reduce mechanism coverage or sample it. Valid input beyond an explicit workload
limit may be split into ordered batches; other protocol errors are reported directly. The original Python
algorithm serves as the differential reference, and its orchestration time must never be counted as the
whole-page native entry point's time.

In a source checkout the runtime component lives in `third_party/analysis-core`; inside PyInstaller the
binary ships alongside `analysis-core-meta/component.json`, and the version and SHA-256 are checked
before loading. `tools/counterfactual/package_rust_core.py` collects the standalone output, provenance,
licence and source digest, and `--destination` can write to an isolated verification directory first. A
missing, corrupt or capability-mismatched component is not a version that passes deployment acceptance.

The differential tooling verifies against a frozen account copy only and never modifies original account
data, covering the complete result, every retained report, ranges, missing input, user candidates,
cancellation and derived restore. Performance is recorded separately for native internal calculation,
process and transport, and the complete page service — a local kernel speed-up never stands in for the
end-to-end gain. Headless verification excludes Qt drawing, account switching and real interaction, so an
official deployment still has to complete [Windows validation](validation/windows.md) plus the component
upgrade and rollback checks.

## 2. Vision, OCR and game input

`src/integrations/vision` exclusively owns window coordinates, screenshots, cell detection, mouse actions
and post-scan state sync; `src/scanner` and the parsing services own OCR, normalisation and equipment
fields. An integration returns screenshots, indexes, parse results or diagnostics. It does not write
business snapshots and does not decide scoring or retention rules.

Mouse and virtual-gamepad full scans both commit as a unified `vision` snapshot. In-game automatic
assembly and the experimental cloud mode use the same public input contract; pages never create a mouse
backend or a virtual gamepad. Cloud mode is currently forced off, keeping only the mapping and
diagnostic code.

A new input backend must define: window identity, physical pixel coordinates, the prerequisite page, the
action sequence, the visible post-state, cancellation checks, input release, timeout and rollback. When
post-confirmation is missing, stop the current task rather than blindly clicking again.

## 3. Binaries and the plugin

`nte-core.exe`, `dwmapi.dll` and the plugin copy in the root directory are local files. `third_party`
holds only release components that were explicitly promoted; before promotion, record the upstream
commit, version, licence and SHA-256, and complete protocol, packaging and real Windows verification.

The mods plugin's runtime SDK cache lives in a writable workspace and never enters Git or the release
template. A game update changes `HTGame.exe`'s PE image identity: a present presence event does not mean
the IPC pipe was created, and a signature match does not mean the hook was installed. Diagnose in the
order presence → workspace → pipe → hook; the real-device steps are in
[Windows acceptance](validation/windows.md), section 10.

## 4. Static data and assets

Official data only ever produces a candidate static database through `tools/game_data`. The importer
retains the source file, row keys and digests, and validates schema, foreign keys, business constraints
and the manifest before replacing the release database. The static database and `data/manifest.json` are
reviewed as one atomic change.

Game UI images are generated into `assets/game_ui` by the asset build tool, and `manifest.json` records
the ID mapping, file hashes and `unresolved_assets` explicitly. A missing asset stays explicitly
unresolved — never a lookalike image or a local path placeholder.

An account schema change adds a migration and covers creation, upgrade, failure rollback and retry. DAOs
own SQL exclusively; snapshot cleanup goes through the public DAO and protects every reference.

## 5. New pages and shared components

Implement the Page/View and Controller under `src/features/<feature>/`, register navigation in
`src/ui/navigation.py`, and inject narrow dependencies from the composition root. Shortcuts use the
navigation key, not a stacked-page number. Cross-feature reuse starts with a service, an immutable
contract or a shared component in the composition root — never forwarding through MainWindow fields or
another controller.

## 6. New algorithms, sync methods and assembly methods

- A new algorithm reuses official IDs, the pinned snapshot, candidate objects, loadout slots and the
  saved-plan payload; its output contains real UIDs, target positions, per-item scores, the source
  snapshot and the algorithm/profile version.
- Multi-character competition is handled by the unified allocator, not a per-character loop that mutates
  the inventory.
- A new sync method provides waiting, collection, completeness, stable listening, single-transaction
  commit and explicit error states; it only commits complete snapshots.
- A new assembler consumes frozen saved plans only and never re-optimises during execution. It validates
  source, character, slot, UID and position before executing, and produces a confirmable new state
  afterwards.
- Bulk side effects record progress through a persistent job, character/slot items and events.
