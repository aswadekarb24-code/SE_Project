"""Shared data-transfer objects used across desktop, gateway, and display_sim.

Kept dependency-free (stdlib only) so this module can be imported by any of the
three runtime processes without pulling in PyQt6, FastAPI, or Tkinter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncStatus(str, Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    CONFLICT = "CONFLICT"


class SyncActionType(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class SyncRecord:
    """A single pending mutation read from sync_audit_log, ready to push."""

    sync_id: int
    entity_name: str
    record_id: str
    action_type: SyncActionType
    payload: dict
    updated_at: str  # ISO 8601 UTC, microsecond precision


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of attempting to push one SyncRecord."""

    sync_id: int
    status: SyncStatus
    winning_payload: dict | None = None  # set when status == CONFLICT
    error: str | None = None


class TokenStatus(str, Enum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    DONE = "DONE"


@dataclass(frozen=True, slots=True)
class PatientIntake:
    """Reception check-in form input. patient_id is None for a new/walk-in
    patient (the service generates a UUIDv4); set it for a returning patient
    looked up by an existing record.
    """

    full_name: str
    dob: str  # ISO date, YYYY-MM-DD
    gender: str | None = None
    contact_no: str | None = None
    patient_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueueTokenIssued:
    """Result of IssueQueueToken(), including the broadcast payload."""

    token_id: str
    patient_id: str
    dept_id: int
    token_num: int
    status: TokenStatus
    broadcast_status: bool


@dataclass(frozen=True, slots=True)
class QueueTokenUpdate:
    """Result of a queue-token state transition (call_next/complete_token)."""

    token_id: str
    dept_id: int
    token_num: int
    status: TokenStatus
    broadcast_status: bool
