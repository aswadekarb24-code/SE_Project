from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation


class QueueTokensRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def next_token_num(self, dept_id: int, issued_date: str) -> int:
        """Implements the design doc's `MAX(token_num) WHERE dept_id = ? AND
        date = ?` step -- numbering resets per department, per day.
        """
        row = self._conn.execute(
            "SELECT MAX(token_num) FROM queue_tokens WHERE dept_id = ? AND issued_date = ?",
            (dept_id, issued_date),
        ).fetchone()
        max_num = row[0]
        return 1 if max_num is None else max_num + 1

    def get(self, token_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT token_id, patient_id, dept_id, token_num, status FROM queue_tokens "
            "WHERE token_id = ?",
            (token_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "token_id": row[0],
            "patient_id": row[1],
            "dept_id": row[2],
            "token_num": row[3],
            "status": row[4],
        }

    def get_oldest_waiting(self, dept_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT token_id FROM queue_tokens WHERE dept_id = ? AND status = 'WAITING' "
            "ORDER BY token_num ASC LIMIT 1",
            (dept_id,),
        ).fetchone()
        return row[0] if row else None

    def update_status(self, token_id: str, new_status: str) -> None:
        timestamp = now_iso()
        self._conn.execute(
            "UPDATE queue_tokens SET status = ?, updated_at = ? WHERE token_id = ?",
            (new_status, timestamp, token_id),
        )
        log_mutation(
            self._conn, entity_name="queue_tokens", record_id=token_id, action_type="UPDATE"
        )

    def insert(
        self,
        *,
        token_id: str,
        patient_id: str,
        dept_id: int,
        token_num: int,
        status: str,
        issued_date: str,
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO queue_tokens
               (token_id, patient_id, dept_id, token_num, status,
                issued_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (token_id, patient_id, dept_id, token_num, status, issued_date, timestamp, timestamp),
        )
        log_mutation(
            self._conn, entity_name="queue_tokens", record_id=token_id, action_type="INSERT"
        )
