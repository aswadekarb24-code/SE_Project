"""The dependency-injection boundary between the local sync worker and the network.

desktop/sync/sync_worker.py is the only caller of SyncProvider. It reads PENDING
rows out of sync_audit_log via a local repository and hands them here -- it never
talks to the network directly. That keeps the sync state machine testable against
a fake provider with zero real I/O, and makes swapping the backend (none -> local
FastAPI/Postgres -> Supabase) a config change instead of a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from common.dto import SyncRecord, SyncResult


class SyncProvider(ABC):
    @abstractmethod
    async def is_reachable(self) -> bool:
        """Cheap connectivity check the worker polls before attempting a sync pass."""

    @abstractmethod
    async def push_batch(self, records: Sequence[SyncRecord]) -> Sequence[SyncResult]:
        """Push PENDING records. Returns one SyncResult per input record, in order."""

    @abstractmethod
    async def pull_updates(self, since: str) -> Sequence[SyncRecord]:
        """Pull remote changes with updated_at > since, for local Last-Write-Wins merge."""


class NoOpSyncProvider(SyncProvider):
    """Default provider through Cycles 0-3: always offline, never touches the network.

    This is what keeps the prototype genuinely offline-first while the sync code
    path already exists and is wired into the worker.
    """

    async def is_reachable(self) -> bool:
        return False

    async def push_batch(self, records: Sequence[SyncRecord]) -> Sequence[SyncResult]:
        return []

    async def pull_updates(self, since: str) -> Sequence[SyncRecord]:
        return []
