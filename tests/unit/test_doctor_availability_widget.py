from PyQt6.QtWidgets import QLabel

from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget


def test_widget_renders_one_combo_per_doctor(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    DoctorsRepository(db_conn).insert(doctor_id="d2", full_name="Dr. Vikram Shah", dept_id=1)

    widget = DoctorAvailabilityWidget(db_conn)
    assert len(widget._combos) == 2
    assert widget._combos["d1"].currentData() == "AVAILABLE"
    assert widget._badges["d1"].text() == "Available"


def test_changing_combo_updates_doctor_status_in_db(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    widget = DoctorAvailabilityWidget(db_conn)

    widget._combos["d1"].setCurrentIndex(widget._combos["d1"].findData("BUSY"))

    status = db_conn.execute("SELECT status FROM doctors WHERE doctor_id = 'd1'").fetchone()[0]
    assert status == "BUSY"
    assert widget._badges["d1"].text() == "Busy"


def test_refresh_does_not_write_back_to_the_db(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    widget = DoctorAvailabilityWidget(db_conn)
    logged_before = db_conn.execute("SELECT COUNT(*) FROM sync_audit_log").fetchone()[0]

    widget.refresh()

    logged_after = db_conn.execute("SELECT COUNT(*) FROM sync_audit_log").fetchone()[0]
    assert logged_after == logged_before


def test_signed_in_doctor_is_listed_first_and_marked(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    DoctorsRepository(db_conn).insert(doctor_id="d2", full_name="Dr. Vikram Shah", dept_id=1)

    widget = DoctorAvailabilityWidget(db_conn, current_doctor_id="d2")

    first_row = widget._layout.itemAt(0).widget()
    texts = [child.text() for child in first_row.findChildren(QLabel)]
    assert "Dr. Vikram Shah  (you)" in texts
