from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation


class BedsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT bed_id, label, status FROM beds ORDER BY label"
        ).fetchall()
        return [{"bed_id": r[0], "label": r[1], "status": r[2]} for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM beds").fetchone()[0]

    def insert(self, *, bed_id: str, label: str, status: str = "AVAILABLE") -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO beds (bed_id, label, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (bed_id, label, status, timestamp, timestamp),
        )
        log_mutation(self._conn, entity_name="beds", record_id=bed_id, action_type="INSERT")

    def update_status(self, bed_id: str, new_status: str) -> None:
        timestamp = now_iso()
        self._conn.execute(
            "UPDATE beds SET status = ?, updated_at = ? WHERE bed_id = ?",
            (new_status, timestamp, bed_id),
        )
        log_mutation(self._conn, entity_name="beds", record_id=bed_id, action_type="UPDATE")
