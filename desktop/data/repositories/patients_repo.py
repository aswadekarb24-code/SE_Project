from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation

_COLUMNS = "patient_id, patient_number, full_name, dob, gender, contact_no, created_at, updated_at"


def _to_dict(row: tuple) -> dict:
    return {
        "patient_id": row[0],
        "patient_number": row[1],
        "full_name": row[2],
        "dob": row[3],
        "gender": row[4],
        "contact_no": row[5],
        "created_at": row[6],
        "updated_at": row[7],
    }


def like_pattern(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, with LIKE's own wildcards
    escaped (pair it with ESCAPE '\\'), so searching "50%" means those
    characters, not "50 followed by anything".
    """
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class PatientsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def exists(self, patient_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        return row is not None

    def get(self, patient_id: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        return None if row is None else _to_dict(row)

    def get_by_number(self, patient_number: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM patients WHERE patient_number = ? COLLATE NOCASE",
            (patient_number,),
        ).fetchone()
        return None if row is None else _to_dict(row)

    def search(self, query: str = "", limit: int = 200) -> list[dict]:
        """Newest first. An empty query lists everyone (up to `limit`);
        otherwise matches patient number, name or contact number.
        """
        pattern = like_pattern(query.strip())
        rows = self._conn.execute(
            f"""SELECT {_COLUMNS} FROM patients
                WHERE patient_number LIKE ? ESCAPE '\\'
                   OR full_name LIKE ? ESCAPE '\\'
                   OR contact_no LIKE ? ESCAPE '\\'
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [_to_dict(row) for row in rows]

    def list_created_between(self, start: str, end: str) -> list[dict]:
        """Patients registered in [start, end) (UTC ISO timestamps), oldest first."""
        rows = self._conn.execute(
            f"""SELECT {_COLUMNS} FROM patients
                WHERE created_at >= ? AND created_at < ?
                ORDER BY created_at, rowid""",
            (start, end),
        ).fetchall()
        return [_to_dict(row) for row in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]

    def count_created_on(self, iso_date: str) -> int:
        """Patients whose created_at (a UTC ISO timestamp) falls on `iso_date`."""
        return self._conn.execute(
            "SELECT COUNT(*) FROM patients WHERE substr(created_at, 1, 10) = ?", (iso_date,)
        ).fetchone()[0]

    def insert(
        self,
        *,
        patient_id: str,
        patient_number: str,
        full_name: str,
        dob: str,
        gender: str | None,
        contact_no: str | None,
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO patients
               (patient_id, patient_number, full_name, dob, gender, contact_no,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, patient_number, full_name, dob, gender, contact_no, timestamp, timestamp),
        )
        log_mutation(self._conn, entity_name="patients", record_id=patient_id, action_type="INSERT")

    def set_patient_number(self, patient_id: str, patient_number: str) -> None:
        self._conn.execute(
            "UPDATE patients SET patient_number = ?, updated_at = ? WHERE patient_id = ?",
            (patient_number, now_iso(), patient_id),
        )
        log_mutation(self._conn, entity_name="patients", record_id=patient_id, action_type="UPDATE")
