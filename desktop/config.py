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

GATEWAY_URL = os.environ.get("HMS_GATEWAY_URL")
DEFAULT_SYNC_INTERVAL_SECONDS = 3600  # hourly
SYNC_INTERVAL_SECONDS = float(
    os.environ.get("HMS_SYNC_INTERVAL_SECONDS", str(DEFAULT_SYNC_INTERVAL_SECONDS))
)
# First pass this soon after launch, so a session shorter than the interval
# still uploads its changes.
STARTUP_SYNC_DELAY_SECONDS = 5
