"""FastAPISyncProvider against a fake HTTP gateway (httpx.MockTransport):
chunking, timeouts kept separate, and failures leaving records PENDING.
"""

import json

import httpx
import pytest

from common.dto import SyncActionType, SyncRecord, SyncStatus
from desktop.sync.providers import fastapi_provider
from desktop.sync.providers.fastapi_provider import FastAPISyncProvider


def _records(count):
    return [
        SyncRecord(
            sync_id=i,
            entity_name="beds",
            record_id=f"bed-{i}",
            action_type=SyncActionType.INSERT,
            payload={"bed_id": f"bed-{i}"},
            updated_at="2026-10-20T10:00:00+00:00",
        )
        for i in range(1, count + 1)
    ]


@pytest.fixture
def gateway(monkeypatch):
    """Routes the provider's httpx clients to `handler`; records each push."""
    state = {"pushes": [], "fail_on_push": None, "timeouts": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(request.content)
        state["pushes"].append(len(body["records"]))
        if state["fail_on_push"] == len(state["pushes"]):
            return httpx.Response(500, text="boom")
        return httpx.Response(
            200,
            json={
                "results": [{"sync_id": r["sync_id"], "status": "SYNCED"} for r in body["records"]]
            },
        )

    real_client = httpx.AsyncClient

    def client_factory(*args, timeout=None, **kwargs):
        state["timeouts"].append(timeout)
        return real_client(transport=httpx.MockTransport(handler), timeout=timeout)

    monkeypatch.setattr(fastapi_provider.httpx, "AsyncClient", client_factory)
    return state


@pytest.mark.asyncio
async def test_large_backlog_is_pushed_in_chunks(gateway):
    provider = FastAPISyncProvider("http://gateway")

    results = await provider.push_batch(_records(250))

    assert gateway["pushes"] == [100, 100, 50]
    assert [r.sync_id for r in results] == list(range(1, 251))
    assert all(r.status == SyncStatus.SYNCED for r in results)


@pytest.mark.asyncio
async def test_failed_chunk_and_the_rest_stay_pending(gateway):
    gateway["fail_on_push"] = 2
    provider = FastAPISyncProvider("http://gateway")

    results = await provider.push_batch(_records(250))

    assert gateway["pushes"] == [100, 100]  # stops after the failure
    statuses = [r.status for r in results]
    assert statuses[:100] == [SyncStatus.SYNCED] * 100
    assert statuses[100:] == [SyncStatus.PENDING] * 150
    assert all(r.error for r in results[100:])


@pytest.mark.asyncio
async def test_push_uses_the_longer_timeout(gateway):
    provider = FastAPISyncProvider("http://gateway")
    assert await provider.is_reachable() is True
    await provider.push_batch(_records(1))
    assert gateway["timeouts"] == [5.0, 30.0]


@pytest.mark.asyncio
async def test_empty_batch_sends_nothing(gateway):
    assert await FastAPISyncProvider("http://gateway").push_batch([]) == []
    assert gateway["pushes"] == []
