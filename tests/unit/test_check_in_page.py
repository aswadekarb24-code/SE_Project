from common.dto import PatientIntake
from desktop.services.queue_service import issue_queue_token
from desktop.ui.pages.check_in_page import CheckInPage


def _page(db_conn, receptionist):
    return CheckInPage(db_conn, receptionist)


def test_register_new_patient_issues_token_and_shows_number(qapp, db_conn, receptionist):
    page = _page(db_conn, receptionist)
    page.full_name_input.setText("Jane Doe")
    page.dob_input.setText("1990-01-01")

    page._on_issue_token()

    assert page.status_label.text() == "Token #1 issued to Jane Doe"
    number = db_conn.execute("SELECT patient_number FROM patients").fetchone()[0]
    assert number in page.banner_detail.text()
    assert not page.banner.isHidden()
    assert page.full_name_input.text() == ""  # form cleared after success
    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 1


def test_invalid_date_of_birth_is_shown_inline(qapp, db_conn, receptionist):
    page = _page(db_conn, receptionist)
    page.full_name_input.setText("Jane Doe")
    page.dob_input.setText("not-a-date")

    page._on_issue_token()

    assert "YYYY-MM-DD" in page.form_error.text()
    assert not page.form_error.isHidden()
    assert page.banner.isHidden()
    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0


def test_empty_name_is_rejected(qapp, db_conn, receptionist):
    page = _page(db_conn, receptionist)
    page.dob_input.setText("1990-01-01")

    page._on_issue_token()

    assert page.form_error.text() == "Full name is required."
    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0


def test_returning_patient_is_checked_in_against_the_same_record(qapp, db_conn, receptionist):
    first = issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-01-01"), 1)
    page = _page(db_conn, receptionist)
    assert not page.returning_button.isEnabled()

    page.search_input.setText(first.patient_number)
    assert page.results.count() == 1
    page.results.setCurrentRow(0)
    assert page.returning_button.isEnabled()
    page.returning_department.setCurrentIndex(page.returning_department.findData(2))

    page._on_issue_returning()

    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 1
    visits = db_conn.execute(
        "SELECT dept_id FROM queue_tokens WHERE patient_id = ? ORDER BY created_at",
        (first.patient_id,),
    ).fetchall()
    assert visits == [(1,), (2,)]
    assert page.status_label.text() == "Token #1 issued to Jane Doe"  # first in Pediatrics


def test_search_with_no_match_says_so(qapp, db_conn, receptionist):
    page = _page(db_conn, receptionist)
    page.search_input.setText("nobody")
    assert page.results.count() == 0
    assert page.results_hint.text() == "No matching patients."
