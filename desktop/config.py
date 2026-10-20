"""Environment-driven configuration. Swapping local dev (docker-compose
gateway) for a production gateway fronting Supabase is a single env var
change here -- see common/sync_provider.py for why this boundary exists.

HMS_GATEWAY_URL unset => the app stays fully offline (NoOpSyncProvider),
exactly matching PLAN.md's "offline-first prototype, DI-ready for cloud
later" requirement.

Cloud sync runs once shortly after launch and then every hour by default
(HMS_SYNC_INTERVAL_SECONDS overrides it). Changes made in between are
queued in sync_audit_log, so nothing is lost while waiting; the sync
status bar's Retry button uploads immediately.
"""

from __future__ import annotations

import os
from pathlib import Path

# Sync settings the desktop app may take from a .env file (the same file the
# gateway reads), so launching it doesn't need environment variables set by
# hand. Deliberately an allow-list: DATABASE_URL is the gateway's secret,
# and HMS_DB_ENCRYPTION_KEY must not change underneath an existing local
# database (it would no longer open), so neither is ever read from here.
DOTENV_KEYS = ("HMS_GATEWAY_URL", "HMS_SYNC_INTERVAL_SECONDS")


def load_dotenv(*paths: Path) -> None:
    """Copy DOTENV_KEYS from the first .env found into os.environ, without
    overriding anything already set. HMS_LOAD_DOTENV=0 turns this off (the
    test suite does, so tests never sync to a real gateway).
    """
    if os.environ.get("HMS_LOAD_DOTENV") == "0":
        return
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key in DOTENV_KEYS and key not in os.environ:
                os.environ[key] = value.strip("'\"")
        return


load_dotenv(Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env")

GATEWAY_URL = os.environ.get("HMS_GATEWAY_URL") or None
DEFAULT_SYNC_INTERVAL_SECONDS = 3600  # hourly
SYNC_INTERVAL_SECONDS = float(
    os.environ.get("HMS_SYNC_INTERVAL_SECONDS", str(DEFAULT_SYNC_INTERVAL_SECONDS))
)
# First pass this soon after launch, so a session shorter than the interval
# still uploads its changes.
STARTUP_SYNC_DELAY_SECONDS = 5
