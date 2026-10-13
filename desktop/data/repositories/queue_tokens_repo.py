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
