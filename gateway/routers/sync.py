"""POST /sync/push -- batch upsert with Last-Write-Wins conflict detection.

For each incoming record: if the server has no row yet for (entity_name,
record_id), or its stored row is no newer than the incoming one, the
incoming record wins and is stored as-is (status SYNCED). If the server's
existing row is strictly newer, the server's row wins and is returned as the
conflict's authoritative payload (status CONFLICT) -- the client applies it
locally (see desktop/sync/sync_worker.py's conflict resolution).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import tuple_

from gateway.db import SessionLocal
from gateway.models import SyncRecordModel

router = APIRouter(prefix="/sync", tags=["sync"])


class PushRecord(BaseModel):
    sync_id: int
    entity_name: str
    record_id: str
    action_type: str
    payload: dict
    updated_at: str  # ISO 8601, microsecond precision


class PushResult(BaseModel):
    sync_id: int
    status: str  # SYNCED | CONFLICT
    winning_payload: dict | None = None


class PushBatchRequest(BaseModel):
    records: list[PushRecord]


class PushBatchResponse(BaseModel):
    results: list[PushResult]


def _as_utc(moment: datetime) -> datetime:
    """Stored timestamps are UTC; some backends (SQLite) return them without
    a timezone, which can't be compared with the incoming aware ones.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


@router.post("/push", response_model=PushBatchResponse)
def push_batch(request: PushBatchRequest) -> PushBatchResponse:
    results: list[PushResult] = []
    # One batch can hold the same record several times (e.g. a bed created
    # then toggled while offline). Rows added earlier in this batch aren't in
    # the database yet; track them here so the later copies update that row
    # instead of inserting a duplicate key.
    added: dict[tuple[str, str], SyncRecordModel] = {}
    with SessionLocal() as session:
        # One query for every record the batch touches, instead of one
        # round trip per record -- with a remote database (Supabase) the
        # per-record version took long enough for clients to time out.
        keys = {(record.entity_name, record.record_id) for record in request.records}
        stored = (
            {
                (row.entity_name, row.record_id): row
                for row in session.query(SyncRecordModel).filter(
                    tuple_(SyncRecordModel.entity_name, SyncRecordModel.record_id).in_(keys)
                )
            }
            if keys
            else {}
        )
        for record in request.records:
            incoming_ts = datetime.fromisoformat(record.updated_at)
            key = (record.entity_name, record.record_id)
            existing = added.get(key) or stored.get(key)

            if existing is None or _as_utc(existing.updated_at) <= incoming_ts:
                if existing is None:
                    row = SyncRecordModel(
                        entity_name=record.entity_name,
                        record_id=record.record_id,
                        payload=record.payload,
                        updated_at=incoming_ts,
                    )
                    session.add(row)
                    added[key] = row
                else:
                    existing.payload = record.payload
                    existing.updated_at = incoming_ts
                results.append(PushResult(sync_id=record.sync_id, status="SYNCED"))
            elif existing.payload == record.payload:
                # Same data we already hold under a newer timestamp: a replay
                # (e.g. a retry after the client timed out waiting for a push
                # that did commit). Nothing to resolve, so it's simply synced.
                results.append(PushResult(sync_id=record.sync_id, status="SYNCED"))
            else:
                results.append(
                    PushResult(
                        sync_id=record.sync_id,
                        status="CONFLICT",
                        winning_payload=existing.payload,
                    )
                )
        session.commit()
    return PushBatchResponse(results=results)
