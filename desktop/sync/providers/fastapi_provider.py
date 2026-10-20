"""Real SyncProvider: pushes pending records to the FastAPI gateway over
HTTP. Swapping this provider's base URL from local docker-compose to a
production gateway (itself fronting Supabase) is a config change only --
see common/sync_provider.py for why this boundary exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from common.dto import SyncRecord, SyncResult, SyncStatus
from common.sync_provider import SyncProvider


class FastAPISyncProvider(SyncProvider):
    # A station that was offline for a while can have hundreds of pending
    # changes; sending them in chunks keeps each request short enough to
    # finish well within the push timeout, even to a distant cloud region.
    CHUNK_SIZE = 100

    def __init__(self, base_url: str, timeout: float = 5.0, push_timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout  # health check: fail fast when offline
        self._push_timeout = push_timeout

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/health")
                return response.status_code == 200
        except httpx.TransportError:
            return False

    async def push_batch(self, records: Sequence[SyncRecord]) -> Sequence[SyncResult]:
        """Push in chunks of CHUNK_SIZE. If a chunk fails, it and every later
        chunk stay PENDING for the next pass (chunks already sent keep their
        results), so a dropped connection never loses or skips a change.
        """
        results: list[SyncResult] = []
        for start in range(0, len(records), self.CHUNK_SIZE):
            chunk = records[start : start + self.CHUNK_SIZE]
            chunk_results = await self._push_chunk(chunk)
            results.extend(chunk_results)
            if any(result.status == SyncStatus.PENDING for result in chunk_results):
                error = next(r.error for r in chunk_results if r.status == SyncStatus.PENDING)
                results.extend(
                    SyncResult(sync_id=record.sync_id, status=SyncStatus.PENDING, error=error)
                    for record in records[start + self.CHUNK_SIZE :]
                )
                break
        return results

    async def _push_chunk(self, records: Sequence[SyncRecord]) -> list[SyncResult]:
        body = {
            "records": [
                {
                    "sync_id": record.sync_id,
                    "entity_name": record.entity_name,
                    "record_id": record.record_id,
                    "action_type": record.action_type.value,
                    "payload": record.payload,
                    "updated_at": record.updated_at,
                }
                for record in records
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=self._push_timeout) as client:
                response = await client.post(f"{self._base_url}/sync/push", json=body)
                response.raise_for_status()
            return [
                SyncResult(
                    sync_id=item["sync_id"],
                    status=SyncStatus(item["status"]),
                    winning_payload=item.get("winning_payload"),
                )
                for item in response.json()["results"]
            ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # Transient failure or an unexpected reply: leave every record
            # PENDING for the next pass.
            error = str(exc) or type(exc).__name__
            return [
                SyncResult(sync_id=record.sync_id, status=SyncStatus.PENDING, error=error)
                for record in records
            ]

    async def pull_updates(self, since: str) -> Sequence[SyncRecord]:
        # Not needed for the push-driven flow this cycle wires up; a later
        # cycle can extend this if bidirectional pull-on-reconnect becomes
        # necessary.
        return []
