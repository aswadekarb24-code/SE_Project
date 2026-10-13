# Cycle 1 — Core Offline Transaction: Patients + Queue Tokens

## Objectives & risks addressed

De-risk the local-first write path: client-generated UUID primary keys,
per-department/per-day token numbering, the <10ms write-latency target
(NFR-01), and WAL-mode crash safety for multi-row transactions (patient +
token + two audit-log rows). This is the first cycle with real business
logic and the first to produce a sync_audit_log trail, even though nothing
consumes it yet (`NoOpSyncProvider` is still the only wired provider).

## What shipped (demoable)

- `common/clock.py` — single source for ISO-8601 UTC microsecond timestamps
  (`now_iso`) and ISO dates (`today_iso`), reused by every repository and
  later by sync's Last-Write-Wins comparison.
- `common/schema/patients.py`, `common/schema/queue_tokens.py` — DDL matching
  the design doc exactly (UUID PKs, FK, status CHECK constraint, indexes for
  name lookup and dept/status/date queries), registered in
  `desktop/data/db.py`'s `MIGRATIONS` list.
- `desktop/data/repositories/` — `PatientsRepository`, `QueueTokensRepository`,
  and a shared `sync_audit_log_repo.log_mutation()` every repo calls on write.
- `desktop/services/queue_service.issue_queue_token()` — the full
  `IssueQueueToken()` algorithm from the design doc, wrapped in a single
  explicit `BEGIN`/`COMMIT`/`ROLLBACK` transaction so patient + token + both
  audit rows commit atomically.
- `desktop/broadcast/broadcaster.py` — a `Broadcaster` Protocol +
  `NullBroadcaster`, mirroring the `SyncProvider` DI pattern. `queue_service`
  already calls it on every issued token; Cycle 2 swaps in the real UDP
  implementation with no change to `queue_service`.
- `desktop/ui/reception_window.py` — a working Reception check-in form (name,
  DOB, gender, contact, department) wired to `issue_queue_token`, now the
  desktop app's central widget.
- 10 new tests (`tests/unit/test_queue_service.py`,
  `tests/unit/test_reception_window.py`,
  `tests/system/test_power_interruption_wal.py`): new-vs-returning-patient
  handling, per-dept/per-day numbering, sync_audit_log row generation, p99
  write-latency assertion, UI validation + happy-path, and two WAL
  crash-safety tests (bare patient insert, and patient+token together).

Demo performed: launched the app, issued several tokens across departments
fully offline, confirmed per-department numbering and the status label;
`uv run pytest tests/unit tests/system` — 19/19 pass.

## Metrics measured this cycle

- Unit test coverage: 95% (cumulative; ≥80% core-logic gate now formally
  applies and is met).
- Local write latency (`issue_queue_token`, 500 iterations): p50 0.056ms,
  p99 0.130ms, max 0.222ms — well inside the <10ms NFR-01 target.
- LAN broadcast latency: not yet applicable (Cycle 2).
- Soak test: not yet applicable (Cycle 4).
- Open defects: P1 0 / P2 0 / P3 0 / P4 0.
- WAL power-interruption protocol: 2/2 crash-safety tests pass (no partial
  patient row; no orphaned token row) when a transaction is abandoned without
  COMMIT.

## Carried-over risks / decisions for next cycle

- Cycle 2 implements the real `desktop/broadcast/udp_broadcaster.py` and the
  Tkinter display simulator, and wires `Broadcaster` into `queue_service`
  callers (and "Call Next" on the Doctor screen, driving
  WAITING→CALLED→DONE).
- `common/broadcast_protocol.py` (the shared UDP payload schema) is deferred
  to Cycle 2 as planned — not needed until there's a second process to talk
  to.
- Department list is currently a hardcoded placeholder in
  `reception_window.py`; Cycle 3 replaces it with a real `doctors`/department
  table and removes the placeholder.
