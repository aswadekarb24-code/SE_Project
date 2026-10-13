"""Doctor availability listing + self-service status toggle."""

from __future__ import annotations

import sqlite3

from desktop.data.repositories.doctors_repo import DoctorsRepository

STATUSES = ["AVAILABLE", "BUSY", "OFF_DUTY"]


def list_doctors(conn: sqlite3.Connection) -> list[dict]:
    return DoctorsRepository(conn).list_all()


def set_doctor_status(conn: sqlite3.Connection, doctor_id: str, status: str) -> dict:
    if status not in STATUSES:
        raise ValueError(f"invalid doctor status: {status}")

    repo = DoctorsRepository(conn)
    doctors = {doctor["doctor_id"]: doctor for doctor in repo.list_all()}
    doctor = doctors.get(doctor_id)
    if doctor is None:
        raise ValueError(f"doctor {doctor_id} does not exist")

    conn.execute("BEGIN")
    try:
        repo.update_status(doctor_id, status)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {**doctor, "status": status}
