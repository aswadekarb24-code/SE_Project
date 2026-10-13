"""Background sync: one run_once() pass reads PENDING sync_audit_log rows,
builds their current-row payloads, pushes them through a SyncProvider, and
applies the OFFLINE_LOCAL -> SYNCING -> RESOLVING_CONFLICT state machine
from the design doc.

Deliberately framework-free (no QThread dependency) so the state machine is
unit-testable with a fake provider and no real I/O; desktop/sync/
sync_scheduler.py wraps this in a QTimer for the real app without touching
this logic.
"""

from __future__ import annotations

import sqlite3
from enum import Enum

from common.dto import SyncActionType, SyncRecord, SyncResult, SyncStatus
from common.sync_provider import SyncProvider
from desktop.data.repositories import sync_audit_log_repo
from desktop.sync.entity_registry import ENTITY_ROW_FETCHERS, overwrite_row


class SyncState(str, Enum):
    OFFLINE_LOCAL = "OFFLINE_LOCAL"
    SYNCING = "SYNCING"
    RESOLVING_CONFLICT = "RESOLVING_CONFLICT"


class SyncWorker:
    def __init__(self, conn: sqlite3.Connection, provider: SyncProvider) -> None:
        self._conn = conn
        self._provider = provider
        self.state = SyncState.OFFLINE_LOCAL

    async def run_once(self) -> list[SyncResult]:
        """Runs a single sync pass. Returns whatever was pushed (empty if
        offline or nothing is pending).
        """
        if not await self._provider.is_reachable():
            self.state = SyncState.OFFLINE_LOCAL
            return []

        self.state = SyncState.SYNCING
        records = self._build_pending_records()
        if not records:
            return []

        results = list(await self._provider.push_batch(records))
        conflicts = [r for r in results if r.status == SyncStatus.CONFLICT]
        if conflicts:
            self.state = SyncState.RESOLVING_CONFLICT
            self._apply_conflict_resolutions(conflicts)
        else:
            self.state = SyncState.SYNCING

        for result in results:
            # SyncStatus.PENDING (error/transient-failure) is left untouched
            # -- the row stays PENDING in sync_audit_log for the next pass.
            if result.status in (SyncStatus.SYNCED, SyncStatus.CONFLICT):
                sync_audit_log_repo.mark_status(self._conn, result.sync_id, result.status.value)

        return results

    def _build_pending_records(self) -> list[SyncRecord]:
        records = []
        for audit_row in sync_audit_log_repo.list_pending(self._conn):
            fetcher = ENTITY_ROW_FETCHERS.get(audit_row["entity_name"])
            if fetcher is None:
                continue
            payload = fetcher(self._conn, audit_row["record_id"])
            if payload is None:
                continue  # row no longer exists locally; nothing to push
            records.append(
                SyncRecord(
                    sync_id=audit_row["sync_id"],
                    entity_name=audit_row["entity_name"],
                    record_id=audit_row["record_id"],
                    action_type=SyncActionType(audit_row["action_type"]),
                    payload=payload,
                    updated_at=audit_row["updated_at"],
                )
            )
        return records

    def _apply_conflict_resolutions(self, conflicts: list[SyncResult]) -> None:
        """Last-Write-Wins: the server rejected our write because its row
        was newer, so we overwrite our local copy with the server's
        authoritative payload.
        """
        for result in conflicts:
            if result.winning_payload is None:
                continue
            entity = sync_audit_log_repo.get_entity_for_sync_id(self._conn, result.sync_id)
            if entity is None:
                continue
            entity_name, record_id = entity
            overwrite_row(self._conn, entity_name, record_id, result.winning_payload)
