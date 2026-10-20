"""Role gating: whoever signs in gets only their role's screens. The MVP has
no server-side permission enforcement (desktop/services/auth_service.py),
so what's verified here is the UI each role is given -- and that clinical
reports are never exposed to receptionists.
"""

import pytest

from desktop.main import MainWindow
from desktop.services.auth_service import Role, register_user


@pytest.fixture
def window(qapp, tmp_path):
    window = MainWindow(db_path=tmp_path / "hms.db")
    yield window
    window.close()


def _account(window, role, **extra):
    return register_user(
        window.conn,
        full_name="Test User",
        username=f"user-{role.value.lower()}",
        password="password-123",
        role=role,
        **extra,
    )


def test_receptionist_gets_front_desk_screens(window):
    window.sign_in(_account(window, Role.RECEPTIONIST))
    assert window.shell.nav_labels == [
        "Dashboard",
        "Check-in",
        "Patients",
        "Doctors",
        "Beds",
        "Pharmacy",
    ]
    assert window.shell.current_key == "dashboard"


def test_doctor_gets_clinical_screens_only(window):
    window.sign_in(_account(window, Role.DOCTOR, dept_id=1))
    labels = window.shell.nav_labels
    assert labels == ["Consultations", "Patients", "Availability"]
    assert "Check-in" not in labels and "Pharmacy" not in labels


def test_receptionist_patient_page_has_no_medical_reports(window):
    window.sign_in(_account(window, Role.RECEPTIONIST))
    page = window.shell.pages["patients"]
    assert not hasattr(page, "reports_table")
    assert not hasattr(page, "new_report_button")


def test_doctor_patient_page_has_medical_reports(window):
    window.sign_in(_account(window, Role.DOCTOR, dept_id=1))
    page = window.shell.pages["patients"]
    assert hasattr(page, "reports_table")
    assert hasattr(page, "new_report_button")
