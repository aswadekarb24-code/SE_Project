"""Maps a sync_audit_log entity_name to (a) the repository method that
fetches its current full row, used to build SyncRecord payloads, and (b) its
primary-key column, used to apply a server-authoritative row during
Last-Write-Wins conflict resolution. New business tables register here once
and the sync worker handles them automatically -- no bespoke sync code per
table.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from desktop.data.repositories.beds_repo import BedsRepository
from desktop.data.repositories.doctor_schedules_repo import DoctorSchedulesRepository
from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.repositories.medical_reports_repo import MedicalReportsRepository
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository

RowFetcher = Callable[[sqlite3.Connection, str], "dict | None"]

ENTITY_ROW_FETCHERS: dict[str, RowFetcher] = {
    "patients": lambda conn, record_id: PatientsRepository(conn).get(record_id),
    "queue_tokens": lambda conn, record_id: QueueTokensRepository(conn).get(record_id),
    "doctors": lambda conn, record_id: DoctorsRepository(conn).get(record_id),
    "beds": lambda conn, record_id: BedsRepository(conn).get(record_id),
    "pharmacy_stock": lambda conn, record_id: PharmacyStockRepository(conn).get(record_id),
    "medical_reports": lambda conn, record_id: MedicalReportsRepository(conn).get(record_id),
    "doctor_schedules": lambda conn, record_id: DoctorSchedulesRepository(conn).get(record_id),
}

# Primary-key column per table. Values come only from this fixed allow-list
# (never from network/user input), so building the UPDATE statement below
# with an f-string is safe -- entity_name is validated against this dict's
# keys before it's ever used in a query.
_PRIMARY_KEY_COLUMN: dict[str, str] = {
    "patients": "patient_id",
    "queue_tokens": "token_id",
    "doctors": "doctor_id",
    "beds": "bed_id",
    "pharmacy_stock": "item_id",
    "medical_reports": "report_id",
    "doctor_schedules": "doctor_id",
}


def overwrite_row(
    conn: sqlite3.Connection, entity_name: str, record_id: str, payload: dict
) -> None:
    """Applies a server-authoritative row during conflict resolution,
    bypassing normal service-layer transition validation since this is a
    trusted merge, not a user action.
    """
    pk_column = _PRIMARY_KEY_COLUMN.get(entity_name)
    if pk_column is None:
        return

    columns = [key for key in payload if key != pk_column]
    if not columns:
        return

    set_clause = ", ".join(f"{column} = ?" for column in columns)
    values = [payload[column] for column in columns] + [record_id]
    conn.execute(f"UPDATE {entity_name} SET {set_clause} WHERE {pk_column} = ?", values)
