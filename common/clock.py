"""Single source of truth for timestamps used as created_at/updated_at and as
the Last-Write-Wins comparison key during cloud sync (Cycle 4).
"""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Microsecond-precision ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def today_iso() -> str:
    """ISO date (YYYY-MM-DD), used for per-day/per-department token numbering."""
    return datetime.now(timezone.utc).date().isoformat()
