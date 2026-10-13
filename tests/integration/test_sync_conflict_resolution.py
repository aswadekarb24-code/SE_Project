"""Exercises the gateway's Last-Write-Wins conflict resolution
(gateway/routers/sync.py) and FastAPISyncProvider end-to-end, against the
live docker-compose stack. Requires `docker compose up -d`; skips otherwise,
same pattern as test_gateway_health.py.
"""

from __future__ import annotations

import httpx
import pytest

from common.dto import SyncActionType, SyncRecord, SyncStatus
from desktop.sync.providers.fastapi_provider import FastAPISyncProvider

GATEWAY_URL = "http://localhost:8000"


def _gateway_reachable() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/health", timeout=1.0)
        return True
    except httpx.TransportError:
        return False


pytestmark = pytest.mark.skipif(not _gateway_reachable(), reason="gateway stack is not running")


def test_first_push_for_a_record_is_synced():
    response = httpx.post(
        f"{GATEWAY_URL}/sync/push",
        json={
            "records": [
                {
                    "sync_id": 1,
                    "entity_name": "beds",
                    "record_id": "conflict-test-bed-1",
                    "action_type": "INSERT",
                    "payload": {"bed_id": "conflict-test-bed-1", "status": "AVAILABLE"},
                    "updated_at": "2026-01-01T00:00:00.000000+00:00",
                }
            ]
        },
        timeout=5.0,
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "SYNCED"


def test_older_push_for_same_record_loses_to_newer_server_row():
    record_id = "conflict-test-bed-2"

    # First push establishes the "server" row at 12:00.
    httpx.post(
        f"{GATEWAY_URL}/sync/push",
        json={
            "records": [
                {
                    "sync_id": 10,
                    "entity_name": "beds",
                    "record_id": record_id,
                    "action_type": "INSERT",
                    "payload": {"bed_id": record_id, "status": "OCCUPIED"},
                    "updated_at": "2026-01-01T12:00:00.000000+00:00",
                }
            ]
        },
        timeout=5.0,
    )

    # Second push claims an OLDER timestamp -- simulating a straggling
    # offline client -- and must lose to the server's already-newer row.
    response = httpx.post(
        f"{GATEWAY_URL}/sync/push",
        json={
            "records": [
                {
                    "sync_id": 11,
                    "entity_name": "beds",
                    "record_id": record_id,
                    "action_type": "UPDATE",
                    "payload": {"bed_id": record_id, "status": "MAINTENANCE"},
                    "updated_at": "2026-01-01T11:00:00.000000+00:00",
                }
            ]
        },
        timeout=5.0,
    )
    result = response.json()["results"][0]
    assert result["status"] == "CONFLICT"
    assert result["winning_payload"]["status"] == "OCCUPIED"  # the server's newer row wins


@pytest.mark.asyncio
async def test_fastapi_sync_provider_push_batch_against_live_gateway():
    provider = FastAPISyncProvider(GATEWAY_URL)
    assert await provider.is_reachable() is True

    record = SyncRecord(
        sync_id=99,
        entity_name="beds",
        record_id="provider-test-bed",
        action_type=SyncActionType.INSERT,
        payload={"bed_id": "provider-test-bed", "status": "AVAILABLE"},
        updated_at="2026-01-01T00:00:00.000000+00:00",
    )

    results = await provider.push_batch([record])

    assert len(results) == 1
    assert results[0].status == SyncStatus.SYNCED
