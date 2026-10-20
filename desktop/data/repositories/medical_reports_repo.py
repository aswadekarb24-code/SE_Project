"""Consultation reports. Insert and read only: a saved report is never
updated or deleted (see common/schema/medical_reports.py).
"""

from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation

# Every column, in table order. get() returns all of them, which is also
# the sync payload (desktop/sync/entity_registry.py).
FIELDS = (
    "report_id",
    "report_number",
    "patient_id",
    "doctor_id",
    "doctor_name",
    "dept_id",
    "token_id",
    "visit_date",
    "chief_complaint",
    "blood_pressure",
    "pulse_rate",
    "temperature",
    "weight",
    "spo2",
    "diagnosis",
    "prescription",
    "advice",
    "follow_up_date",
    "created_at",
    "updated_at",
)
_COLUMNS = ", ".join(FIELDS)


class MedicalReportsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, report_id: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM medical_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        return None if row is None else dict(zip(FIELDS, row, strict=True))

    def list_for_patient(self, patient_id: str) -> list[dict]:
        """Newest first. rowid breaks timestamp ties in insertion order."""
        rows = self._conn.execute(
            f"""SELECT {_COLUMNS} FROM medical_reports WHERE patient_id = ?
                ORDER BY created_at DESC, rowid DESC""",
            (patient_id,),
        ).fetchall()
        return [dict(zip(FIELDS, row, strict=True)) for row in rows]

    def count_by_doctor_on(self, doctor_id: str, iso_date: str) -> int:
        return self._conn.execute(
            """SELECT COUNT(*) FROM medical_reports
               WHERE doctor_id = ? AND substr(created_at, 1, 10) = ?""",
            (doctor_id, iso_date),
        ).fetchone()[0]

    def count_for_token(self, token_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM medical_reports WHERE token_id = ?", (token_id,)
        ).fetchone()[0]

    def insert(self, report: dict) -> None:
        """`report` holds every field except created_at/updated_at."""
        timestamp = now_iso()
        row = {**report, "created_at": timestamp, "updated_at": timestamp}
        placeholders = ", ".join("?" for _ in FIELDS)
        self._conn.execute(
            f"INSERT INTO medical_reports ({_COLUMNS}) VALUES ({placeholders})",
            [row[field] for field in FIELDS],
        )
        log_mutation(
            self._conn,
            entity_name="medical_reports",
            record_id=report["report_id"],
            action_type="INSERT",
        )
