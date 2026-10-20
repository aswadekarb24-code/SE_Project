# Cycle 6 — Accounts, Patient Records & Reports

## Objectives & risks addressed

Turn the dual-role prototype into something a clinic could actually run a
day on: real per-person sign-in instead of a role picker, a permanent
patient identity that survives repeat visits, and a doctor-side medical
record that can be printed. Also a full UI overhaul to the card-based
dashboard style of the design references.

The main risk was **data integrity in an offline-first, multi-station
setup**: human-readable numbers and medical history both have to stay
correct when several stations work offline and sync later, and existing
databases have to upgrade in place without losing anything.

## What shipped (demoable, verified here)

- **Accounts, sign-in, sign-out** (`desktop/services/auth_service.py`,
  `desktop/ui/auth_page.py`). Create account / sign in screens replace the
  role picker; the role comes from the account.
  - Passwords: PBKDF2-HMAC-SHA256, 600,000 iterations (OWASP 2023), random
    16-byte salt, constant-time comparison. The iteration count is stored
    in each hash so it can be raised later without breaking old accounts.
  - Wrong password and unknown username return the same message, and an
    unknown username still runs a dummy hash so response time doesn't
    reveal which usernames exist.
  - Usernames are case-insensitive (`COLLATE NOCASE` + unique index).
  - A doctor account links to a `doctors` row: it takes over an
    unclaimed row with the same name and department (e.g. a seeded doctor)
    instead of creating a duplicate, otherwise creates a new one.
  - Accounts are local to the station and **not** written to
    `sync_audit_log` — credential hashes never leave the device.
  - Logging out destroys the whole workspace widget tree, so nothing from
    one user's session remains on screen for the next.
- **Patient numbers** (`desktop/data/numbering.py`): `PT-K7Q2-00042`.
  Plain running numbers would collide when two offline stations sync, so
  each database gets a random 4-character Crockford-base32 station code on
  first use and numbers count up per station. The counter lives in the
  same transaction as the patient insert, so a rollback never burns or
  reuses a number. Reports get `RPT-…` numbers the same way.
- **Returning patients**: Check-in can search by patient number, name or
  phone and issue a token against the existing record, so visits and
  reports accumulate in one history instead of creating duplicates.
- **Medical reports** (`desktop/services/report_service.py`): chief
  complaint, vitals (BP, pulse, temperature, weight, SpO₂), diagnosis,
  prescription, advice, follow-up date. Validated against plausible
  clinical ranges; temperature keeps its unit (°C and °F are both
  accepted). Only doctor accounts can author reports. **Append-only**:
  the app has no update or delete path for reports, so history is
  preserved as signed. Reports are registered with the sync entity
  registry, so they back up to the gateway like other business data.
- **PDF export** (`desktop/export/report_pdf.py`): A4 report rendered with
  Qt's own QTextDocument + QPdfWriter (no new dependency, works offline
  and inside the PyInstaller build). All user text is HTML-escaped. Writes
  go to a temporary file that's then moved into place, so a PDF locked
  open in a viewer raises a visible error instead of silently leaving the
  old file. The in-app report viewer shows the same HTML the PDF prints.
- **New UI** (`desktop/ui/`): floating icon sidebar, page header with
  user chip and log-out, stat cards, status badges, tables with avatars,
  segmented controls, and a sign-in screen with a brand panel. Pages:
  reception Dashboard / Check-in / Patients / Beds / Pharmacy; doctor
  Consultations / Patients (with reports) / Availability. Receptionists
  never see clinical content.
- **Schema upgrade path** (`desktop/data/db.py`): `CREATE TABLE IF NOT
  EXISTS` never alters an existing table, so `migrate()` now also adds
  `patients.patient_number` when missing and back-fills numbers for
  existing patients (oldest first, logged for sync). Rehearsed on a copy of
  a real pre-Cycle-6 database: 1 patient numbered, all row counts
  unchanged, `PRAGMA integrity_check` ok, no foreign-key violations, and a
  second `migrate()` changes nothing.

## Gap review against the lab documents (1A, 1B, 2A, 2B, 5, 6, 7)

Every requirement in the problem statement, scope, estimation, SQA plan,
SRS and design documents was checked against the code. These were missing
and were added this cycle:

| Requirement (document) | What was added |
| --- | --- |
| Sync Status Bar: online/offline badge, pending counter, Retry, tooltip, blue/orange/red (Lab 7 UI design) | Sync chip in the workspace header (`desktop/sync/sync_status.py`, `SyncChip` in `desktop/ui/app_shell.py`). The scheduler now records each pass and never lets a sync exception escape a Qt slot, since that would abort the app. |
| Printed token slips, automatic local print trigger (Lab 6 DFD outputs, Lab 7 transform mapping and UI) | 80 mm token slip (`desktop/export/token_slip.py`): Print slip button / Ctrl+P, and an "automatically after issuing" option saved per station. |
| Keyboard shortcuts, Ctrl+N, Enter to submit, doctor hotkeys (Lab 1A, Lab 7) | Enter submits check-in and issues for a single search match; Ctrl+N, Ctrl+F, Ctrl+1..6; F2/F3/F4 on the doctor console; Ctrl+S in the report editor. The patient being seen is highlighted in the queue. |
| Display broadcasts doctor status; status controls colour and sound (Lab 1B, Lab 6 data dictionary, Lab 7 "display chimes") | `DoctorStatusPayload` on the same UDP port (old token packets still decode), status changes broadcast immediately plus a 30 s heartbeat, display shows a doctors panel and chimes on each new call. |
| Doctor schedules; "Doctor Schedule Update" input and Doctor/Schedule table (Lab 1A, Lab 1B roadmap, Lab 2B FP analysis) | `doctor_schedules` table, weekly OPD days and hours set by each doctor, default hours for seeded doctors, synced like other business data. |
| Doctor availability for reception; Doctor Availability Query (Lab 1B, Lab 2B) | Read-only Doctors page for receptionists, with "in OPD today". |
| Stock Entry (Lab 2B FP analysis) | "Receive" on every pharmacy row adds a delivery of any size, instead of only +1/-1. |

Checked and already met: offline operation (FR-01), LAN broadcast (FR-02,
2 integration tests pass on loopback), background sync and LWW (FR-03,
FR-04), SQLCipher (NFR-02), standalone .exe (NFR-04), dual-role access,
patient search, bed matrix, low-stock alerts, the IssueQueueToken
algorithm, and the SQA sign-off figures below.

Not added, deliberately: pulling other stations' data from the cloud
(the DFD's "push/pull"). The gateway has no pull endpoint and can only be
integration-tested against Postgres in Docker, which this environment
doesn't have; it stays a carried-over item (see below and Cycle 4).
Archiving old logs is listed in Lab 1A as an anticipated limitation, not
a requirement.

## Follow-up requests

- **Calendar on the date chip** (`desktop/ui/day_overview.py`,
  `desktop/services/day_service.py`): pick a day to see its visits, new
  registrations and, for doctors, reports; busy days are bold in the
  calendar; double-click opens the patient or report. Days are local
  midnight-to-midnight, converted to UTC ranges, because timestamps are
  stored in UTC (matching on the UTC date would file a 1:00 AM IST
  check-in under the previous day).
- **Calendar pickers on date inputs** (`desktop/ui/date_field.py`): date of
  birth and follow-up date can be typed or picked from a calendar popup
  (button in the field, or Alt+Down). The popup only offers dates the
  field accepts: no future birth dates, no past follow-ups.
- **Hourly cloud sync**: the default interval was 30 seconds; it is now
  3600 (`HMS_SYNC_INTERVAL_SECONDS` still overrides it). A first pass runs
  5 seconds after launch so sessions shorter than an hour still upload,
  and the status bar's Retry syncs on demand. Changes waiting for the next
  pass are queued in `sync_audit_log`, so nothing is lost in between.

## Defects found and fixed during the cycle

- Ordering ties: two records written in the same microsecond sorted by
  random UUID, so "newest first" was non-deterministic. Now ties break on
  SQLite `rowid` (insertion order). Caught by the new history-order tests.
- Signing up as a seeded doctor's name created a second identical doctor
  (found in the UI preview); fixed by the take-over rule above.
- Beds sorted as text ("Bed 10" before "Bed 2"); now natural order.
- Variable fonts (Segoe UI Variable) embed in PDFs at a heavy weight, so
  every line printed bold; PDFs now use static fonts.
- A `&` in a button label became a keyboard-mnemonic marker and vanished.

## Metrics measured this cycle

- Tests: **258 passed** (unit + system, excluding the `perf` marker as in
  CI), up from 93. New coverage: accounts and hashing, patient numbering
  and the schema upgrade, intake validation, reports and their
  validation, PDF export, dashboard figures, schedules, sync status,
  token slips, shortcuts, the doctor-status protocol and every new screen.
  LAN broadcast integration tests: 2 passed.
- Coverage of business logic (UI excluded, as configured):
  **94%** against the SQA plan's 80% sign-off bar.
- NFR-01 launch time: process start to painted window **0.5 s** (target
  < 3 s).
- NFR-01 write latency, `issue_queue_token` (now including intake
  validation and patient numbering), 500 writes on the Windows dev
  machine: **p50 0.27 ms, p99 4.4 ms**, under the 10 ms target.
  `pytest -m perf` passes.
- WCAG AA contrast: every text/background pair in the theme checked at
  ≥ 4.5:1 (spec colours that failed were darkened; see
  `common/design_tokens.py`).

## Carried-over risks / decisions

- Accounts are per station. A clinic with several stations creates
  accounts on each; syncing credentials was deliberately left out.
- No password reset or account management screen yet; no lockout after
  repeated failed sign-ins (the slow hash limits guessing speed).
- Role gating is still UI-level on a single station, as in earlier
  cycles — anyone with the database file and key could read it directly.
  `HMS_DB_ENCRYPTION_KEY` must be set for real deployments (Cycle 5).
- "Today" for queue numbering and dashboard counts is the UTC date (as
  since Cycle 1); report dates, dates of birth and follow-ups use the
  local date.
- The sync worker pushes reports but doesn't pull other stations' data
  (unchanged from Cycle 4), so cross-station patient lookup needs a pull
  step before it works.
