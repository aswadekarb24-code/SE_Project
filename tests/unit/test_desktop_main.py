from PyQt6.QtWidgets import QApplication

from desktop.main import APP_TITLE, MainWindow
from desktop.services.auth_service import Role, register_user


def test_main_window_opens_db_in_wal_mode(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db")
    try:
        mode = window.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"
        assert window.windowTitle() == APP_TITLE == "Hybrid Offline-First HMS"
    finally:
        window.close()


def test_window_starts_on_the_sign_in_screen(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db")
    try:
        assert window.screens.currentWidget() is window.auth_page
        assert window.shell is None and window.user is None
    finally:
        window.close()


def test_signing_in_through_the_form_opens_the_workspace(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db")
    try:
        register_user(
            window.conn,
            full_name="Riya Desk",
            username="riya",
            password="front-desk-1",
            role=Role.RECEPTIONIST,
        )
        window.auth_page.reset()
        window.auth_page.login_form.username_input.setText("riya")
        window.auth_page.login_form.password_input.setText("front-desk-1")
        window.auth_page.login_form.submit()

        assert window.screens.currentWidget() is window.shell
        assert window.user.username == "riya"
        assert "Riya Desk" in window.windowTitle()
    finally:
        window.close()


def test_logout_returns_to_sign_in_and_discards_the_session(tmp_path, qapp):
    window = MainWindow(db_path=tmp_path / "hms.db")
    try:
        user = register_user(
            window.conn,
            full_name="Riya Desk",
            username="riya",
            password="front-desk-1",
            role=Role.RECEPTIONIST,
        )
        window.sign_in(user)
        shell = window.shell

        shell.logout_button.click()

        assert window.shell is None
        assert window.screens.currentWidget() is window.auth_page
        assert window.screens.indexOf(shell) == -1
        assert window.auth_page.forms.currentWidget() is window.auth_page.login_form
        assert window.windowTitle() == APP_TITLE
    finally:
        window.close()


def test_qapp_fixture_reuses_singleton(qapp):
    assert QApplication.instance() is qapp
