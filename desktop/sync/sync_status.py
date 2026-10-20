"""What the sync status bar shows: a colour, a short label and a tooltip,
derived from sync_audit_log counts and the scheduler's last pass.

Colours follow the UI design spec: blue = synced, orange = working from
the offline cache, red = conflict (or a failed pass).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from common.clock import format_local_datetime
from common.dto import SyncResult, SyncStatus
from desktop.sync.sync_worker import SyncState


@dataclass(frozen=True, slots=True)
class SyncSnapshot:
    tone: str  # "synced" (blue), "offline" (orange) or "conflict" (red)
    label: str
    detail: str
    pending: int


def audit_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {"PENDING": 0, "SYNCED": 0, "CONFLICT": 0}
    rows = conn.execute("SELECT sync_status, COUNT(*) FROM sync_audit_log GROUP BY sync_status")
    for status, count in rows:
        counts[status] = count
    return counts


def _pending_text(pending: int) -> str:
    return f"{pending} change{'s' if pending != 1 else ''} waiting to upload"


def sync_snapshot(
    conn: sqlite3.Connection,
    *,
    gateway_url: str | None,
    state: SyncState | None,
    last_attempt_at: str | None,
    last_results: list[SyncResult],
    last_error: str | None,
) -> SyncSnapshot:
    counts = audit_counts(conn)
    pending = counts["PENDING"]
    attempted = (
        f"Last attempt: {format_local_datetime(last_attempt_at)}"
        if last_attempt_at
        else "No sync attempted yet this session"
    )
    totals = (
        f"Uploaded: {counts['SYNCED']}  ·  Waiting: {pending}  ·  "
        f"Resolved conflicts: {counts['CONFLICT']}"
    )

    if gateway_url is None:
        return SyncSnapshot(
            "offline",
            f"Offline · {pending} pending" if pending else "Offline",
            "Cloud sync isn't set up on this station (HMS_GATEWAY_URL), so everything "
            f"is kept in the encrypted local database.\n{_pending_text(pending)}.",
            pending,
        )

    if last_error is not None:
        return SyncSnapshot(
            "conflict",
            "Sync error",
            f"The last sync pass failed: {last_error}\nNothing was lost; changes stay "
            f"queued and are retried automatically.\n{attempted}\n{totals}",
            pending,
        )

    conflicts = sum(result.status == SyncStatus.CONFLICT for result in last_results)
    if conflicts:
        return SyncSnapshot(
            "conflict",
            f"{conflicts} conflict{'s' if conflicts != 1 else ''} resolved",
            f"The cloud had newer versions of {conflicts} record(s); the newest version "
            f"was kept here (Last-Write-Wins).\n{attempted}\n{totals}",
            pending,
        )

    if state is None or state == SyncState.OFFLINE_LOCAL:
        return SyncSnapshot(
            "offline",
            f"Offline · {pending} pending" if pending else "Offline",
            f"Can't reach the cloud at {gateway_url}. Working from the local database; "
            f"{_pending_text(pending)}.\n{attempted}\n{totals}",
            pending,
        )

    return SyncSnapshot(
        "synced",
        "Synced" if pending == 0 else f"Online · {pending} pending",
        f"Connected to {gateway_url}.\n{attempted}\n{totals}",
        pending,
    )
