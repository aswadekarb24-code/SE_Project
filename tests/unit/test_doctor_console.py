from common.dto import PatientIntake
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import ReportDraft, create_report
from desktop.ui.pages.doctor_console import DoctorConsole


def _issue_waiting_token(db_conn, department_id=1, name="Jane Doe"):
    patient = PatientIntake(full_name=name, dob="1990-01-01")
    return issue_queue_token(db_conn, patient, department_id=department_id)


def _console(db_conn, doctor):
    console = DoctorConsole(db_conn, doctor)
    console.refresh()
    return console


def test_console_opens_on_the_doctors_department(qapp, db_conn, doctor):
    assert _console(db_conn, doctor).department_id == doctor.dept_id == 1


def test_call_next_with_empty_queue_shows_message_and_keeps_complete_disabled(
    qapp, db_conn, doctor
):
    console = _console(db_conn, doctor)
    console._on_call_next()

    assert console.status_label.text() == "Queue is empty for this department"
    assert console.complete_button.isEnabled() is False
    assert console.call_next_button.isEnabled() is True


def test_call_next_with_waiting_token_updates_status_and_enables_complete(qapp, db_conn, doctor):
    _issue_waiting_token(db_conn)
    console = _console(db_conn, doctor)

    console._on_call_next()

    assert console.status_label.text() == "Now serving token #1 (CALLED)"
    assert console.complete_button.isEnabled() is True
    assert console.report_button.isEnabled() is True
    assert console.call_next_button.isEnabled() is False  # finish this patient first
    assert console.patient_name_label.text() == "Jane Doe"
    assert console.report_badge.text() == "No report yet"


def test_complete_consultation_disables_button_and_clears_current_token(qapp, db_conn, doctor):
    _issue_waiting_token(db_conn)
    console = _console(db_conn, doctor)
    console._on_call_next()
    console._on_complete()

    assert console.status_label.text() == "Token #1 complete (DONE)"
    assert console.complete_button.isEnabled() is False
    assert console._current_token_id is None
    assert console.call_next_button.isEnabled() is True


def test_double_click_complete_is_a_no_op_once_disabled(qapp, db_conn, doctor):
    _issue_waiting_token(db_conn)
    console = _console(db_conn, doctor)
    console._on_call_next()
    console._on_complete()
    console._on_complete()  # no-op: _current_token_id is already None

    assert console.status_label.text() == "Token #1 complete (DONE)"


def test_consultation_in_progress_survives_a_new_session(qapp, db_conn, doctor):
    """Log out mid-consultation, log back in: the patient is still with you."""
    token = _issue_waiting_token(db_conn)
    _console(db_conn, doctor)._on_call_next()

    fresh = _console(db_conn, doctor)

    assert fresh._current_token_id == token.token_id
    assert fresh.complete_button.isEnabled() is True


def test_report_badge_reflects_saved_report(qapp, db_conn, doctor):
    token = _issue_waiting_token(db_conn)
    console = _console(db_conn, doctor)
    console._on_call_next()
    create_report(
        db_conn,
        author=doctor,
        patient_id=token.patient_id,
        token_id=token.token_id,
        draft=ReportDraft(chief_complaint="Cough", diagnosis="Common cold"),
    )

    console.refresh()

    assert console.report_badge.text() == "Report saved"
    assert console.reports_stat.value_label.text() == "1"


def test_queue_and_stats_follow_the_selected_department(qapp, db_conn, doctor):
    _issue_waiting_token(db_conn, 1, "A")
    _issue_waiting_token(db_conn, 2, "B")
    _issue_waiting_token(db_conn, 2, "C")
    console = _console(db_conn, doctor)
    assert console.queue_table.rowCount() == 1

    console.department_select.setCurrentIndex(console.department_select.findData(2))

    assert console.queue_table.rowCount() == 2
    assert console.waiting_stat.value_label.text() == "2"
    assert console.next_stat.caption_label.text() == "B"


def test_patient_history_asks_the_shell_to_open_the_patient(qapp, db_conn, doctor):
    token = _issue_waiting_token(db_conn)
    console = _console(db_conn, doctor)
    console._on_call_next()
    requests = []
    console.navigate.connect(lambda key, patient_id: requests.append((key, patient_id)))

    console.history_button.click()

    assert requests == [("patients", token.patient_id)]
