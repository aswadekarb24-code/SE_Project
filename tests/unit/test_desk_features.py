"""UI features from the design documents: sync status bar, token slips,
keyboard shortcuts, doctor schedules, the reception Doctors page and
receiving stock.
"""

import pytest
from PyQt6.QtGui import QShortcut
from PyQt6.QtPrintSupport import QPrinter

from common.dto import PatientIntake
from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.data.settings import AUTO_PRINT_SLIPS, get_flag
from desktop.export import token_slip
from desktop.main import MainWindow
from desktop.services.auth_service import Role, register_user
from desktop.services.doctor_service import get_schedules
from desktop.services.queue_service import issue_queue_token
from desktop.ui.pages import check_in_page
from desktop.ui.pages.check_in_page import CheckInPage
from desktop.ui.pages.doctor_console import DoctorConsole
from desktop.ui.widgets import pharmacy_widget
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget, ScheduleDialog
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


@pytest.fixture
def window(qapp, tmp_path):
    window = MainWindow(db_path=tmp_path / "hms.db")
    yield window
    window.close()


def _sign_in(window, role, **extra):
    user = register_user(
        window.conn,
        full_name="Test User",
        username=f"user-{role.value.lower()}",
        password="password-123",
        role=role,
        **extra,
    )
    window.sign_in(user)
    return user


def _shortcut_keys(widget):
    return {shortcut.key().toString() for shortcut in widget.findChildren(QShortcut)}


# Sync status bar ------------------------------------------------------------


def test_sync_chip_shows_offline_cache_without_a_gateway(window):
    _sign_in(window, Role.RECEPTIONIST)
    chip = window.shell.sync_chip
    assert chip.property("tone") == "offline"
    assert chip.text_label.text().startswith("Offline")
    assert not chip.retry_button.isEnabled()  # nothing to retry against


def test_logout_stops_the_sync_chip_timer(window):
    _sign_in(window, Role.RECEPTIONIST)
    chip = window.shell.sync_chip
    window.logout()
    assert not chip._timer.isActive()


# Token slips -----------------------------------------------------------------


def _issue_from_page(page):
    page.full_name_input.setText("Jane Doe")
    page.dob_input.setText("1990-01-01")
    page.full_name_input.returnPressed.emit()  # Enter submits the form


def test_enter_submits_and_slip_details_are_kept(qapp, db_conn, receptionist):
    page = CheckInPage(db_conn, receptionist)
    _issue_from_page(page)

    assert page.status_label.text() == "Token #1 issued to Jane Doe"
    assert page.last_slip["token_num"] == 1
    assert page.last_slip["dept_name"] == "General OPD"
    assert page.last_slip["patient_number"].startswith("PT-")


def test_slip_prints_to_a_pdf_printer(qapp, tmp_path):
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(tmp_path / "slip.pdf"))
    slip = {
        "token_num": 7,
        "dept_name": "Pediatrics",
        "full_name": "Jane <b>Doe</b>",
        "patient_number": "PT-ABCD-00007",
        "issued_at": "2026-10-20T10:00:00+00:00",
    }

    token_slip.print_slip(slip, printer)

    assert (tmp_path / "slip.pdf").read_bytes().startswith(b"%PDF")
    html = token_slip.slip_html(slip)
    assert "#7" in html and "Pediatrics" in html and "&lt;b&gt;" in html


def test_auto_print_setting_is_remembered(qapp, db_conn, receptionist):
    page = CheckInPage(db_conn, receptionist)
    page.auto_print_check.setChecked(True)
    assert get_flag(db_conn, AUTO_PRINT_SLIPS) is True
    assert CheckInPage(db_conn, receptionist).auto_print_check.isChecked()


def test_auto_print_prints_on_the_default_printer(qapp, db_conn, receptionist, monkeypatch):
    printed = []
    monkeypatch.setattr(check_in_page, "has_default_printer", lambda: True)
    monkeypatch.setattr(check_in_page, "print_slip", lambda slip, printer: printed.append(slip))
    page = CheckInPage(db_conn, receptionist)
    page.auto_print_check.setChecked(True)

    _issue_from_page(page)

    assert [slip["token_num"] for slip in printed] == [1]


def test_auto_print_without_a_printer_says_so(qapp, db_conn, receptionist, monkeypatch):
    monkeypatch.setattr(check_in_page, "has_default_printer", lambda: False)
    page = CheckInPage(db_conn, receptionist)
    page.auto_print_check.setChecked(True)

    _issue_from_page(page)

    assert "No default printer" in page.banner_detail.text()


def test_enter_in_search_issues_for_the_only_match(qapp, db_conn, receptionist):
    first = issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-01-01"), 1)
    page = CheckInPage(db_conn, receptionist)
    page.search_input.setText(first.patient_number)

    page.search_input.returnPressed.emit()

    assert page.status_label.text() == "Token #2 issued to Jane Doe"
    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 1


# Keyboard shortcuts ---------------------------------------------------------


def test_receptionist_shortcuts(window):
    _sign_in(window, Role.RECEPTIONIST)
    shell = window.shell
    assert {"Ctrl+1", "Ctrl+6", "Ctrl+N", "Ctrl+F"} <= _shortcut_keys(shell)
    assert "Ctrl+P" in _shortcut_keys(shell.pages["check_in"])

    shell.show_page("beds")
    shell.new_patient()
    assert shell.current_key == "check_in"


def test_doctor_console_function_keys_respect_button_state(qapp, db_conn, doctor):
    console = DoctorConsole(db_conn, doctor)
    console.refresh()
    shortcuts = {s.key().toString(): s for s in console.findChildren(QShortcut)}
    assert {"F2", "F3", "F4"} <= set(shortcuts)

    shortcuts["F4"].activated.emit()  # complete while nobody is called: ignored
    assert console.status_label.text() == "No patient called"

    issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-01-01"), 1)
    shortcuts["F2"].activated.emit()
    assert console.status_label.text() == "Now serving token #1 (CALLED)"
    assert console.queue_table.selectionModel().selectedRows()[0].row() == 0  # highlighted

    shortcuts["F4"].activated.emit()
    assert console.status_label.text() == "Token #1 complete (DONE)"


# Doctor schedules and the reception Doctors page ---------------------------


def test_doctor_edits_own_hours(qapp, db_conn, doctor):
    widget = DoctorAvailabilityWidget(db_conn, current_doctor_id=doctor.doctor_id)
    assert widget.edit_hours_button is not None
    doctor_row = DoctorsRepository(db_conn).get(doctor.doctor_id)
    dialog = ScheduleDialog(db_conn, doctor_row, None)
    for day in ("Sat", "Sun"):
        dialog.day_buttons[day].setChecked(False)
    dialog.day_buttons["Fri"].setChecked(False)
    dialog.start_select.setCurrentText("10:00")
    dialog.end_select.setCurrentText("12:30")

    dialog.save()

    saved = get_schedules(db_conn)[doctor.doctor_id]
    assert (saved["opd_days"], saved["start_time"], saved["end_time"]) == (
        "Mon,Tue,Wed,Thu",
        "10:00",
        "12:30",
    )
    widget.refresh()
    assert "Mon–Thu · 10:00–12:30" in widget._details[doctor.doctor_id].text()


def test_schedule_dialog_shows_errors(qapp, db_conn, doctor):
    doctor_row = DoctorsRepository(db_conn).get(doctor.doctor_id)
    dialog = ScheduleDialog(db_conn, doctor_row, None)
    dialog.start_select.setCurrentText("14:00")
    dialog.end_select.setCurrentText("09:00")

    dialog.save()

    assert dialog.saved is None
    assert "end after" in dialog.error_label.text()


def test_reception_doctors_page_is_read_only(window):
    _sign_in(window, Role.RECEPTIONIST)
    assert "Doctors" in window.shell.nav_labels
    widget = window.shell.pages["doctors"].availability
    assert widget._badges  # seeded doctors listed
    assert widget._combos == {}
    assert widget.edit_hours_button is None


# Receiving stock -------------------------------------------------------------


def test_receive_adds_a_whole_delivery(qapp, db_conn, monkeypatch):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    monkeypatch.setattr(pharmacy_widget.QInputDialog, "getInt", lambda *args, **kwargs: (120, True))
    widget = PharmacyWidget(db_conn)

    widget.receive(widget.items()[0])

    assert widget.table.item(0, 1).text() == "125"


def test_cancelled_receive_changes_nothing(qapp, db_conn, monkeypatch):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    monkeypatch.setattr(pharmacy_widget.QInputDialog, "getInt", lambda *args, **kwargs: (0, False))
    widget = PharmacyWidget(db_conn)

    widget.receive(widget.items()[0])

    assert widget.table.item(0, 1).text() == "5"
