from common.dto import PatientIntake
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import ReportDraft, create_report
from desktop.ui.pages.patients_page import PatientsPage


def _register(db_conn, name, dob="1990-01-01", dept=1):
    return issue_queue_token(db_conn, PatientIntake(full_name=name, dob=dob), dept)


def test_directory_lists_and_filters_patients(qapp, db_conn, receptionist):
    _register(db_conn, "Jane Doe")
    _register(db_conn, "John Roe")
    page = PatientsPage(db_conn, receptionist)
    page.refresh()
    assert page.table.rowCount() == 2

    page.search_input.setText("john")

    assert page.table.rowCount() == 1
    assert page.count_badge.text() == "1 shown"


def test_no_match_shows_the_empty_state(qapp, db_conn, receptionist):
    page = PatientsPage(db_conn, receptionist)
    page.search_input.setText("nobody")
    assert page.directory_stack.currentIndex() == 1


def test_selecting_a_patient_shows_details_and_visits(qapp, db_conn, receptionist):
    first = _register(db_conn, "Jane Doe")
    issue_queue_token(
        db_conn, PatientIntake("Jane Doe", "1990-01-01", patient_id=first.patient_id), 2
    )
    page = PatientsPage(db_conn, receptionist)
    page.refresh()
    assert page.detail_stack.currentIndex() == 0  # nothing selected yet

    page.table.selectRow(0)

    assert page.detail_stack.currentIndex() == 1
    assert page.info_values["Date of birth"].text() == "1 Jan 1990"
    assert page.visits_table.rowCount() == 2


def test_select_patient_opens_them_from_another_page(qapp, db_conn, doctor):
    _register(db_conn, "John Roe")
    target = _register(db_conn, "Jane Doe")
    page = PatientsPage(db_conn, doctor)

    page.select_patient(target.patient_id)

    assert page.search_input.text() == target.patient_number
    assert page.table.rowCount() == 1
    assert page.detail_stack.currentIndex() == 1


def test_doctor_sees_reports_newest_first_with_newest_selected(qapp, db_conn, doctor):
    visit = _register(db_conn, "Jane Doe")
    for diagnosis in ("Viral fever", "Recovered"):
        create_report(
            db_conn,
            author=doctor,
            patient_id=visit.patient_id,
            draft=ReportDraft(chief_complaint="Follow-up", diagnosis=diagnosis),
        )
    page = PatientsPage(db_conn, doctor)
    page.select_patient(visit.patient_id)

    assert page.reports_table.rowCount() == 2
    assert page.reports_table.item(0, 1).text() == "Recovered"
    assert page._selected_report()["diagnosis"] == "Recovered"
    assert page.export_report_button.isEnabled()


def test_doctor_with_no_reports_sees_prompt(qapp, db_conn, doctor):
    visit = _register(db_conn, "Jane Doe")
    page = PatientsPage(db_conn, doctor)
    page.select_patient(visit.patient_id)

    assert page.reports_table.isHidden()
    assert not page.reports_empty.isHidden()
    assert not page.view_report_button.isEnabled()
