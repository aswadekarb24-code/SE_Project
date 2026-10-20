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
            """SELECT token_id, patient_id, dept_id, token_num, status,
                      issued_date, created_at, updated_at
               FROM queue_tokens WHERE token_id = ?""",
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
            "issued_date": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    def get_oldest_waiting(self, dept_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT token_id FROM queue_tokens WHERE dept_id = ? AND status = 'WAITING' "
            "ORDER BY token_num ASC LIMIT 1",
            (dept_id,),
        ).fetchone()
        return row[0] if row else None

    def get_latest_called(self, dept_id: int, issued_date: str) -> str | None:
        """The department's most recently called token that hasn't been
        completed yet, so a doctor who logs out mid-consultation picks up
        where they left off.
        """
        row = self._conn.execute(
            """SELECT token_id FROM queue_tokens
               WHERE dept_id = ? AND issued_date = ? AND status = 'CALLED'
               ORDER BY updated_at DESC LIMIT 1""",
            (dept_id, issued_date),
        ).fetchone()
        return row[0] if row else None

    def list_for_date(self, issued_date: str, dept_id: int | None = None) -> list[dict]:
        """A day's tokens (optionally one department's) with patient and
        department details, in queue order.
        """
        sql = """SELECT t.token_id, t.token_num, t.status, t.dept_id, d.name,
                        p.patient_id, p.patient_number, p.full_name, t.updated_at
                 FROM queue_tokens t
                 JOIN patients p ON p.patient_id = t.patient_id
                 JOIN departments d ON d.dept_id = t.dept_id
                 WHERE t.issued_date = ?"""
        params: list = [issued_date]
        if dept_id is not None:
            sql += " AND t.dept_id = ?"
            params.append(dept_id)
        sql += " ORDER BY t.dept_id, t.token_num"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "token_id": r[0],
                "token_num": r[1],
                "status": r[2],
                "dept_id": r[3],
                "dept_name": r[4],
                "patient_id": r[5],
                "patient_number": r[6],
                "full_name": r[7],
                "updated_at": r[8],
            }
            for r in rows
        ]

    def list_for_patient(self, patient_id: str) -> list[dict]:
        """A patient's visits (one per token), newest first."""
        rows = self._conn.execute(
            """SELECT t.token_id, t.token_num, t.status, t.issued_date, d.name
               FROM queue_tokens t JOIN departments d ON d.dept_id = t.dept_id
               WHERE t.patient_id = ?
               ORDER BY t.created_at DESC, t.rowid DESC""",
            (patient_id,),
        ).fetchall()
        return [
            {
                "token_id": r[0],
                "token_num": r[1],
                "status": r[2],
                "issued_date": r[3],
                "dept_name": r[4],
            }
            for r in rows
        ]

    def count_by_status(self, issued_date: str, dept_id: int | None = None) -> dict[str, int]:
        sql = "SELECT status, COUNT(*) FROM queue_tokens WHERE issued_date = ?"
        params: list = [issued_date]
        if dept_id is not None:
            sql += " AND dept_id = ?"
            params.append(dept_id)
        counts = {"WAITING": 0, "CALLED": 0, "DONE": 0}
        for status, count in self._conn.execute(sql + " GROUP BY status", params):
            counts[status] = count
        return counts

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
