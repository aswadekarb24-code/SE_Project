"""Unit tests for the sync state machine, using a fake SyncProvider -- no
real network/I/O. Covers the plan's "mock-provider offline/online
transitions", "LWW conflict tests", and "drop/retry tests".
"""

from __future__ import annotations

import pytest

from common.dto import PatientIntake, SyncResult, SyncStatus
from common.sync_provider import SyncProvider
from desktop.services.queue_service import issue_queue_token
from desktop.sync.sync_worker import SyncState, SyncWorker


class FakeSyncProvider(SyncProvider):
    def __init__(self, reachable=True, results_by_sync_id=None, push_error=False):
        self.reachable = reachable
        self.results_by_sync_id = results_by_sync_id or {}
        self.push_error = push_error
        self.pushed_batches: list = []

    async def is_reachable(self) -> bool:
        return self.reachable

    async def push_batch(self, records):
        self.pushed_batches.append(list(records))
        if self.push_error:
            return [
                SyncResult(sync_id=r.sync_id, status=SyncStatus.PENDING, error="boom")
                for r in records
            ]
        return [
            self.results_by_sync_id.get(
                r.sync_id, SyncResult(sync_id=r.sync_id, status=SyncStatus.SYNCED)
            )
            for r in records
        ]

    async def pull_updates(self, since):
        return []


def _issue(db_conn):
    patient = PatientIntake(full_name="Jane Doe", dob="1990-01-01")
    return issue_queue_token(db_conn, patient, department_id=1)


@pytest.mark.asyncio
async def test_offline_provider_keeps_state_offline_and_does_not_push(db_conn):
    _issue(db_conn)
    provider = FakeSyncProvider(reachable=False)
    worker = SyncWorker(db_conn, provider)

    results = await worker.run_once()

    assert results == []
    assert worker.state == SyncState.OFFLINE_LOCAL
    assert provider.pushed_batches == []


@pytest.mark.asyncio
async def test_online_with_nothing_pending_does_not_push(db_conn):
    provider = FakeSyncProvider(reachable=True)
    worker = SyncWorker(db_conn, provider)

    results = await worker.run_once()

    assert results == []
    assert provider.pushed_batches == []


@pytest.mark.asyncio
async def test_online_pushes_pending_records_and_marks_them_synced(db_conn):
    _issue(db_conn)
    provider = FakeSyncProvider(reachable=True)
    worker = SyncWorker(db_conn, provider)

    results = await worker.run_once()

    assert len(results) == 2  # patient INSERT + queue_token INSERT
    assert all(r.status == SyncStatus.SYNCED for r in results)
    assert worker.state == SyncState.SYNCING

    pending_count = db_conn.execute(
        "SELECT COUNT(*) FROM sync_audit_log WHERE sync_status = 'PENDING'"
    ).fetchone()[0]
    assert pending_count == 0


@pytest.mark.asyncio
async def test_pushed_records_include_full_row_payload(db_conn):
    issued = _issue(db_conn)
    provider = FakeSyncProvider(reachable=True)
    worker = SyncWorker(db_conn, provider)

    await worker.run_once()

    pushed = provider.pushed_batches[0]
    token_record = next(r for r in pushed if r.entity_name == "queue_tokens")
    assert token_record.payload["token_id"] == issued.token_id
    assert token_record.payload["status"] == "WAITING"


@pytest.mark.asyncio
async def test_transient_push_failure_leaves_rows_pending_for_retry(db_conn):
    _issue(db_conn)
    provider = FakeSyncProvider(reachable=True, push_error=True)
    worker = SyncWorker(db_conn, provider)

    results = await worker.run_once()

    assert all(r.status == SyncStatus.PENDING for r in results)
    pending_count = db_conn.execute(
        "SELECT COUNT(*) FROM sync_audit_log WHERE sync_status = 'PENDING'"
    ).fetchone()[0]
    assert pending_count == 2  # untouched, ready for the next sync pass


@pytest.mark.asyncio
async def test_conflict_result_overwrites_local_row_with_server_payload(db_conn):
    issued = _issue(db_conn)

    row = db_conn.execute(
        "SELECT sync_id FROM sync_audit_log WHERE entity_name = 'queue_tokens' AND record_id = ?",
        (issued.token_id,),
    ).fetchone()
    token_sync_id = row[0]

    server_payload = {
        "token_id": issued.token_id,
        "patient_id": issued.patient_id,
        "dept_id": issued.dept_id,
        "token_num": issued.token_num,
        "status": "DONE",  # server says this token was already completed elsewhere
        "issued_date": "2020-01-01",
        "created_at": "t",
        "updated_at": "t",
    }
    provider = FakeSyncProvider(
        reachable=True,
        results_by_sync_id={
            token_sync_id: SyncResult(
                sync_id=token_sync_id, status=SyncStatus.CONFLICT, winning_payload=server_payload
            )
        },
    )
    worker = SyncWorker(db_conn, provider)

    await worker.run_once()

    assert worker.state == SyncState.RESOLVING_CONFLICT
    local_status = db_conn.execute(
        "SELECT status FROM queue_tokens WHERE token_id = ?", (issued.token_id,)
    ).fetchone()[0]
    assert local_status == "DONE"  # overwritten by the server's authoritative row

    audit_status = db_conn.execute(
        "SELECT sync_status FROM sync_audit_log WHERE sync_id = ?", (token_sync_id,)
    ).fetchone()[0]
    assert audit_status == "CONFLICT"
