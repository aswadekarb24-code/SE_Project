# Cycle 0 — Walking Skeleton

## Objectives & risks addressed

De-risk the development environment and the integration of the core stack
before any business logic is written: Python + `uv` across Windows/Linux/
macOS, PyQt6 running headless in tests, SQLite in WAL mode, and the
FastAPI-gateway-to-Postgres path via Docker Compose. Also establishes the
`SyncProvider` DI boundary (as a `NoOpSyncProvider`) so every later cycle
builds on top of an already-wired, already-offline-by-default sync seam.

## What shipped (demoable)

- Repo scaffold: `common/`, `desktop/`, `display_sim/`, `gateway/`, `tests/`,
  `docker/`, `build/` — with `common/` kept free of PyQt6/FastAPI/Tkinter
  imports so it's independently testable and reusable by all three runtime
  processes.
- `common/sync_provider.py` — `SyncProvider` ABC + `NoOpSyncProvider`.
- `common/dto.py` — shared dataclasses (`SyncRecord`, `SyncResult`,
  `QueueTokenIssued`, etc.) for later cycles.
- `common/schema/sync_audit_log.py` — first schema module; the DDL every
  future business-table mutation will write an audit row into.
- `desktop/main.py` + `desktop/data/db.py` — a PyQt6 window that opens a
  local SQLite DB in WAL mode and applies migrations on startup.
- `gateway/main.py` + `gateway/db.py` — FastAPI app with a `/health` endpoint
  that round-trips a real query through SQLAlchemy to Postgres.
- `docker-compose.yml` + `docker/gateway.Dockerfile` (multi-stage, slim) —
  `docker compose up -d` brings up Postgres + the gateway on any OS.
- `.pre-commit-config.yaml` (Black, Ruff, fast unit tests) and
  `.github/workflows/ci.yml` (lint + unit tests on Linux/Windows/macOS
  runners, plus a Docker-Compose-backed integration job).
- 10 tests across `tests/unit/` and `tests/integration/` (DB WAL mode,
  migration idempotency, `NoOpSyncProvider` behavior, PyQt6 window
  construction headless via `QT_QPA_PLATFORM=offscreen`, gateway `/health`
  against the live Compose stack).

Demo performed: `uv sync --extra dev --extra gateway`, `uv run pytest
tests/unit` (all pass), `docker compose up -d`, `curl localhost:8000/health`
→ `{"status": "ok"}`, `uv run pytest tests/integration` (passes against the
live stack), `docker compose down -v`.

## Metrics measured this cycle

- Unit test coverage: 93% (9 unit tests; Cycle 0 has negligible business
  logic, so the ≥80% core-logic gate formally starts applying from Cycle 1).
- Local write latency: not yet applicable — no business-table writes exist
  yet (Cycle 1).
- LAN broadcast latency: not yet applicable (Cycle 2).
- Soak test: not yet applicable (Cycle 4).
- Open defects: P1 0 / P2 0 / P3 0 / P4 0.
- Cross-OS verification: `uv sync` + `uv run pytest tests/unit` run locally
  on Linux; CI matrix (`ubuntu-latest`, `windows-latest`, `macos-latest`)
  configured to verify Windows/macOS on every push/PR.
- Gateway container: Postgres `healthcheck` (`pg_isready`) confirmed green
  before gateway start; `/health` confirmed reachable and DB-backed.

## Carried-over risks / decisions for next cycle

- Cycle 1 will implement `IssueQueueToken()` and the `patients`/
  `queue_tokens` schema exactly as specified in `docs/` — this is the first
  cycle where the ≥10ms write-latency and WAL power-interruption test
  protocols become meaningful and must be measured.
- The CI Windows/macOS legs have not yet been exercised against a real push
  (no remote yet) — confirm on first push to `main`.
- Port 5432 on the host machine was already occupied by an unrelated local
  Postgres instance; `docker-compose.yml` maps Postgres to host port 5433
  to avoid collisions. Internal container-to-container traffic (gateway →
  postgres) is unaffected since it uses the Compose service name on 5432.
