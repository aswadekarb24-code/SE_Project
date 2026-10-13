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
from common.dto import PatientIntake, QueueTokenIssued, TokenStatus
from desktop.broadcast.broadcaster import Broadcaster, NullBroadcaster
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository


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
