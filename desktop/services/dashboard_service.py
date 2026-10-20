"""Read-only figures for the dashboards' stat cards and queue lists."""

from __future__ import annotations

import sqlite3

from common.clock import today_iso
from desktop.data.repositories.beds_repo import BedsRepository
from desktop.data.repositories.medical_reports_repo import MedicalReportsRepository
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository
from desktop.services.pharmacy_service import search_stock


def reception_summary(conn: sqlite3.Connection) -> dict:
    today = today_iso()
    patients = PatientsRepository(conn)
    queue = QueueTokensRepository(conn).count_by_status(today)
    beds = BedsRepository(conn).list_all()
    stock = search_stock(conn)
    return {
        "total_patients": patients.count(),
        "registered_today": patients.count_created_on(today),
        "waiting": queue["WAITING"],
        "in_consultation": queue["CALLED"],
        "seen_today": queue["DONE"],
        "beds_available": sum(bed["status"] == "AVAILABLE" for bed in beds),
        "beds_total": len(beds),
        "low_stock": sum(item["low_stock"] for item in stock),
        "stock_items": len(stock),
    }


def doctor_summary(conn: sqlite3.Connection, dept_id: int, doctor_id: str | None) -> dict:
    today = today_iso()
    queue = QueueTokensRepository(conn).count_by_status(today, dept_id)
    reports_today = (
        MedicalReportsRepository(conn).count_by_doctor_on(doctor_id, today) if doctor_id else 0
    )
    return {
        "waiting": queue["WAITING"],
        "in_consultation": queue["CALLED"],
        "seen_today": queue["DONE"],
        "reports_today": reports_today,
    }


def todays_queue(conn: sqlite3.Connection, dept_id: int | None = None) -> list[dict]:
    return QueueTokensRepository(conn).list_for_date(today_iso(), dept_id)


def current_consultation(conn: sqlite3.Connection, dept_id: int) -> dict | None:
    """The department's token currently being seen (CALLED), with patient
    details, or None.
    """
    repo = QueueTokensRepository(conn)
    token_id = repo.get_latest_called(dept_id, today_iso())
    if token_id is None:
        return None
    return next(
        (row for row in repo.list_for_date(today_iso(), dept_id) if row["token_id"] == token_id),
        None,
    )
