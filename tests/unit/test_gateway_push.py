"""/sync/push with the same record repeated in one batch -- what a station
sends after working offline (a bed created, then toggled twice). Runs the
handler against an in-memory SQLite database, so no Postgres is needed.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gateway.models import Base, SyncRecordModel
from gateway.routers import sync


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(sync, "SessionLocal", factory)
    return factory


def _record(sync_id, status, updated_at, record_id="bed-1"):
    return sync.PushRecord(
        sync_id=sync_id,
        entity_name="beds",
        record_id=record_id,
        action_type="INSERT" if sync_id == 1 else "UPDATE",
        payload={"bed_id": record_id, "status": status},
        updated_at=updated_at,
    )


def test_repeated_record_in_one_batch_is_merged_not_duplicated(session_factory):
    batch = sync.PushBatchRequest(
        records=[
            _record(1, "AVAILABLE", "2026-10-18T17:38:57.814033+00:00"),
            _record(2, "OCCUPIED", "2026-10-20T13:35:29.428865+00:00"),
            _record(3, "MAINTENANCE", "2026-10-20T13:35:29.870225+00:00"),
            _record(4, "AVAILABLE", "2026-10-18T17:38:57.814033+00:00", record_id="bed-2"),
        ]
    )

    response = sync.push_batch(batch)

    assert [r.status for r in response.results] == ["SYNCED"] * 4
    with session_factory() as session:
        rows = {row.record_id: row.payload["status"] for row in session.query(SyncRecordModel)}
    assert rows == {"bed-1": "MAINTENANCE", "bed-2": "AVAILABLE"}  # newest copy wins


def test_older_copy_later_in_the_batch_is_a_conflict(session_factory):
    batch = sync.PushBatchRequest(
        records=[
            _record(1, "OCCUPIED", "2026-10-20T13:00:00+00:00"),
            _record(2, "AVAILABLE", "2026-10-20T12:00:00+00:00"),  # older than the first
        ]
    )

    response = sync.push_batch(batch)

    assert [r.status for r in response.results] == ["SYNCED", "CONFLICT"]
    assert response.results[1].winning_payload["status"] == "OCCUPIED"


def test_replaying_already_stored_data_is_synced_not_a_conflict(session_factory):
    """A push that committed but timed out on the client gets re-sent: the
    older copies carry the same data, so they mustn't show up as conflicts.
    """
    newest = _record(2, "OCCUPIED", "2026-10-20T13:00:00+00:00")
    sync.push_batch(sync.PushBatchRequest(records=[newest]))

    replay = _record(1, "OCCUPIED", "2026-10-20T12:00:00+00:00")  # older stamp, same data
    response = sync.push_batch(sync.PushBatchRequest(records=[replay]))

    assert [r.status for r in response.results] == ["SYNCED"]
