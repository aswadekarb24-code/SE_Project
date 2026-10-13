"""POST /sync/push -- batch upsert with Last-Write-Wins conflict detection.

For each incoming record: if the server has no row yet for (entity_name,
record_id), or its stored row is no newer than the incoming one, the
incoming record wins and is stored as-is (status SYNCED). If the server's
existing row is strictly newer, the server's row wins and is returned as the
conflict's authoritative payload (status CONFLICT) -- the client applies it
locally (see desktop/sync/sync_worker.py's conflict resolution).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

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


@router.post("/push", response_model=PushBatchResponse)
def push_batch(request: PushBatchRequest) -> PushBatchResponse:
    results: list[PushResult] = []
    with SessionLocal() as session:
        for record in request.records:
            incoming_ts = datetime.fromisoformat(record.updated_at)
            existing = session.get(SyncRecordModel, (record.entity_name, record.record_id))

            if existing is None or existing.updated_at <= incoming_ts:
                if existing is None:
                    session.add(
                        SyncRecordModel(
                            entity_name=record.entity_name,
                            record_id=record.record_id,
                            payload=record.payload,
                            updated_at=incoming_ts,
                        )
                    )
                else:
                    existing.payload = record.payload
                    existing.updated_at = incoming_ts
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
