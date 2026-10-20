from common.dto import SyncResult, SyncStatus
from desktop.data.repositories.beds_repo import BedsRepository
from desktop.sync.sync_scheduler import SyncScheduler
from desktop.sync.sync_status import audit_counts, sync_snapshot
from desktop.sync.sync_worker import SyncState

URL = "http://gateway.local"


def _snapshot(conn, **overrides):
    fields = {
        "gateway_url": URL,
        "state": SyncState.SYNCING,
        "last_attempt_at": "2026-10-20T10:00:00+00:00",
        "last_results": [],
        "last_error": None,
    }
    fields.update(overrides)
    return sync_snapshot(conn, **fields)


def _pending(conn, count=2):
    for i in range(count):
        BedsRepository(conn).insert(bed_id=f"b{i}", label=f"Bed {i}")


def test_no_gateway_means_offline_cache(db_conn):
    _pending(db_conn)
    snapshot = _snapshot(db_conn, gateway_url=None)
    assert (snapshot.tone, snapshot.label) == ("offline", "Offline · 2 pending")
    assert "HMS_GATEWAY_URL" in snapshot.detail


def test_unreachable_gateway_is_offline(db_conn):
    _pending(db_conn, 1)
    snapshot = _snapshot(db_conn, state=SyncState.OFFLINE_LOCAL)
    assert (snapshot.tone, snapshot.label) == ("offline", "Offline · 1 pending")
    assert URL in snapshot.detail


def test_reachable_and_nothing_pending_is_synced(db_conn):
    snapshot = _snapshot(db_conn)
    assert (snapshot.tone, snapshot.label) == ("synced", "Synced")


def test_reachable_with_new_changes_shows_pending(db_conn):
    _pending(db_conn, 3)
    assert _snapshot(db_conn).label == "Online · 3 pending"


def test_conflicts_in_last_pass_are_red(db_conn):
    results = [
        SyncResult(sync_id=1, status=SyncStatus.CONFLICT, winning_payload={}),
        SyncResult(sync_id=2, status=SyncStatus.SYNCED),
    ]
    snapshot = _snapshot(db_conn, last_results=results, state=SyncState.RESOLVING_CONFLICT)
    assert (snapshot.tone, snapshot.label) == ("conflict", "1 conflict resolved")
    assert "Last-Write-Wins" in snapshot.detail


def test_failed_pass_is_red_and_says_nothing_was_lost(db_conn):
    snapshot = _snapshot(db_conn, last_error="KeyError: 'results'")
    assert (snapshot.tone, snapshot.label) == ("conflict", "Sync error")
    assert "Nothing was lost" in snapshot.detail


def test_audit_counts(db_conn):
    _pending(db_conn, 2)
    db_conn.execute("UPDATE sync_audit_log SET sync_status = 'SYNCED' WHERE sync_id = 1")
    assert audit_counts(db_conn) == {"PENDING": 1, "SYNCED": 1, "CONFLICT": 0}


class _BrokenWorker:
    state = SyncState.SYNCING

    async def run_once(self):
        raise KeyError("results")


class _OkWorker:
    state = SyncState.SYNCING

    async def run_once(self):
        return [SyncResult(sync_id=1, status=SyncStatus.SYNCED)]


def test_scheduler_records_errors_instead_of_crashing(qapp):
    scheduler = SyncScheduler(_BrokenWorker())
    runs = []
    scheduler.ran.connect(lambda: runs.append(True))

    scheduler.sync_now()  # must not raise: an exception in a Qt slot aborts the app

    assert scheduler.last_error == "KeyError: 'results'"
    assert scheduler.last_attempt_at is not None
    assert runs == [True]


def test_scheduler_keeps_last_results_and_clears_old_errors(qapp):
    scheduler = SyncScheduler(_OkWorker())
    scheduler.last_error = "old"
    scheduler.sync_now()
    assert scheduler.last_error is None
    assert [r.status for r in scheduler.last_results] == [SyncStatus.SYNCED]
