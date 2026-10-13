# Cycle 4 — Background Sync + Conflict Resolution

## Objectives & risks addressed

The highest-risk cycle per the plan: FR-03 (non-blocking background sync)
and FR-04 (deterministic Last-Write-Wins conflict resolution), deliberately
saved until last because it depends on a stable `sync_audit_log` producer
from Cycles 1-3. Every table added so far already logs its mutations, so
this cycle had a real backlog of PENDING rows to sync against from day one.

## What shipped (demoable)

- Repository `get()` methods added to `PatientsRepository`, `DoctorsRepository`,
  `BedsRepository`, `PharmacyStockRepository` (QueueTokensRepository already
  had one), each returning a full-row dict -- the payload the sync worker
  pushes.
- `desktop/data/repositories/sync_audit_log_repo.py` extended with
  `list_pending()`, `get_entity_for_sync_id()`, `mark_status()`.
- `desktop/sync/entity_registry.py` -- maps `entity_name` to its row-fetcher
  and primary-key column, so new tables register once and the sync worker
  handles them automatically with no bespoke per-table sync code.
- `desktop/sync/sync_worker.py` (`SyncWorker`) -- framework-free
  `OFFLINE_LOCAL -> SYNCING -> RESOLVING_CONFLICT` state machine exactly per
  the design doc. `run_once()` builds `SyncRecord`s from PENDING audit rows
  + their current full row content, pushes via the injected `SyncProvider`,
  marks SYNCED/CONFLICT rows accordingly, and leaves failed pushes PENDING
  for the next pass.
- `desktop/sync/providers/fastapi_provider.py` (`FastAPISyncProvider`) --
  the real provider, swapped in for `NoOpSyncProvider` via `desktop/config.py`
  (`HMS_GATEWAY_URL` unset => stays fully offline, exactly matching PLAN.md's
  "offline prototype, DI-ready for cloud" requirement).
- **Gateway**: `gateway/models.py` defines one generic `sync_records`
  `(entity_name, record_id) -> payload + updated_at` table, rather than
  mirroring every hospital table's schema again in Postgres -- a deliberate
  simplification matching the gateway's actual job (off-site backup +
  conflict resolution, not hospital-side queries). `gateway/routers/sync.py`
  implements `POST /sync/push`: incoming records win unless the server's
  stored row is strictly newer, in which case the server's row is returned
  as the conflict's authoritative `winning_payload`.
- `desktop/sync/sync_scheduler.py` -- a QTimer wrapper driving `run_once()`
  periodically without blocking the UI (documented simplification: each
  tick runs the async pass to completion via `asyncio.run()`, acceptable at
  this sync volume; full `qasync` integration is noted as a future option,
  not built).
- `desktop/main.py` now wires a real sync pipeline when `HMS_GATEWAY_URL` is
  set, starting/stopping the scheduler with the app lifecycle.
- 25 new tests: `SyncWorker` state transitions against a fake provider
  (offline/online, nothing-pending, successful push, transient failure
  leaving rows PENDING, conflict resolution overwriting the local row),
  `entity_registry` fetch/overwrite behavior, `SyncScheduler` start/stop/tick,
  and three Docker-Compose-backed integration tests hitting the real gateway
  (first push SYNCED, older push loses to a newer server row with the
  correct `winning_payload`, `FastAPISyncProvider` round-trip). Also added a
  shortened display-node soak test (`tests/system/test_display_soak.py`) now
  that both the display and sync paths are live, per the SQA plan's timing.

Demo performed: the plan's literal scenario -- issued a token, ran a sync
pass against an unreachable gateway (`state == OFFLINE_LOCAL`, row stays
PENDING, "cable pulled"), then pointed the same worker at the real running
gateway and ran another pass ("reconnected") -- both audit rows flipped to
SYNCED with zero data loss, verified against the live Postgres-backed
gateway, not a mock. Full suite: 92/92 passing (86 offline + 6 against
Docker Compose), 91% combined coverage.

## Metrics measured this cycle

- Combined (offline + Docker-Compose) coverage: 91%; offline-only (the
  subset CI's fast job runs) 88%. Both above the ≥80% gate.
- Data integrity: 0 data loss observed across the offline→online demo and
  all sync tests; every PENDING row was eventually marked SYNCED or
  CONFLICT, never silently dropped.
- Conflict resolution accuracy: 100% in tests -- the gateway integration
  test asserts the exact LWW outcome (older timestamp loses, correct
  `winning_payload` returned) against real Postgres, not a mock.
- Soak test (shortened): `test_listener_survives_sustained_bursty_traffic`
  ran the UDP listener against ~3s of bursty traffic (50 packets/burst plus
  interleaved corrupted packets every 50ms) and confirmed the listener
  thread stayed alive, processed ≥90% of sent packets, and shut down
  cleanly. The full 72-hour hardware soak remains a planned manual/hardware
  activity, not something CI can run.
- Open defects: P1 0 / P2 0 / P3 0 / P4 0.

## Carried-over risks / decisions for next cycle

- `SyncScheduler`'s `asyncio.run()`-per-tick approach is a known
  simplification, not a defect: fine at this sync volume (a handful of rows
  every ~30s), but would need `qasync` or a dedicated thread if sync volume
  or payload size grows significantly.
- `pull_updates()` on `FastAPISyncProvider` is a stub (returns `[]`) -- this
  cycle's flow is push-driven only (each device publishes its own pending
  changes); bidirectional pull-on-reconnect is unimplemented and would be
  additive, not a rewrite, if a future cycle needs it.
- Cycle 5 (packaging & hardening) is next: PyInstaller build, SQLCipher
  encryption, HTTPS/TLS enforcement on the gateway boundary, and a clean-VM
  build verification -- all explicitly deferred "later-cycle hardening"
  items per the plan, not required for the sync functionality itself.
- The gateway's generic `sync_records` table (vs. mirroring each business
  table in Postgres) is a deliberate scope choice; if a future need arises
  for the cloud copy to support direct relational queries (not just
  conflict resolution/backup), that would be new scope, not a bug fix.
