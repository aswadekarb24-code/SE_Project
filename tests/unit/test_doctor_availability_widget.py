from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget


def test_widget_renders_one_combo_per_doctor(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    DoctorsRepository(db_conn).insert(doctor_id="d2", full_name="Dr. Vikram Shah", dept_id=1)

    widget = DoctorAvailabilityWidget(db_conn)
    assert len(widget._combos) == 2
    assert widget._combos["d1"].currentText() == "AVAILABLE"


def test_changing_combo_updates_doctor_status_in_db(qapp, db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    widget = DoctorAvailabilityWidget(db_conn)

    widget._on_status_changed("d1", "BUSY")

    status = db_conn.execute("SELECT status FROM doctors WHERE doctor_id = 'd1'").fetchone()[0]
    assert status == "BUSY"
