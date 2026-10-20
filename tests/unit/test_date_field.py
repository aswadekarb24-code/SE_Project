from datetime import date, timedelta

from common.clock import local_today
from common.dto import PatientIntake
from desktop.services.patient_service import get_patient
from desktop.services.queue_service import issue_queue_token
from desktop.ui.date_field import DateField, to_qdate
from desktop.ui.pages.check_in_page import CheckInPage
from desktop.ui.report_dialogs import ReportEditorDialog


def test_typing_still_works(qapp):
    field = DateField()
    field.setText("1990-04-23")
    assert field.date_value() == date(1990, 4, 23)
    for bad in ("", "1990-4-23", "23-04-1990", "1990-02-30"):
        field.setText(bad)
        assert field.date_value() is None


def test_picking_a_day_fills_the_field_and_closes(qapp):
    field = DateField()
    field.open_calendar()
    popup = field.popup
    assert popup.isVisible()

    popup.calendar.clicked.emit(to_qdate(date(2001, 1, 9)))

    assert field.text() == "2001-01-09"
    assert not popup.isVisible()


def test_calendar_opens_on_the_typed_date(qapp):
    field = DateField()
    field.setText("1985-06-15")
    field.open_calendar()
    assert field.popup.calendar.selectedDate().toPyDate() == date(1985, 6, 15)
    field.popup.close()


def test_calendar_range_matches_the_field(qapp):
    today = local_today()
    field = DateField(minimum=today, maximum=today + timedelta(days=30))
    field.open_calendar()
    calendar = field.popup.calendar
    assert calendar.minimumDate().toPyDate() == today
    assert calendar.maximumDate().toPyDate() == today + timedelta(days=30)
    field.popup.close()


def test_today_button_respects_the_range(qapp):
    yesterday = local_today() - timedelta(days=1)
    field = DateField(maximum=yesterday)
    field.open_calendar()
    assert not field.popup.today_button.isEnabled()
    field.popup.close()

    open_field = DateField()
    open_field.open_calendar()
    open_field.popup.today_button.click()
    assert open_field.text() == local_today().isoformat()


def test_clear_empties_the_field(qapp):
    field = DateField()
    field.setText("2026-10-27")
    field.open_calendar()
    field.popup.clear_button.click()
    assert field.text() == ""


def test_date_of_birth_uses_the_calendar_field(qapp, db_conn, receptionist):
    page = CheckInPage(db_conn, receptionist)
    assert isinstance(page.dob_input, DateField)
    assert page.dob_input.maximum == local_today()  # no future dates of birth
    assert page.dob_input.minimum.year == local_today().year - 130

    page.full_name_input.setText("Jane Doe")
    page.dob_input.open_calendar()
    page.dob_input.popup.calendar.clicked.emit(to_qdate(date(1990, 4, 23)))
    page._on_issue_token()

    assert page.status_label.text() == "Token #1 issued to Jane Doe"
    assert db_conn.execute("SELECT dob FROM patients").fetchone()[0] == "1990-04-23"


def test_follow_up_uses_the_calendar_field(qapp, db_conn, doctor):
    visit = issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-01-01"), 1)
    dialog = ReportEditorDialog(db_conn, doctor, get_patient(db_conn, visit.patient_id))
    assert isinstance(dialog.follow_up_input, DateField)
    assert dialog.follow_up_input.minimum == local_today()  # no follow-ups in the past

    dialog.complaint_input.setPlainText("Fever")
    dialog.diagnosis_input.setText("Viral fever")
    dialog.follow_up_input.open_calendar()
    follow_up = local_today() + timedelta(days=7)
    dialog.follow_up_input.popup.calendar.clicked.emit(to_qdate(follow_up))
    dialog.save()

    assert dialog.saved_report["follow_up_date"] == follow_up.isoformat()
