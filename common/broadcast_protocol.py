"""Shared UDP packet schema between desktop's broadcaster and display_sim's
listener. Keeping this in common/ means both processes encode/decode
identically without importing each other, and a future real Pi/ESP32 client
only needs to speak this same wire format.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

BROADCAST_PORT = 5005


class PacketDecodeError(ValueError):
    """Raised when a received UDP packet is not a valid token-update payload.

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
        return json.dumps(asdict(self)).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> TokenUpdatePayload:
        try:
            obj = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PacketDecodeError(str(exc)) from exc

        if not isinstance(obj, dict):
            raise PacketDecodeError(f"expected a JSON object, got {type(obj).__name__}")

        try:
            return TokenUpdatePayload(
                token_id=str(obj["token_id"]),
                token_num=int(obj["token_num"]),
                dept_id=int(obj["dept_id"]),
                status=str(obj["status"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PacketDecodeError(str(exc)) from exc
