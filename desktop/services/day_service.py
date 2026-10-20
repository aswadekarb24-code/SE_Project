"""Everything that happened on one calendar day: visits (queue tokens),
new registrations and consultation reports. Backs the header calendar.

A "day" here is the local calendar day (midnight to midnight on this
computer's clock). Timestamps are stored in UTC, so each day is turned into
a UTC range first. Matching on the UTC date instead would put, say, an
1:00 AM IST check-in on the previous day.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone

from desktop.data.repositories.medical_reports_repo import MedicalReportsRepository
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def day_bounds(day: date) -> tuple[str, str]:
    """[start, end) of the local day `day`, as UTC ISO timestamps in the same
    format the app stores, so plain string comparison selects the day.
    """
    start = datetime.combine(day, time.min).astimezone()  # local midnight
    end = datetime.combine(day + timedelta(days=1), time.min).astimezone()
    return _utc_iso(start), _utc_iso(end)


def local_date(iso_timestamp: str) -> date:
    return datetime.fromisoformat(iso_timestamp).astimezone().date()


def local_time(iso_timestamp: str) -> str:
    """A stored UTC timestamp as local "2:05 PM"."""
    moment = datetime.fromisoformat(iso_timestamp).astimezone()
    return f"{moment.hour % 12 or 12}:{moment:%M %p}"


def day_overview(conn: sqlite3.Connection, day: date, *, include_reports: bool) -> dict:
    """The day's visits, registrations and (for doctors) reports.
    Receptionists don't get report contents, so `include_reports` is False
    for them and "reports" is an empty list.
    """
    start, end = day_bounds(day)
    return {
        "visits": QueueTokensRepository(conn).list_created_between(start, end),
        "registrations": PatientsRepository(conn).list_created_between(start, end),
        "reports": (
            MedicalReportsRepository(conn).list_created_between(start, end)
            if include_reports
            else []
        ),
    }


def active_days(conn: sqlite3.Connection, first: date, last: date) -> set[date]:
    """Local days between `first` and `last` (inclusive) with any visit or
    report, for highlighting in the calendar.
    """
    start, _ = day_bounds(first)
    _, end = day_bounds(last)
    stamps = QueueTokensRepository(conn).created_timestamps_between(start, end)
    stamps += MedicalReportsRepository(conn).created_timestamps_between(start, end)
    return {local_date(stamp) for stamp in stamps}
