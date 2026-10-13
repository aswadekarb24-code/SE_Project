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
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/health")
                return response.status_code == 200
        except httpx.TransportError:
            return False

    async def push_batch(self, records: Sequence[SyncRecord]) -> Sequence[SyncResult]:
        if not records:
            return []

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
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/sync/push", json=body)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # Transient failure: leave every record PENDING for the next pass.
            return [
                SyncResult(sync_id=record.sync_id, status=SyncStatus.PENDING, error=str(exc))
                for record in records
            ]

        data = response.json()
        return [
            SyncResult(
                sync_id=item["sync_id"],
                status=SyncStatus(item["status"]),
                winning_payload=item.get("winning_payload"),
            )
            for item in data["results"]
        ]

    async def pull_updates(self, since: str) -> Sequence[SyncRecord]:
        # Not needed for the push-driven flow this cycle wires up; a later
        # cycle can extend this if bidirectional pull-on-reconnect becomes
        # necessary.
        return []
