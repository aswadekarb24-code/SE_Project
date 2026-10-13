import statistics
import time

from common.dto import PatientIntake, TokenStatus
from desktop.services.queue_service import issue_queue_token


def _patient(name="Jane Doe", dob="1990-01-01", **kwargs):
    return PatientIntake(full_name=name, dob=dob, **kwargs)


def test_new_patient_creates_patient_and_token(db_conn):
    result = issue_queue_token(db_conn, _patient(), department_id=1)

    assert result.token_num == 1
    assert result.status == TokenStatus.WAITING
    assert result.broadcast_status is False  # NullBroadcaster until Cycle 2

    patient_row = db_conn.execute(
        "SELECT full_name, dob FROM patients WHERE patient_id = ?", (result.patient_id,)
    ).fetchone()
    assert patient_row == ("Jane Doe", "1990-01-01")


def test_returning_patient_does_not_duplicate_patient_row(db_conn):
    first = issue_queue_token(db_conn, _patient(), department_id=1)

    returning = PatientIntake(full_name="Jane Doe", dob="1990-01-01", patient_id=first.patient_id)
    second = issue_queue_token(db_conn, returning, department_id=1)

    assert second.patient_id == first.patient_id
    count = db_conn.execute(
        "SELECT COUNT(*) FROM patients WHERE patient_id = ?", (first.patient_id,)
    ).fetchone()[0]
    assert count == 1
    assert second.token_num == 2  # numbering continues for the same dept/day


def test_token_numbering_increments_per_department_per_day(db_conn):
    t1 = issue_queue_token(db_conn, _patient("A"), department_id=1)
    t2 = issue_queue_token(db_conn, _patient("B"), department_id=1)
    t3 = issue_queue_token(db_conn, _patient("C"), department_id=2)

    assert (t1.token_num, t2.token_num) == (1, 2)
    assert t3.token_num == 1  # different department starts its own sequence


def test_issue_queue_token_writes_sync_audit_log_pending_rows(db_conn):
    result = issue_queue_token(db_conn, _patient(), department_id=1)

    rows = db_conn.execute(
        "SELECT entity_name, record_id, action_type, sync_status FROM sync_audit_log"
    ).fetchall()
    assert ("patients", result.patient_id, "INSERT", "PENDING") in rows
    assert ("queue_tokens", result.token_id, "INSERT", "PENDING") in rows


def test_write_latency_p99_under_10ms(db_conn):
    durations_ms = []
    for i in range(200):
        start = time.perf_counter()
        issue_queue_token(db_conn, _patient(f"Patient {i}"), department_id=1)
        durations_ms.append((time.perf_counter() - start) * 1000)

    p99 = statistics.quantiles(durations_ms, n=100)[98]
    assert p99 < 10, f"p99 write latency {p99:.3f}ms exceeded the 10ms NFR-01 target"
