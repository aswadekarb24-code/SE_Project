"""Patient numbers: assigned on registration, unique, stable per station,
and back-filled when an older database is upgraded.
"""

import re

from common.dto import PatientIntake
from desktop.data.db import connect, migrate
from desktop.data.numbering import next_patient_number, station_code
from desktop.services.queue_service import issue_queue_token

NUMBER = re.compile(r"^PT-[0-9A-HJKMNP-TV-Z]{4}-\d{5}$")


def _issue(conn, name="Jane Doe"):
    return issue_queue_token(conn, PatientIntake(full_name=name, dob="1990-01-01"), 1)


def test_new_patient_gets_a_formatted_number(db_conn):
    result = _issue(db_conn)
    assert NUMBER.match(result.patient_number)
    stored = db_conn.execute(
        "SELECT patient_number FROM patients WHERE patient_id = ?", (result.patient_id,)
    ).fetchone()[0]
    assert stored == result.patient_number


def test_numbers_count_up_on_one_station(db_conn):
    numbers = [_issue(db_conn, f"Patient {i}").patient_number for i in range(3)]
    code = station_code(db_conn)
    assert numbers == [f"PT-{code}-00001", f"PT-{code}-00002", f"PT-{code}-00003"]


def test_returning_patient_keeps_their_number(db_conn):
    first = _issue(db_conn)
    again = issue_queue_token(
        db_conn,
        PatientIntake(full_name="Jane Doe", dob="1990-01-01", patient_id=first.patient_id),
        2,
    )
    assert again.patient_number == first.patient_number


def test_station_code_survives_reopening(tmp_path):
    path = tmp_path / "hms.db"
    conn = connect(path)
    migrate(conn)
    code = station_code(conn)
    conn.close()

    reopened = connect(path)
    try:
        assert station_code(reopened) == code
    finally:
        reopened.close()


def test_rolled_back_registration_does_not_burn_a_number(db_conn):
    db_conn.execute("BEGIN")
    next_patient_number(db_conn)
    db_conn.execute("ROLLBACK")

    assert _issue(db_conn).patient_number.endswith("-00001")


def test_counter_skips_numbers_already_in_use(db_conn):
    first = _issue(db_conn)
    db_conn.execute("UPDATE app_meta SET value = '0' WHERE key = 'patient_seq'")  # simulate reset
    second = _issue(db_conn, "John Roe")
    assert second.patient_number != first.patient_number


def test_upgrade_adds_column_and_numbers_existing_patients(tmp_path):
    """A database created before patient numbers existed: the old patients
    table has no patient_number column and holds two patients.
    """
    path = tmp_path / "old.db"
    conn = connect(path)
    conn.executescript("""
        CREATE TABLE patients (
            patient_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, dob TEXT NOT NULL,
            gender TEXT, contact_no TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO patients VALUES ('p2', 'Second', '1980-01-01', NULL, NULL,
                                     '2026-01-02T00:00:00+00:00', '2026-01-02T00:00:00+00:00');
        INSERT INTO patients VALUES ('p1', 'First', '1970-01-01', NULL, NULL,
                                     '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        """)
    try:
        migrate(conn)
        rows = dict(conn.execute("SELECT patient_id, patient_number FROM patients"))
        code = station_code(conn)
        assert rows == {"p1": f"PT-{code}-00001", "p2": f"PT-{code}-00002"}  # oldest first

        logged = conn.execute(
            "SELECT record_id, action_type FROM sync_audit_log WHERE entity_name = 'patients'"
        ).fetchall()
        assert sorted(logged) == [("p1", "UPDATE"), ("p2", "UPDATE")]

        migrate(conn)  # idempotent: nothing renumbered
        assert dict(conn.execute("SELECT patient_id, patient_number FROM patients")) == rows
    finally:
        conn.close()
