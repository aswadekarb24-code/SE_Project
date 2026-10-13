"""Environment-driven configuration. Swapping local dev (docker-compose
gateway) for a production gateway fronting Supabase is a single env var
change here -- see common/sync_provider.py for why this boundary exists.

HMS_GATEWAY_URL unset => the app stays fully offline (NoOpSyncProvider),
exactly matching PLAN.md's "offline-first prototype, DI-ready for cloud
later" requirement.
"""

from __future__ import annotations

import os

GATEWAY_URL = os.environ.get("HMS_GATEWAY_URL")
SYNC_INTERVAL_SECONDS = float(os.environ.get("HMS_SYNC_INTERVAL_SECONDS", "30"))
