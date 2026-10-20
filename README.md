# Hybrid Offline-First HMS

A lightweight, offline-first hospital management system: a local-first desktop
app for reception/doctor workflows, an embedded LAN display client for
waiting-room queues, and background sync to a cloud Postgres backend
(Supabase in production, local Docker Postgres in dev).

## What it does

- **Sign-in with per-person accounts.** Receptionist and Doctor accounts
  (create one on the sign-in screen); the role decides which screens you
  get. Passwords are stored only as salted PBKDF2-SHA256 hashes, and
  accounts stay on the station (never synced).
- **Front desk:** dashboard with today's numbers, check-in for new and
  returning patients, queue tokens broadcast to LAN displays, bed board and
  pharmacy stock.
- **Permanent patient numbers** like `PT-K7Q2-00042`, assigned at
  registration. The middle part is a per-station code, so two stations
  registering offline can never hand out the same number.
- **Doctors:** call the next patient, write a consultation report (vitals,
  diagnosis, prescription, advice, follow-up), browse each patient's full
  history, and export any report as a PDF. Saved reports are append-only,
  so a patient's medical history is preserved exactly as written.
- **Doctor schedules:** each doctor sets weekly OPD hours; reception sees
  who's available and who's in OPD today on the Doctors page.
- **Token slips:** print a slip for the patient after check-in (Ctrl+P), or
  turn on automatic printing to the default printer.
- **Sync status bar:** blue when synced, orange when working from the
  offline cache, red on a conflict or failed pass; hover for details,
  click to retry.
- **Keyboard-first:** Enter submits check-in, Ctrl+N new patient, Ctrl+F
  search, Ctrl+1..6 switch pages, F2/F3/F4 call next / write report /
  complete on the doctor console, Ctrl+S saves a report.
- **Waiting-room display** shows the queue and doctor availability, and
  chimes when a patient is called.

See `PLAN.md` for the project brief and `docs/` for the original planning
documents. The implementation plan (spiral-model cycles, architecture,
testing/metrics strategy) lives in `docs/progress/`.

**For full per-OS setup, testing, and Windows `.exe`/installer build
instructions (including a clean-VM release checklist), see
[`SETUP.md`](SETUP.md).** The sections below are a quick-start summary.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker + Docker Compose (for the cloud sync gateway + local Postgres)

`uv` and Docker both manage their own toolchains, so there's little else to
install — **except** on minimal/headless Linux, where PyQt6 needs a handful
of system graphics/IPC libraries it doesn't bundle itself. See
[`SETUP.md`](SETUP.md#21-install-prerequisites) for the exact (verified,
not guessed) package list — the same one `.github/workflows/ci.yml` installs
for CI.

## Setup

```bash
# Desktop app, display simulator, and all tests
uv sync --extra dev --extra gateway

# Cloud sync gateway + local Postgres (stands in for Supabase in dev)
docker compose up -d
```

## Running

```bash
# Desktop app
uv run python -m desktop.main

# Unit tests (fast, no Docker required)
uv run pytest tests/unit

# Integration tests (requires `docker compose up -d` first)
uv run pytest tests/integration

# Lint/format
uv run ruff check .
uv run black .
```

The gateway exposes `GET /health` and `POST /sync/push` once the Compose
stack is up.

## Configuration

Copy `.env.example` to `.env` and adjust `DATABASE_URL` to point at a real
Supabase/Postgres instance when ready — this is the only change needed to
move the sync layer from local dev to production (see `SyncProvider` in
`common/sync_provider.py`).

By default the desktop app stays fully offline (`NoOpSyncProvider`). Set
`HMS_GATEWAY_URL` (e.g. `http://localhost:8000`, with the Compose stack up)
to enable the real background sync worker, which pushes pending changes
every `HMS_SYNC_INTERVAL_SECONDS` (default 30) and resolves conflicts via
Last-Write-Wins (see `desktop/sync/`).

The local SQLite DB is encrypted at rest via SQLCipher (NFR-02). Set
`HMS_DB_ENCRYPTION_KEY` to a real secret for any non-dev deployment — if
unset, `desktop/data/db.py` falls back to a fixed, publicly-known dev key so
local dev/tests work with zero setup. Set `HMS_REQUIRE_TLS=true` on the
gateway once a TLS-terminating reverse proxy is in front of it in
production; local docker-compose dev has no cert, so this stays off there.

## Packaging (Windows .exe)

```bash
# One-folder build, for fast dev iteration (produces dist/HMS/HMS.exe)
uv run pyinstaller build/pyinstaller.spec

# One-file build, for an actual release artifact (produces dist/HMS.exe)
uv run pyinstaller build/pyinstaller.release.spec
```

Both specs exclude `tests/`, `gateway/`, and dev-only packages, so the
desktop build never bundles FastAPI/SQLAlchemy/pytest/etc. `build/installer.iss`
wraps the one-file build into a Windows installer via
[Inno Setup](https://jrsoftware.org/isinfo.php) — compile it on Windows
after the release build. See **[`SETUP.md`](SETUP.md#15-build-the-windows-exe)**
for the full step-by-step Windows build + installer + clean-VM verification
checklist, and `docs/progress/cycle-5.md` for what's been verified on Linux
vs. what still needs an actual Windows machine.

## Project layout

- `common/` — schema, shared DTOs, the `SyncProvider` DI boundary, LAN
  broadcast protocol. No GUI/web-framework dependencies.
- `desktop/` — PyQt6 app: UI (`ui/`: sign-in, app shell, pages, theme),
  local SQLite data layer, services (accounts, patients, reports), PDF
  export (`export/`), sync worker, LAN broadcaster.
- `display_sim/` — software simulator for the embedded LAN display node.
- `gateway/` — FastAPI cloud sync gateway.
- `tests/` — `unit/` (no external services), `integration/` (needs Docker
  Compose), `system/` (end-to-end scenarios).
- `docker-compose.yml` — local Postgres + gateway.
- `build/` — PyInstaller/Inno Setup packaging config (added in a later cycle).
