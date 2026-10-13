import pytest

from common.sync_provider import NoOpSyncProvider


@pytest.mark.asyncio
async def test_noop_provider_is_never_reachable():
    provider = NoOpSyncProvider()
    assert await provider.is_reachable() is False


@pytest.mark.asyncio
async def test_noop_provider_push_batch_returns_empty():
    provider = NoOpSyncProvider()
    assert await provider.push_batch([]) == []


@pytest.mark.asyncio
async def test_noop_provider_pull_updates_returns_empty():
    provider = NoOpSyncProvider()
    assert await provider.pull_updates(since="2026-01-01T00:00:00Z") == []
