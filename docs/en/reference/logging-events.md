# Core logging event catalogue

*English · [简体中文](../../reference/logging-events.md)*

Event names use a stable dotted English format. Logs record business stages and safe summaries; they are
not a source of database truth.

> Note: logging *text* stays Chinese by repository convention (see `AGENTS.md`). Only this reference is
> mirrored in English.

## Common fields

| Field | Meaning |
| --- | --- |
| `event` | Stable event name |
| `feature` | Feature domain |
| `operation_id` | Correlation ID for one user operation across controller, worker, service and integration |
| `account_id` | Internal account ID; the display name is never logged |
| `context_generation` | `AppContext` account generation |
| `snapshot_id` | Frozen inventory snapshot |
| `slot_id` | Loadout slot; recorded when a plan is saved, imported or assembled |
| `job_id` | Persistent job ID |
| `source` | Controlled source enum, e.g. `nte_core`, `vision` |
| `phase` | `started`, `succeeded`, `failed` or a stable business stage |
| `duration_ms` | Stage duration |
| `result` | Redacted result summary |

Fields that do not apply are omitted rather than filled with fake empty values. Operations with a
standard lifecycle get `phase` and `duration` attached automatically by `operation_scope()`.
Cancellation, stale-result discard, pending confirmation and degradation use their own events and are
never disguised as `succeeded`.

## Event families

| Feature | Event prefix / key events | What it helps diagnose |
| --- | --- | --- |
| Application | `application.*` | Version, startup, exceptions and exit |
| Account | `account.switch_*` | Blocking, stopping, generation switch, rebuild and completion |
| Migration | `database.*` | Schema, shared-shape migration, transaction failure and retry |
| Sync | `inventory_sync.*` | Connection, candidates, stabilisation, commit, runtime state deltas, retention policy and stop reason |
| Scanning | `scanning.*` | Frozen dependencies, capture driver, pagination, parsing, commit and post-scan state management |
| Calculation | `allocation.*` | Frozen request, solving, target slot, saving, failure and stale-result discard |
| Loadout slots | `loadout_slot.*` | Creation, rename, archive, current-plan switch and lock conflicts |
| Characters | `role.*` | Index/detail, configuration, replacement, dynamic weights and dirty decisions |
| Base weights | `basic_weight.*` | Account weights, custom characters and chassis save/reset |
| Shared extra shapes | `shape_bonus.*` | Shared override save, migration and restoring release defaults |
| Blueprints | `blueprint.*` | Generation, failure and discarding results from a previous account |
| Warehouse | `warehouse.*` | Pinned snapshot, runtime overlay, filters, plan, RPC, pending confirmation and final state |
| Appraisal | `identification.*` | Input source, hotkey owner, recognition and display lifecycle |
| Fast assembly | `equipment_apply.*` | Slot pre-check, dispatch, full-snapshot/scoped-event confirmation, retry and summary |
| Automatic assembly | `drive_assembly.*` | Page stages, input backend, actions, stop and visible result |
| Rewind | `rewind.*` | Recommendation request, eight-slot save, OCR stages, ten-pull plan and stop |
| Battle report | `battle_report.*` | Capture lifecycle, summary persistence, history restore and retention policy |
| Environment | `environment.*` | Npcap, nte-core, dwmapi, SDK cache, pipe, deployment and restore |
| Update | `update.*` | Check, download, cancel, failure, completion and installer launch |

Sync and warehouse may log aggregate counts of Modules, Cartridges, equipped items, locked items and
character instances — never UID lists. Battle-report fields may include `battle_record_id`,
`persistence_status`, `retention_kind`, `inserted`, `changed`, `pruned_record_count`, `character_count`,
`skill_count` and `total_hits`; raw summaries and damage detail are never logged.

Inventory sync logs the following decision chain at INFO without requiring verbose logging:

| Event | Diagnostic |
| --- | --- |
| `inventory_sync.baseline_selected` | Whether this run's dedup baseline is valid, its source, item count and settle window; a vision source is never a native baseline. |
| `inventory_sync.baseline_invalid` | A saved snapshot could not seed the dedup baseline; a new complete snapshot is still accepted, and the raw validation error is not logged. |
| `inventory_sync.core_connected` | Core/data version (when the handshake provides one in a valid format), protocol and capabilities; never the executable's absolute path. |
| `inventory_sync.event_evaluated` | The stabilisation verdict for the event taken, its fixed reason code, the completeness flag, field types, declared/actual counts, generation/sequence and the assembly-guard item count. |
| `inventory_sync.session_summary` | Cumulative processed count, per-verdict and per-rejection counts, commit/save failures, items awaiting stability and time since the last processed event; a final summary is emitted on both stop and error. |
| `inventory_sync.snapshot_committed` | The new snapshot summary, the previous inventory's source and item count, and how long the content stayed stable; a shrinking count is recorded as fact, never treated as incomplete on the strength of a historical count. |
| `inventory_sync.failed` | Keeps the domain error code and uses `failure_stage` to separate settings loading, Core start-up, capture start, event handling, saving and post-commit work. |

`event_evaluated` is rate-limited per "verdict + fixed reason code": the first is logged immediately
and later ones of the same kind at most every 30 seconds, with no loss to the aggregate counts. The
session summary is logged every 30 seconds and on exit. The processed count is how many times the
worker thread took an event from the latest slot and judged it — not the number of network packets,
not the total events Core emitted, and not the pre-merge callback count; zero only means this session
has not processed an inventory event yet and is not on its own proof that the adapter saw no traffic.
Rejection reason codes separate an incomplete snapshot, a declared-count mismatch, a duplicate
equipment/character instance, other structural invalidity, an assembly-inventory guard mismatch, a
stale or duplicate sequence, and old-format events ignored during a character-list upgrade. Raw
validation text, which can contain UIDs, is never logged.

`inventory_sync.snapshot_commit_retry` also records this session's save attempts and the candidate
item count. SQLite save-failure diagnostics include `save_error_code`, `save_stage`,
`sqlite_exception_type`, `sqlite_errorcode`, `sqlite_errorname`, `sqlite_message` and
`rollback_status`; a code or name the driver did not supply is not written. `save_stage` separates
opening the transaction, writing the snapshot, equipment and stats, updating the equipment-character
and independent-character mappings, switching the current pointer and committing. A failed rollback
adds the same class of safe SQLite fields under `rollback_error` and keeps the first error.
Classification uses the primary SQLite error code while diagnostics keep the full extended code.
Messages allow only fixed SQLite text and table, column or constraint names in a restricted format;
other raw messages stay private so a trigger or binding error cannot smuggle out business data or
paths. These diagnostics never read or log SQL parameters, UIDs, complete snapshots or the account
display name.

Mouse-scan report events log only the profile, resolution, expected/captured counts, page count, queue
high-water mark, duration and the safe-termination type. Post-scan state management logs only planned
and completed counts plus aggregate state transitions, never target indexes.

## Session files

- Persistent: `accounts/<account_id>/logs/nte_runtime.log`, INFO and above;
- Verbose: `accounts/<account_id>/logs/nte_runtime_YYYYMMDD_HHMMSS[_N].log`, DEBUG and above;
- re-enabling verbose logging creates a new file each time;
- an account switch ends the previous account's session first, then creates one using the new account's
  settings;
- "Clear" on the settings page clears the on-screen text only; it does not delete log files.

## Redaction boundary

Logs never contain a Mirror CDK, token, cookie, `Authorization` header, authentication query parameters,
a complete nte-core RPC, a complete inventory, UID lists, account display names, full OCR text,
screenshot content, absolute user paths, window titles or any recoverable business payload.

Exceptions pass through unified redaction before reaching structured logs, keeping only the exception
type, a safe message and permitted error codes. The automated entry points are
`tests.test_observability_logging` and `tests.test_runtime_logging`.
