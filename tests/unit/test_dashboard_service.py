from common.dto import PatientIntake
from desktop.data.seed import seed_default_data
from desktop.services.dashboard_service import (
    current_consultation,
    doctor_summary,
    reception_summary,
    todays_queue,
)
from desktop.services.queue_service import call_next, complete_token, issue_queue_token
from desktop.services.report_service import ReportDraft, create_report


def _issue(conn, name, dept=1):
    return issue_queue_token(conn, PatientIntake(full_name=name, dob="1990-01-01"), dept)


def test_reception_summary_counts(db_conn):
    seed_default_data(db_conn)
    _issue(db_conn, "A")
    _issue(db_conn, "B")
    called = call_next(db_conn, 1)
    complete_token(db_conn, called.token_id)
    db_conn.execute("UPDATE beds SET status = 'OCCUPIED' WHERE label = 'Bed 1'")
    db_conn.execute("UPDATE pharmacy_stock SET quantity = 2 WHERE name = 'ORS Sachets'")

    summary = reception_summary(db_conn)

    assert summary["total_patients"] == 2
    assert summary["registered_today"] == 2
    assert (summary["waiting"], summary["in_consultation"], summary["seen_today"]) == (1, 0, 1)
    assert (summary["beds_available"], summary["beds_total"]) == (9, 10)
    assert summary["low_stock"] == 1


def test_doctor_summary_and_current_consultation(db_conn, doctor):
    first = _issue(db_conn, "A")
    _issue(db_conn, "B")
    _issue(db_conn, "C", dept=2)
    assert current_consultation(db_conn, 1) is None

    call_next(db_conn, 1)
    current = current_consultation(db_conn, 1)
    assert current["token_id"] == first.token_id
    assert current["full_name"] == "A"
    assert current["patient_number"] == first.patient_number

    create_report(
        db_conn,
        author=doctor,
        patient_id=first.patient_id,
        draft=ReportDraft(chief_complaint="Cough", diagnosis="Cold"),
    )
    summary = doctor_summary(db_conn, 1, doctor.doctor_id)
    assert summary == {"waiting": 1, "in_consultation": 1, "seen_today": 0, "reports_today": 1}


def test_todays_queue_is_in_queue_order_with_names(db_conn):
    _issue(db_conn, "A", dept=2)
    _issue(db_conn, "B", dept=1)
    _issue(db_conn, "C", dept=1)

    assert [(t["dept_name"], t["token_num"], t["full_name"]) for t in todays_queue(db_conn)] == [
        ("General OPD", 1, "B"),
        ("General OPD", 2, "C"),
        ("Pediatrics", 1, "A"),
    ]
    assert len(todays_queue(db_conn, dept_id=2)) == 1
