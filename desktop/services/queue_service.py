"""Implements IssueQueueToken() exactly per the design doc's procedural
algorithm (docs Lab 7): generate a UUID for a new patient, compute the next
per-department/per-day token number, write patients/queue_tokens rows plus a
sync_audit_log entry for each, then hand off to the broadcaster.

The patient insert, token insert, and both audit-log inserts run inside a
single SQLite transaction so a crash mid-operation can never leave a token
without its patient, or a mutation without its audit trail -- verified in
tests/system/test_power_interruption_wal.py.
"""

from __future__ import annotations

import sqlite3
from uuid import uuid4

from common.clock import today_iso
from common.dto import PatientIntake, QueueTokenIssued, QueueTokenUpdate, TokenStatus
from desktop.broadcast.broadcaster import Broadcaster, NullBroadcaster
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository


class InvalidTokenTransitionError(ValueError):
    """Raised when a token isn't in the expected state for the requested
    transition (e.g. completing a token that was never called, or calling
    an already-completed token twice).
    """


def issue_queue_token(
    conn: sqlite3.Connection,
    patient: PatientIntake,
    department_id: int,
    *,
    broadcaster: Broadcaster | None = None,
) -> QueueTokenIssued:
    broadcaster = broadcaster or NullBroadcaster()
    patients_repo = PatientsRepository(conn)
    tokens_repo = QueueTokensRepository(conn)

    conn.execute("BEGIN")
    try:
        patient_id = patient.patient_id
        # A non-null but not-yet-persisted ID covers a client-generated UUID
        # built before submission (e.g. an offline-created draft); the design
        # doc's literal check is just `patient_id IS NULL`.
        if patient_id is None or not patients_repo.exists(patient_id):
            patient_id = patient_id or str(uuid4())
            patients_repo.insert(
                patient_id=patient_id,
                full_name=patient.full_name,
                dob=patient.dob,
                gender=patient.gender,
                contact_no=patient.contact_no,
            )

        issued_date = today_iso()
        token_num = tokens_repo.next_token_num(department_id, issued_date)
        token_id = str(uuid4())
        tokens_repo.insert(
            token_id=token_id,
            patient_id=patient_id,
            dept_id=department_id,
            token_num=token_num,
            status=TokenStatus.WAITING.value,
            issued_date=issued_date,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    broadcast_status = broadcaster.broadcast_token_update(
        token_id=token_id,
        token_num=token_num,
        dept_id=department_id,
        status=TokenStatus.WAITING.value,
    )

    return QueueTokenIssued(
        token_id=token_id,
        patient_id=patient_id,
        dept_id=department_id,
        token_num=token_num,
        status=TokenStatus.WAITING,
        broadcast_status=broadcast_status,
    )


def call_next(
    conn: sqlite3.Connection,
    department_id: int,
    *,
    broadcaster: Broadcaster | None = None,
) -> QueueTokenUpdate | None:
    """Transitions the oldest WAITING token for a department to CALLED.

    Returns None if the department's queue is empty (boundary case -- not an
    error, since "nobody waiting" is a normal state).
    """
    broadcaster = broadcaster or NullBroadcaster()
    tokens_repo = QueueTokensRepository(conn)

    token_id = tokens_repo.get_oldest_waiting(department_id)
    if token_id is None:
        return None

    conn.execute("BEGIN")
    try:
        tokens_repo.update_status(token_id, TokenStatus.CALLED.value)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    token = tokens_repo.get(token_id)
    broadcast_status = broadcaster.broadcast_token_update(
        token_id=token_id,
        token_num=token["token_num"],
        dept_id=token["dept_id"],
        status=TokenStatus.CALLED.value,
    )
    return QueueTokenUpdate(
        token_id=token_id,
        dept_id=token["dept_id"],
        token_num=token["token_num"],
        status=TokenStatus.CALLED,
        broadcast_status=broadcast_status,
    )


def complete_token(
    conn: sqlite3.Connection,
    token_id: str,
    *,
    broadcaster: Broadcaster | None = None,
) -> QueueTokenUpdate:
    """Transitions a CALLED token to DONE. Raises InvalidTokenTransitionError
    if the token doesn't exist or isn't currently CALLED (e.g. a duplicate
    "complete" click, or completing a token that was never called).
    """
    broadcaster = broadcaster or NullBroadcaster()
    tokens_repo = QueueTokensRepository(conn)

    token = tokens_repo.get(token_id)
    if token is None:
        raise InvalidTokenTransitionError(f"token {token_id} does not exist")
    if token["status"] != TokenStatus.CALLED.value:
        raise InvalidTokenTransitionError(
            f"token {token_id} is {token['status']}, expected "
            f"{TokenStatus.CALLED.value} to complete"
        )

    conn.execute("BEGIN")
    try:
        tokens_repo.update_status(token_id, TokenStatus.DONE.value)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    broadcast_status = broadcaster.broadcast_token_update(
        token_id=token_id,
        token_num=token["token_num"],
        dept_id=token["dept_id"],
        status=TokenStatus.DONE.value,
    )
    return QueueTokenUpdate(
        token_id=token_id,
        dept_id=token["dept_id"],
        token_num=token["token_num"],
        status=TokenStatus.DONE,
        broadcast_status=broadcast_status,
    )
