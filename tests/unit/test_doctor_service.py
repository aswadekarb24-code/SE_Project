import pytest

from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.services.doctor_service import list_doctors, set_doctor_status


def _seed_doctor(db_conn, doctor_id="doc-1", name="Dr. Asha Rao", dept_id=1):
    DoctorsRepository(db_conn).insert(doctor_id=doctor_id, full_name=name, dept_id=dept_id)


def test_list_doctors_returns_seeded_doctors(db_conn):
    _seed_doctor(db_conn)
    doctors = list_doctors(db_conn)
    assert len(doctors) == 1
    assert doctors[0]["status"] == "AVAILABLE"


def test_set_doctor_status_updates_status(db_conn):
    _seed_doctor(db_conn)
    result = set_doctor_status(db_conn, "doc-1", "BUSY")
    assert result["status"] == "BUSY"

    status = db_conn.execute("SELECT status FROM doctors WHERE doctor_id = 'doc-1'").fetchone()[0]
    assert status == "BUSY"


def test_set_doctor_status_rejects_invalid_status(db_conn):
    _seed_doctor(db_conn)
    with pytest.raises(ValueError):
        set_doctor_status(db_conn, "doc-1", "ON_VACATION")


def test_set_doctor_status_rejects_unknown_doctor(db_conn):
    with pytest.raises(ValueError):
        set_doctor_status(db_conn, "does-not-exist", "BUSY")


def test_set_doctor_status_writes_sync_audit_log_update_row(db_conn):
    _seed_doctor(db_conn)
    set_doctor_status(db_conn, "doc-1", "OFF_DUTY")

    row = db_conn.execute(
        "SELECT action_type, sync_status FROM sync_audit_log "
        "WHERE entity_name = 'doctors' AND record_id = 'doc-1' ORDER BY sync_id DESC LIMIT 1"
    ).fetchone()
    assert row == ("UPDATE", "PENDING")
