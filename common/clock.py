"""Single source of truth for timestamps used as created_at/updated_at and as
the Last-Write-Wins comparison key during cloud sync (Cycle 4).
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def now_iso() -> str:
    """Microsecond-precision ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def local_today() -> date:
    """Today's date on this machine's clock -- what a person at the desk
    means by "today" (dates of birth, report dates, follow-ups).
    """
    return datetime.now().astimezone().date()


def format_local_datetime(iso_timestamp: str) -> str:
    """A stored UTC timestamp as local time for display, e.g.
    "20 Oct 2026, 2:45 PM".
    """
    local = datetime.fromisoformat(iso_timestamp).astimezone()
    return f"{local.day} {local:%b %Y}, {local.hour % 12 or 12}:{local:%M %p}"


def format_date(iso_date: str) -> str:
    """An ISO date for display, e.g. "2026-10-20" -> "20 Oct 2026"."""
    value = date.fromisoformat(iso_date)
    return f"{value.day} {value:%b %Y}"


def today_iso() -> str:
    """ISO date (YYYY-MM-DD), used for per-day/per-department token numbering."""
    return datetime.now(timezone.utc).date().isoformat()
