from common.dto import PatientIntake
from desktop.services.queue_service import issue_queue_token
from desktop.ui.doctor_window import DoctorWindow


def _issue_waiting_token(db_conn, department_id=1):
    patient = PatientIntake(full_name="Jane Doe", dob="1990-01-01")
    return issue_queue_token(db_conn, patient, department_id=department_id)


def test_call_next_with_empty_queue_shows_message_and_keeps_complete_disabled(qapp, db_conn):
    window = DoctorWindow(db_conn)
    window._on_call_next()

    assert window.status_label.text() == "Queue is empty for this department"
    assert window.complete_button.isEnabled() is False


def test_call_next_with_waiting_token_updates_status_and_enables_complete(qapp, db_conn):
    _issue_waiting_token(db_conn)

    window = DoctorWindow(db_conn)
    window._on_call_next()

    assert window.status_label.text() == "Now serving token #1 (CALLED)"
    assert window.complete_button.isEnabled() is True


def test_complete_consultation_disables_button_and_clears_current_token(qapp, db_conn):
    _issue_waiting_token(db_conn)

    window = DoctorWindow(db_conn)
    window._on_call_next()
    window._on_complete()

    assert window.status_label.text() == "Token #1 complete (DONE)"
    assert window.complete_button.isEnabled() is False
    assert window._current_token_id is None


def test_double_click_complete_is_a_no_op_once_disabled(qapp, db_conn):
    """The button is disabled after one completion, so a second UI-level
    click (simulated by calling the handler again, since _current_token_id
    is already cleared) must not raise.
    """
    _issue_waiting_token(db_conn)

    window = DoctorWindow(db_conn)
    window._on_call_next()
    window._on_complete()
    window._on_complete()  # no-op: _current_token_id is already None

    assert window.status_label.text() == "Token #1 complete (DONE)"
