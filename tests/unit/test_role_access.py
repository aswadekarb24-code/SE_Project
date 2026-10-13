"""UI-level role gating: the MVP has no server-side permission enforcement
(desktop/services/auth_service.py documents why), so what we verify here is
that each role only ever gets the tabs/screens appropriate to it.
"""

from desktop.main import MainWindow
from desktop.services.auth_service import Role


def _tab_titles(window) -> list[str]:
    tabs = window.centralWidget()
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_receptionist_role_sees_reception_beds_and_pharmacy(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db", role=Role.RECEPTIONIST)
    try:
        titles = _tab_titles(window)
        assert titles == ["Reception", "Beds", "Pharmacy"]
    finally:
        window.close()


def test_doctor_role_sees_doctor_console_and_availability_only(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db", role=Role.DOCTOR)
    try:
        titles = _tab_titles(window)
        assert titles == ["Doctor Console", "Doctor Availability"]
        assert "Reception" not in titles
        assert "Pharmacy" not in titles
    finally:
        window.close()
