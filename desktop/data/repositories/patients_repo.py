from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation


class PatientsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def exists(self, patient_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        return row is not None

    def insert(
        self,
        *,
        patient_id: str,
        full_name: str,
        dob: str,
        gender: str | None,
        contact_no: str | None,
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO patients
               (patient_id, full_name, dob, gender, contact_no, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, full_name, dob, gender, contact_no, timestamp, timestamp),
        )
        log_mutation(self._conn, entity_name="patients", record_id=patient_id, action_type="INSERT")
