"""Shared helper every other repository uses to log its mutations.

sync_audit_log is the single source of truth for "what needs syncing" -- the
Cycle 4 sync worker only ever reads PENDING rows from here, never scans
business tables directly.
"""

from __future__ import annotations

import sqlite3

from common.clock import now_iso


def log_mutation(
    conn: sqlite3.Connection, *, entity_name: str, record_id: str, action_type: str
) -> None:
    conn.execute(
        """INSERT INTO sync_audit_log (entity_name, record_id, action_type, sync_status, updated_at)
           VALUES (?, ?, ?, 'PENDING', ?)""",
        (entity_name, record_id, action_type, now_iso()),
    )


def list_pending(conn: sqlite3.Connection) -> list[dict]:
    """PENDING rows the sync worker needs to push, oldest first."""
    rows = conn.execute("""SELECT sync_id, entity_name, record_id, action_type, updated_at
           FROM sync_audit_log WHERE sync_status = 'PENDING' ORDER BY sync_id ASC""").fetchall()
    return [
        {
            "sync_id": r[0],
            "entity_name": r[1],
            "record_id": r[2],
            "action_type": r[3],
            "updated_at": r[4],
        }
        for r in rows
    ]


def get_entity_for_sync_id(conn: sqlite3.Connection, sync_id: int) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT entity_name, record_id FROM sync_audit_log WHERE sync_id = ?", (sync_id,)
    ).fetchone()
    return (row[0], row[1]) if row else None


def mark_status(conn: sqlite3.Connection, sync_id: int, status: str) -> None:
    conn.execute("UPDATE sync_audit_log SET sync_status = ? WHERE sync_id = ?", (status, sync_id))
