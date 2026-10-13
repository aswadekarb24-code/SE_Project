# Hybrid Offline-First HMS

A lightweight, offline-first hospital management system: a local-first desktop
app for reception/doctor workflows, an embedded LAN display client for
waiting-room queues, and background sync to a cloud Postgres backend
(Supabase in production, local Docker Postgres in dev).

See `PLAN.md` for the project brief and `docs/` for the original planning
documents. The implementation plan (spiral-model cycles, architecture,
testing/metrics strategy) lives in `docs/progress/`.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker + Docker Compose (for the cloud sync gateway + local Postgres)

No other setup is required on Windows, Linux, or macOS — `uv` and Docker both
manage their own toolchains.

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

The gateway exposes `GET /health` at `http://localhost:8000/health` once the
Compose stack is up.

## Configuration

Copy `.env.example` to `.env` and adjust `DATABASE_URL` to point at a real
Supabase/Postgres instance when ready — this is the only change needed to
move the sync layer from local dev to production (see `SyncProvider` in
`common/sync_provider.py`).

## Project layout

- `common/` — schema, shared DTOs, the `SyncProvider` DI boundary, LAN
  broadcast protocol. No GUI/web-framework dependencies.
- `desktop/` — PyQt6 app: UI, local SQLite data layer, sync worker, LAN
  broadcaster.
- `display_sim/` — software simulator for the embedded LAN display node.
- `gateway/` — FastAPI cloud sync gateway.
- `tests/` — `unit/` (no external services), `integration/` (needs Docker
  Compose), `system/` (end-to-end scenarios).
- `docker-compose.yml` — local Postgres + gateway.
- `build/` — PyInstaller/Inno Setup packaging config (added in a later cycle).
