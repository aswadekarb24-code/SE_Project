import statistics
import time

import pytest

from common.dto import PatientIntake, TokenStatus
from desktop.services.queue_service import (
    InvalidTokenTransitionError,
    call_next,
    complete_token,
    issue_queue_token,
)


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


def test_call_next_on_empty_queue_returns_none(db_conn):
    assert call_next(db_conn, department_id=1) is None


def test_call_next_transitions_oldest_waiting_token_to_called(db_conn):
    issue_queue_token(db_conn, _patient("A"), department_id=1)
    second = issue_queue_token(db_conn, _patient("B"), department_id=1)

    result = call_next(db_conn, department_id=1)

    assert result.token_num == 1  # oldest token called first, not "B"
    assert result.status == TokenStatus.CALLED
    status = db_conn.execute(
        "SELECT status FROM queue_tokens WHERE token_id = ?", (second.token_id,)
    ).fetchone()[0]
    assert status == "WAITING"  # untouched


def test_call_next_twice_serves_tokens_in_order(db_conn):
    issue_queue_token(db_conn, _patient("A"), department_id=1)
    issue_queue_token(db_conn, _patient("B"), department_id=1)

    first_called = call_next(db_conn, department_id=1)
    second_called = call_next(db_conn, department_id=1)

    assert (first_called.token_num, second_called.token_num) == (1, 2)
    assert call_next(db_conn, department_id=1) is None  # queue now empty


def test_call_next_writes_sync_audit_log_update_row(db_conn):
    issue_queue_token(db_conn, _patient(), department_id=1)
    result = call_next(db_conn, department_id=1)

    row = db_conn.execute(
        "SELECT action_type, sync_status FROM sync_audit_log "
        "WHERE entity_name = 'queue_tokens' AND record_id = ? "
        "ORDER BY sync_id DESC LIMIT 1",
        (result.token_id,),
    ).fetchone()
    assert row == ("UPDATE", "PENDING")


def test_complete_token_transitions_called_to_done(db_conn):
    issued = issue_queue_token(db_conn, _patient(), department_id=1)
    call_next(db_conn, department_id=1)

    result = complete_token(db_conn, issued.token_id)

    assert result.status == TokenStatus.DONE
    status = db_conn.execute(
        "SELECT status FROM queue_tokens WHERE token_id = ?", (issued.token_id,)
    ).fetchone()[0]
    assert status == "DONE"


def test_complete_token_rejects_a_token_that_was_never_called(db_conn):
    issued = issue_queue_token(db_conn, _patient(), department_id=1)

    with pytest.raises(InvalidTokenTransitionError):
        complete_token(db_conn, issued.token_id)


def test_complete_token_rejects_duplicate_completion(db_conn):
    issued = issue_queue_token(db_conn, _patient(), department_id=1)
    call_next(db_conn, department_id=1)
    complete_token(db_conn, issued.token_id)

    with pytest.raises(InvalidTokenTransitionError):
        complete_token(db_conn, issued.token_id)  # duplicate "complete" click


def test_complete_token_rejects_unknown_token_id(db_conn):
    with pytest.raises(InvalidTokenTransitionError):
        complete_token(db_conn, "does-not-exist")


def test_write_latency_p99_under_10ms(db_conn):
    durations_ms = []
    for i in range(200):
        start = time.perf_counter()
        issue_queue_token(db_conn, _patient(f"Patient {i}"), department_id=1)
        durations_ms.append((time.perf_counter() - start) * 1000)

    p99 = statistics.quantiles(durations_ms, n=100)[98]
    assert p99 < 10, f"p99 write latency {p99:.3f}ms exceeded the 10ms NFR-01 target"
