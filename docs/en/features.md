# Feature principles and data contracts

*English · [简体中文](../features.md)*

This document describes the features that are implemented and covered by public behaviour tests.
Layering and data domains are in [Architecture](architecture.md); anything still waiting on a real
environment or an upstream capability is in [Current roadmap](roadmap.md).

## 1. Accounts, settings and the dashboard

The application manages the current account and generation through `AppContext`. Account databases,
screenshots and logs are isolated from each other. Switching accounts first stops or blocks background
tasks, then rebuilds the sync, scanning, appraisal and battle-report dependencies. Worker results from
an old generation never update a page or the database.

The theme is written to `config/global_ui_preferences.json` and applies to every account; a previous
account's theme is migrated only when the global file is first created. Calculation preferences, base
weights, hotkeys, scanning, rewind and UI selections are written to the current account under their
established keys. The dashboard only reads the account summary, environment status and current stable
snapshot; it does not reimplement business queries.

## 2. Inventory sync and immutable snapshots

nte-core inventory events pass through collection, a completeness check and content stabilisation in
`InventorySnapshotStabilizer`, then commit equipment, stats, character instances and the current pointer
in a single transaction. Stability is judged by a complete content fingerprint plus a quiet window,
never by the historical maximum count. A missing character-list field and an explicitly empty list
are different snapshot contents: when a character list arrives, a new snapshot is written even if the
equipment is unchanged, and history is never rewritten.

Native sync deduplicates only against a saved native snapshot. Coming back to native sync from a
vision inventory always saves a new native-source snapshot, even when the items are identical. Sync
status distinguishes the two sources: a vision scan provides no character instances and is never
described as an old-Core snapshot. When a native snapshot carries no character list, or no character
instance has been observed yet, the status says so rather than implying anything about the Core
version or about fast assembly being available for every character; assembly still resolves target
character identity through its own public validation. Identical content arriving again refreshes the
status without saving another snapshot.

When a stable snapshot fails to save, the interface distinguishes a database lock conflict,
read-only or permission problems, insufficient space, corruption, a read/write or open failure, a
schema mismatch, a constraint conflict and a transaction error, and says the cause is unknown when
it cannot classify one. Technical detail keeps the SQLite exception type, the raw extended error
code and name, the failing stage, a safe message and the rollback result; a rollback error never
masks the first save error. Retries continue in the background at the existing interval — the app
never repairs the database or creates a new account on its own. Log fields and the privacy boundary
are in [Logging event specification](reference/logging-events.md).

`inventory.get_latest` reads the most recent capture and does not force a refresh. Downstream work
resolves the current `snapshot_id` once at start and does not follow the latest pointer while running.
Snapshot cleanup protects the current snapshot, active loadout slots, locked plans and references held
by unfinished jobs.

Account schema v21 supports runtime state deltas for native inventory. A partial equipment event only
overlays `locked`, `discarded`, `equipped`, character instance and position for official UIDs already
known in the current full snapshot; an older sequence never overwrites newer state, unknown UIDs are
ignored, and neither inventory membership nor the current snapshot pointer changes. Accepted commands
from fast assembly and bulk discard/lock also write the same current-snapshot projection so the
warehouse can show the target character/state immediately; later nte-core events still overwrite the
same UID. That projection never adds or removes equipment and never advances the current snapshot
pointer.

## 3. Vision and gamepad full scans

Mouse and virtual gamepad are the same vision-inventory capability:

```text
mouse capture  ─┐
                ├→ bounded screenshot stream → OCR/parse → complete vision snapshot
gamepad capture ─┘
```

A scan freezes the account, generation, user database, screenshot directory, static dataset, parse
profile, capture driver, window and token. OCR initialisation completes before the first game input. On
cancellation, a window change, a missing screenshot, a parse failure, a discontinuous index or a count
mismatch, the previous current snapshot is kept and nothing half-finished is committed.

### 3.1 Mouse capture model

- The reference canvas is 2560×1440 with 7 columns × 4 rows; coordinates map to a top-aligned 16:9
  physical-pixel content area within the client region.
- The first screen holds at most 28 items; each later page skips the overlapping first row and adds 3
  rows, at most 21 items.
- Before their respective navigation, mouse and virtual-gamepad full scans both perform one long
  top-to-bottom drag, using the opposite two-point direction from fully automatic incremental scanning
  to reset the list position.
- A mouse full scan builds an immutable pagination plan from the user's total count. The final page maps
  the total row count onto a bottom-aligned four-row viewport, clicks only the planned cells, and
  re-checks the count with contiguous-occupancy detection. Gamepad scanning keeps its existing flow.
- Before the first click, a cell pre-check runs on the planned first screen to catch the wrong tab,
  unloaded content, occlusion and whole-view offset.
- The normal scroll profile is `-280 × 7 + -120 × 2`; every sixth page turn uses the cumulative
  compensation `-280 × 6 + -120 × 4`. Wheel deltas do not scale with resolution.
- Click positions and timing are randomised within safe bounds; tests can inject a fixed seed. Each
  item's screenshot still saves the full client area so the unified parser keeps working.
- Dual-thread mode uses one screenshot producer, one OCR consumer and a bounded 21-item queue.
  Compatibility low-load mode uses slower input and serial parsing.

Automated coverage currently includes 1080p, 2K, 4K, 2560×1600 top alignment, final pages of 1–21 items
and bottom alignment, 2000-item pagination, scroll compensation, the random safe area, backpressure,
cancellation and not committing on failure. Real-device behaviour is recorded per
[Windows acceptance](validation/windows.md).

### 3.2 Scan reports and post-scan management

Each mouse scan atomically updates `mouse_scan_last_report.json` in the account's screenshot directory,
recording resolution, profile, pre-check counts, pagination, wheel, expected/captured counts, duration
and termination state. It never records UIDs, full OCR text, screenshot content or absolute paths.

When post-scan management is on, the complete vision snapshot commits first, then a lock/discard plan is
generated from the same frozen scan index. Execution walks backwards from the highest index, verifying
each item's original screenshot identity, pre-operation icon, action and post-operation icon in turn.
Switching a locked item to discarded must wait for the confirmation dialog. When the pre-operation icon
disagrees with the pinned plan, that item performs no input, is recorded, and the rest of the plan
continues, with a summary in the scan-complete notice; a positioning, identity, dialog or
post-operation check failure still stops all further input.

Results go to `mouse_state_sync_last_report.json`, holding aggregate counts, state transitions, items
skipped for state mismatch, duration and safe error types. This session capability does not turn a
temporary vision UID into an official UID with deferred warehouse write-back.

## 4. Calculation, character configuration and custom characters

A calculation request freezes the account, generation, snapshot, static dataset, profile, character
order/equal-priority groups, target loadout slot, lock snapshot and the blueprint combination cap,
and returns an immutable `WeightedAllocationPreview`. Saving consumes only that preview and never
re-reads the latest inventory or configuration. Combination evaluation reuses the scores already in
the current pinned candidate pool and changes no blueprint candidate, search order, tie-break or
search limit; switching pools or entering a new reservation-conflict branch re-prepares that data,
while checks that depend on the current loadout state, such as the CRIT threshold, still run one
step at a time.

Candidate rules:

1. Locked real UIDs are excluded together before candidates are built; an invalid lock blocks the
   calculation.
2. Account-level "filter settings" select no rarity or type by default. Once Cartridge or Module is
   selected, at least one rarity must be selected too. For a selected type, only the selected rarities
   reach the character-management filter and the rest are filtered out; unselected types follow the
   default rules. This filter runs once before character configuration, and the character-priority and
   incremental-update modes share the same candidate result.
3. The Module sub-stat blacklist is a hard filter by default. With "blacklist means zero weight" on,
   matching Modules are not eliminated — the blacklisted stats score zero in the Top-K ranking. Custom
   sub-stat selection prefers the deepest/most-hit candidate pool, widening step by step when no
   combination works.
4. Cartridges apply the set and main-stat hard filter first, then the same sub-stat fallback; the
   default is a 4-piece set.
5. "No grade restriction" only removes the custom sub-stat threshold. It does not remove the set or main
   stat, and it does not change the blacklist's current hard-filter or zero-weight semantics.
6. Equal-priority group CRIT recovery goes: swap the Cartridge only, then freeze the required set pieces
   and re-pick the extra pieces, then rebuild only the failed characters from scratch.
7. Under character priority, UIDs fixed by an earlier group do not enter later candidate pools, but
   Modules that tie on score and are genuinely equivalent within the final blueprint defer their
   ownership. Equivalent candidates must match on shape, score, stat priority, extra-shape gain and
   CRIT constraints; a later group may use them, but every such use keeps a one-to-one back-fill for
   all of the earlier reserved slots. An equal-priority group completes its joint allocation first
   and only then establishes reservations as a whole; ownership is back-filled by stable UID when
   the calculation ends. When an ordinary same-tier matrix search exhausts the reservation branches
   with no back-fillable result, the earlier reserved slots join the same matching to recover a
   complete plan within the original blueprint candidate range, still checking the original CRIT cap
   and the other constraints; an existing back-fillable result and the explicit CRIT-minimum path
   keep their original rules. Virtual placeholders score 0 and never enter a lock or fast assembly.
8. The allocation settings' "blueprint combination cap" defaults to 500 and limits how many entries
   of the blueprint Cartesian product the current priority group evaluates: for a single-character
   group that is just that character, for an equal-priority group it is the group's joint
   combinations. Any positive integer is accepted; above the theoretical number of combinations only
   that total is evaluated. The global stop key cancels at a combination-enumeration boundary.

Unless explicitly overridden, official characters use the graduation template set and signature weapon;
Cartridge main/sub stats default to unselected; and the automatic-equipment CRIT Rate cap in character
management counts the level, ascension and unconditional `CritBase` of the automatically selected Arc
(including refinement's permanent attributes) plus the `CritBase` of an enabled affinity 10. The
minimum is checked against equipment-side CRIT only and ignores affinity. The last manual entry or
Arc selection in character management overrides the current cap, and a manual `0` means no CRIT Rate
cap; a manual cap may only tighten it further. Both character priority and incremental update consume
the character-management CRIT Rate cap and minimum. Upgrades preserve existing account configuration,
including the historical
"Cycle intensity" setting for the protagonist 「零」.

Account base weights are a persistent calculation input. The dynamic weights on the character detail
page are generated only from the current panel's direct-damage margin, used for analysis and replacement
ordering, and never written back to the base weights. Official extra shapes read the public shared
override. A custom character's name, weights, extra shapes, default set and 5×5 chassis are written to
the current account only. A custom chassis has a fixed 20 enabled cells, and individual cells can be
locked.

Custom characters can take part in vision-inventory calculation and in-game automatic assembly. They do
not enter official character details, nte-core character instances, in-game loadout import or fast
assembly.

Cartridges uniformly use the `StatCatalog` max-level main-stat values: gold/orange 1.0, purple 0.8,
blue 0.6. A plan saves `payload.tape_main_values` and `payload.assignment_scores`; the unified helper
fallback is used only when an older plan is missing those fields.

Individual Cartridges and Modules are still graded D to ACE on the ratio "score / (area × 10)". A
complete loadout plan's overall grade uses fixed total-score bands only: D `<160`, C `>=160`, B `>=180`,
A `>=200`, S `>=220`, SS `>=240`, SSS `>=260`, ACE `>=280`. That overall rule does not depend on
character source or slot: official characters, custom characters and each loadout slot of the same
character are graded on their own plan totals, and no individual item's score or grade changes.

## 5. Loadout slots, in-game import and locks

Each character has at most three visible slots. `primary` is the compatibility default slot and shows
the character name by default; users can create, rename, archive and select slots. Each slot has exactly
one current plan at a time; overwriting creates a new plan version and atomically updates
`current_plan_id`, while historical plans still resolve against their own source snapshots.

Multiple slots on one character are alternative loadouts: they may reference the same real UID and that
is not an equipment-reuse conflict. Both the character-priority and incremental-update modes
treat the character as the UID conflict boundary; a conflict is handled only when different characters'
current slots reference the same UID.

Before saving, calculation and weighted calculation explicitly choose a target slot for each character,
optionally creating a slot or skipping. Difference comparison uses that same target slot and does not
treat another alternative slot as the baseline. Bulk saving is transactional: if a later character fails
validation, the whole batch rolls back. Calculation results warn only about characters whose slots are
"all locked" among those chosen in step two; locked characters that were not selected produce no such
warning.

An in-game loadout is a read-only projection of an nte-core stable snapshot. An explicit import saves it
as `game-observed-loadout-v1`, freezing the source snapshot, target slot, per-item scores and Cartridge
max-level values. A plan with complete Modules but no Cartridge can be saved as
`incomplete/missing_tape`; vision sources do not enter in-game loadout import.

A lock applies to a specific slot plan in the current account and never calls the game's lock RPC. One
real item is enough to lock; empty plans and virtual-placeholder plans cannot be locked. A locked slot
cannot be overwritten, archived or have a single item replaced, and other characters/slots may not
borrow its UIDs. When `primary` is archived the DAO promotes a remaining visible slot; every character
keeps at least one visible slot.

The loadout page, the character's Console detail, replacement, rewind and assembly all read the selected
or default slot. Bulk assembly explicitly chooses one `slot_id` per character and, before executing,
checks character uniqueness, slot existence, native source and the absence of cross-character UID
conflicts.

## 6. Warehouse and appraisal

The warehouse reads a pinned snapshot and produces a projection through `WarehouseInventoryService`.
Cartridges filter by set, main stat and sub stat; Modules filter by shape and sub stat. Conditions use
official IDs, OR within a group and AND across groups. States are equipped, locked, discarded and other.
Reset clears every condition. Vision sources fall under "other" because they have no reliable native
state.

Native warehouse state management pins the snapshot and official UIDs: the service builds the plan, the
integration submits the RPC, and it then waits for an increasing full snapshot to confirm. Bulk
discard/lock and warehouse state saving update the warehouse projection for the target UIDs as soon as
the command is accepted. If, within those two actions' guard window, a single inventory snapshot arrives
covering every target UID, the action itself replaces the inventory set, which may add or remove items.
The player is prompted to re-sync from the game's login screen only when that action receives an
inventory event declaring a reduced count; background listening never performs such a replacement on its
own. The vision warehouse is read-only; only same-session mouse management right after a scan performs
immediate write-back using the scan index.

The evaluation character scope affects warehouse lock/discard scoring only, and is isolated from
calculation characters, the active loadout and rewind preferences.

Appraisal projects screenshots, the clipboard, manual input and the warehouse single-item entry point
into one unified equipment object, then calls the shared scoring and `EquipmentPresentation`. It never
writes inventory, base weights or loadouts. Scanning and appraisal share `GlobalHotkeyManager`, using
the owner to isolate sessions and stop permissions.

## 7. Rewind recommendation and execution

The toolbox page reads the pinned inventory, account preferences and the active loadout slot. Opening
the page or changing options does not solve automatically; an explicit generate returns an eight-slot
shape multiset. The preference fields are `target_character_ids`, `main_character_ids`, `strategy`,
`target_grade`, `target_threshold_mode` and `target_custom_percent`. Standard grades keep D to ACE;
choosing "custom" requires a target percentage from 1.0% to 100.0%, saved to the current account at 0.1%
precision.

```text
standard target score = grade ratio × max(1, Module area) × 10
custom target score   = custom percentage × max(1, Module area) × 10
shortfall             = max(0, target score - the plan's saved per-item score)
```

Grade ratios: D=0, C=.2, B=.3, A=.4, S=.5, SS=.6, SSS=.7, ACE=.8. The custom percentage is computed
against each Module's own actual area; matching the target produces no shortfall, and a score above the
target does not offset another Module's shortfall. This threshold changes only the rewind
recommendation's shortfall statistics — never an individual item's score or a plan's overall grade.
Custom characters and each active loadout slot of the same character take part in the statistics
independently.

- **Balanced**: every built character keeps one slot per shape with a positive shortfall, and the
  remaining slots are distributed in proportion to "shape shortfall ÷ inventory".
- **Focused push**: only the push characters are considered; one slot per shape with a positive
  shortfall, and the remaining slots distributed by score shortfall alone.

More than eight shapes with positive shortfall returns a notice. Each slot has a 12.5% chance; when the
same shape repeats `q` times, each slot costs `10 + 5 × (q - 1)` and the total is `q × per-slot price`.
Difficulty determines only blue/purple/gold rarity and never affects shape, probability or price.

Explicit execution freezes rarity, custom mode and the eight-slot plan. Each rarity switches to its
difficulty first and then reads that difficulty's balance; balances are not reused across difficulties.
The beginner random ten-pull is fixed at 600; purple/gold custom reads the ten-pull price from below the
coin slot on the right. "No changes" keeps the existing candidates; "Apply plan" configures the eight
slots after globally matching outlines against the 12 topologies. The ten-pull loop is click, wait 1s,
Esc, wait 1s, Esc, wait 0.5s, and the global stop key from Settings stops it. Real execution is still an
experimental capability.

## 8. Fast assembly and in-game automatic assembly

Fast assembly consumes only nte-core official UIDs, character instances and saved slot plans; in-game
automatic assembly consumes the vision projection and input actions, and can support custom characters.
Both chains freeze the account, generation, source snapshot, slot list and job token, and persist
character items and events.

Fast assembly makes at most three full requests per character. After each dispatch it waits 10 seconds
for a complete increasing snapshot. Whether a full snapshot, a scoped equipment event, or nothing
follows, the Cartridge/Modules in an accepted command are immediately projected onto the target
character and cells. A full snapshot is the preferred confirmation source and can verify the character,
instance and complete equipment set; a Module cell difference alone does not trigger re-assembly. Scoped
events are used only to spot omissions: a character is retried only when the target equipment appears in
an event but is not equipped. With neither a snapshot nor a scoped event, the round simply ends — that
is not treated as an omission and the inventory set is not rewritten.

A clear mismatch on the first or second attempt triggers an unequip-and-reassemble; only a third
mismatch produces a final error. Reports distinguish a missing pipe, a transient outage, a busy queue, a
core request timeout, a full-snapshot wait timeout, an unconfirmed scoped event, and character/instance/
position/equipment-set mismatches.

In-game automatic assembly uses character recognition, mouse/virtual gamepad and screen state. The
regular mouse path is the current public capability; cloud-mode code is retained but the controller pins
it off — the blocking conditions are in [the roadmap](roadmap.md).

## 9. Battle reports

The battle-report calculation pages load through the standalone `nte-analysis-core.exe` and its
direct database read interface. The request carries only the frozen account, generation, record
number, database and configuration paths, analysis range and user candidates; the Rust side takes the
raw summary, per-hit data, frozen growth and equipment, edit copies and target conditions in a
read-only transaction, then runs action and source resolution, target identification and fitting,
character and Arc state, healing, buffs, per-hit formula replay, damage composition, counterfactual
comparison, candidate gains and the dynamic panel. The overview, per-hit, buff and marginal pages all
share that entry point. Native calculation keeps the existing mechanism-coverage boundary and never
turns missing evidence into zero or into a complete gain. The component protocol, failure behaviour
and verification boundary are in
[External integrations](integrations.md#11-nte-analysis-core).

A finished result is kept for at most two entries within the current account session and is cleared
when the report changes; returning to a recent identical configuration re-validates the calculation
inputs before reusing it. Any change to the range, marginal character, candidate configuration,
target conditions, raw evidence or static rules recalculates, and the cache is never written to the
account database. While per-hit formulas, buff auditing and marginal calculation are running, a
full-width progress bar is pinned outside the scrolling content and the page stack. It shows a 1–100%
workload estimate weighted by the stages the request actually contains, advanced by core stage and
completion events; it never grows with elapsed time, never resets when a stage changes, and only
reaches 100% once every calculation and the result assembly have succeeded.

When the account has no complete native inventory, the summary, record and per-hit data are still
saved, and that match's assumed Consoles, Modules, sets and all stats are frozen from the release's
graduation template, with the calculation panel frozen through the same formula. The save prompt and
the loadout source are both marked as a graduation-template assumption. Assumed equipment is stored
with the character snapshot under its own source metadata and creates neither an inventory snapshot
nor real UIDs. It supports per-hit replay, attribute gains, Console main-stat comparison and growth
edits, but template equipment is read-only: no per-item replacement and no in-game assembly. Export
and import keep the assumed source and stats, and a later inventory or a retried save never replaces
that baseline.

The marginal page shows a wide character panel above the Module sub-stat unit margins: the header
lists the frozen base, extra, percentage and total ATK/HP/DEF, CRIT Rate, CRIT DMG, universal DMG,
own-element and other element damage, Cycle, Break, DEF ignore, each element's penetration, healing,
shield and charge. The first row is the static panel and the second is the dynamic panel weighted by
formula-panel damage. The own element is decided only from that character's own non-reaction,
non-overlay hits, and is not guessed. An attribute with no formula link or too little dynamic
evidence shows as unknown rather than presenting the static value as dynamic.

Battle reports use aggregate events and summaries from the nte-core combat session, and history is
written to the current account's database. Inventory sync and battle reports share the capture process
lifecycle and never compete for the capture session simultaneously. The page shows only official
summaries and never infers per-hit data, buff/debuff intervals, teams or enemy instances from the
aggregate result.

The live overlay is shown only during the current capture session. Clicking "Finish and generate report"
hides it immediately, and it also stays hidden on capture end, errors and historical reports. It
reappears on the next explicit capture start only if "Show live overlay" is enabled.

Manual and automatic records are cleaned up by the account's retention policy. Structured logs record
only the record ID, status, counts and safe errors — never the raw summary or the full damage table.

## 10. Environment, updates and logging

Environment diagnostics separately check Npcap, nte-core, dwmapi, the mods plugin, the runtime SDK
cache, the IPC pipe and assets. Plugin deployment backs up and copies the release DLL after user
confirmation; a workspace upgrade updates only the managed scripts and preserves the dynamic SDK cache.

The Mirror controller/integration handles version checking, downloading, cancellation and launching the
installer. Logs never record a CDK, token or authentication URL.

The persistent log is `nte_runtime.log` in the account directory; enabling verbose logging creates a
separate timestamped file. An account switch ends the previous account's session and creates one in the
new account's directory. Stable event names, common fields and the redaction boundary are in the
[Logging event specification](reference/logging-events.md).
