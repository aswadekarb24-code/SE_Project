from PyQt6.QtWidgets import QApplication

from desktop.main import MainWindow
from desktop.services.auth_service import Role


def test_main_window_opens_db_in_wal_mode(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db", role=Role.RECEPTIONIST)
    try:
        mode = window.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"
        assert window.windowTitle() == "Hybrid Offline-First HMS"
    finally:
        window.close()


def test_qapp_fixture_reuses_singleton(qapp):
    assert QApplication.instance() is qapp
