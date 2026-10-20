"""Shared UDP packet schema between desktop's broadcaster and display_sim's
listener. Keeping this in common/ means both processes encode/decode
identically without importing each other, and a future real Pi/ESP32 client
only needs to speak this same wire format.

Two packet kinds share the port, told apart by a "kind" field: "token"
(queue-token updates) and "doctor" (doctor availability). Token packets
from before "kind" existed have no such field and still decode as tokens.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

BROADCAST_PORT = 5005


class PacketDecodeError(ValueError):
    """Raised when a received UDP packet is not a valid payload.

    Callers (the display listener) are expected to drop the packet and keep
    listening rather than propagate this -- UDP offers no delivery guarantee,
    so a corrupted/truncated packet is an expected condition, not a crash.
    """


@dataclass(frozen=True, slots=True)
class TokenUpdatePayload:
    token_id: str
    token_num: int
    dept_id: int
    status: str

    def encode(self) -> bytes:
        return json.dumps({"kind": "token", **asdict(self)}).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> TokenUpdatePayload:
        obj = _json_object(data)
        if obj.get("kind", "token") != "token":
            raise PacketDecodeError(f"not a token packet: kind={obj.get('kind')!r}")
        try:
            return TokenUpdatePayload(
                token_id=str(obj["token_id"]),
                token_num=int(obj["token_num"]),
                dept_id=int(obj["dept_id"]),
                status=str(obj["status"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PacketDecodeError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class DoctorStatusPayload:
    """A doctor's availability, for the waiting-room display."""

    doctor_id: str
    name: str
    dept_id: int
    status: str

    def encode(self) -> bytes:
        return json.dumps({"kind": "doctor", **asdict(self)}).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> DoctorStatusPayload:
        obj = _json_object(data)
        if obj.get("kind") != "doctor":
            raise PacketDecodeError(f"not a doctor packet: kind={obj.get('kind')!r}")
        try:
            return DoctorStatusPayload(
                doctor_id=str(obj["doctor_id"]),
                name=str(obj["name"]),
                dept_id=int(obj["dept_id"]),
                status=str(obj["status"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PacketDecodeError(str(exc)) from exc


Packet = TokenUpdatePayload | DoctorStatusPayload


def decode_packet(data: bytes) -> Packet:
    """Decode either packet kind. Raises PacketDecodeError for anything else."""
    kind = _json_object(data).get("kind", "token")
    if kind == "doctor":
        return DoctorStatusPayload.decode(data)
    return TokenUpdatePayload.decode(data)


def _json_object(data: bytes) -> dict:
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketDecodeError(str(exc)) from exc
    if not isinstance(obj, dict):
        raise PacketDecodeError(f"expected a JSON object, got {type(obj).__name__}")
    return obj
