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
