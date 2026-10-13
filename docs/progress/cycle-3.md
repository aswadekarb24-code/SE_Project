# Cycle 3 — Doctor/Bed/Pharmacy Modules + Role-Based Access

## Objectives & risks addressed

Feature completeness risk: three remaining in-scope ILFs (doctors/schedule,
bed_status, medicine stock) all needing the same UUID + sync_audit_log
pattern established in Cycles 1-2, plus getting role separation right
(receptionist vs. doctor) without over-building a real auth system the MVP
doesn't need. Also retires the `DEPARTMENTS` placeholder from Cycle 1/2 in
favor of a real `departments` table.

## What shipped (demoable)

- `common/schema/departments.py` — static reference data (General OPD,
  Pediatrics, Orthopedics), seeded directly in DDL rather than through
  sync_audit_log, since it's not a business mutation. `queue_tokens.dept_id`
  now has a real FK to it.
- `common/schema/doctors.py`, `beds.py`, `pharmacy_stock.py` + matching
  repositories (`DoctorsRepository`, `BedsRepository`,
  `PharmacyStockRepository`), each following the Cycle 1 pattern: every
  insert/update logs to `sync_audit_log`.
- `desktop/data/seed.py` — idempotent MVP seed data (10 beds, 20 pharmacy
  items, 4 doctors across the 3 departments), run once at startup.
- `desktop/services/bed_service.py` — 1-click
  AVAILABLE→OCCUPIED→MAINTENANCE→AVAILABLE cycling.
- `desktop/services/pharmacy_service.py` — search + low-stock flag
  (`quantity <= threshold`) + quantity adjustment that rejects going below
  zero with no partial mutation.
- `desktop/services/doctor_service.py` — availability listing + self-service
  status toggle (AVAILABLE/BUSY/OFF_DUTY).
- `desktop/services/auth_service.py` (`Role` enum) + UI-level role gating in
  `desktop/main.py`: Receptionist gets Reception/Beds/Pharmacy tabs, Doctor
  gets Doctor Console/Doctor Availability tabs. Documented as UI-level
  gating only, not server-enforced permissions -- appropriate to the MVP's
  "Dual-role Interface" scope, not a gap to be silently assumed otherwise.
- `desktop/ui/role_select_dialog.py` + three new widgets
  (`bed_matrix_widget.py`, `pharmacy_widget.py`,
  `doctor_availability_widget.py`), wired into `desktop/main.py`.
- 34 new tests: per-table CRUD + sync_audit_log generation (beds, pharmacy,
  doctors), boundary cases (double-toggle, stock-at-zero, invalid
  status/unknown IDs), seed idempotency, role-access tab composition, and
  widget-level interaction tests (search filtering, low-stock label,
  disabled-until-selected buttons).

Demo performed: `uv run pytest` full suite (76/76 pass, 94% coverage);
confirmed `MainWindow(role=Role.RECEPTIONIST)` and
`MainWindow(role=Role.DOCTOR)` produce the correct, disjoint tab sets.

## Metrics measured this cycle

- Unit + integration + system test coverage: 94% (491 statements, 28
  missed — mostly `except OSError` branches, the real modal-dialog path in
  `_prompt_for_role`, and `if __name__ == "__main__"` guards). Comfortably
  above the ≥80% core-logic gate, reassessed as planned this cycle.
- Boundary-value protocol: stock-at-zero rejection, bed double-toggle
  consistency, duplicate doctor-status-change handling — all covered by
  dedicated tests, consistent with the SQA plan's desktop UI stress-testing
  protocol.
- Open defects: P1 0 / P2 0 / P3 0 / P4 0.
- Soak test: still not applicable (Cycle 4).

## Carried-over risks / decisions for next cycle

- Cycle 4 implements `FastAPISyncProvider` and the background `SyncWorker`
  state machine (OFFLINE_LOCAL→SYNCING→RESOLVING_CONFLICT). Every table
  added so far (patients, queue_tokens, doctors, beds, pharmacy_stock)
  already writes to `sync_audit_log` on every mutation, so Cycle 4 has a
  real backlog of PENDING rows to sync against from day one — no retrofitting
  needed.
- Role gating remains UI-level only (no login/password, no per-request
  authorization) by design for this MVP; if a future cycle needs real
  authentication, it is additive to `auth_service.py`, not a rewrite.
- `display_sim`'s Tkinter widgets remain untested in CI (carried over from
  Cycle 2 — no Xvfb configured); unaffected by this cycle's changes.
