from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation


class DoctorsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT doctor_id, full_name, dept_id, status FROM doctors ORDER BY full_name"
        ).fetchall()
        return [
            {"doctor_id": r[0], "full_name": r[1], "dept_id": r[2], "status": r[3]} for r in rows
        ]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]

    def insert(
        self, *, doctor_id: str, full_name: str, dept_id: int, status: str = "AVAILABLE"
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO doctors (doctor_id, full_name, dept_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doctor_id, full_name, dept_id, status, timestamp, timestamp),
        )
        log_mutation(self._conn, entity_name="doctors", record_id=doctor_id, action_type="INSERT")

    def update_status(self, doctor_id: str, new_status: str) -> None:
        timestamp = now_iso()
        self._conn.execute(
            "UPDATE doctors SET status = ?, updated_at = ? WHERE doctor_id = ?",
            (new_status, timestamp, doctor_id),
        )
        log_mutation(self._conn, entity_name="doctors", record_id=doctor_id, action_type="UPDATE")
