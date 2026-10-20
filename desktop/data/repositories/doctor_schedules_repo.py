from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation

_COLUMNS = "doctor_id, opd_days, start_time, end_time, created_at, updated_at"


def _to_dict(row: tuple) -> dict:
    return {
        "doctor_id": row[0],
        "opd_days": row[1],
        "start_time": row[2],
        "end_time": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }


class DoctorSchedulesRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, doctor_id: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM doctor_schedules WHERE doctor_id = ?", (doctor_id,)
        ).fetchone()
        return None if row is None else _to_dict(row)

    def list_all(self) -> dict[str, dict]:
        """Schedules keyed by doctor_id."""
        rows = self._conn.execute(f"SELECT {_COLUMNS} FROM doctor_schedules").fetchall()
        return {row[0]: _to_dict(row) for row in rows}

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM doctor_schedules").fetchone()[0]

    def upsert(self, *, doctor_id: str, opd_days: str, start_time: str, end_time: str) -> None:
        timestamp = now_iso()
        exists = self.get(doctor_id) is not None
        self._conn.execute(
            """INSERT INTO doctor_schedules
               (doctor_id, opd_days, start_time, end_time, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (doctor_id) DO UPDATE SET
                   opd_days = excluded.opd_days,
                   start_time = excluded.start_time,
                   end_time = excluded.end_time,
                   updated_at = excluded.updated_at""",
            (doctor_id, opd_days, start_time, end_time, timestamp, timestamp),
        )
        log_mutation(
            self._conn,
            entity_name="doctor_schedules",
            record_id=doctor_id,
            action_type="UPDATE" if exists else "INSERT",
        )
