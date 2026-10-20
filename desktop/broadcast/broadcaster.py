"""Broadcaster seam: queue_service depends on this interface only. Cycle 2
wires in the real UDP broadcaster (desktop/broadcast/udp_broadcaster.py);
until then, NullBroadcaster keeps queue-token issuance fully functional with
broadcast_status always False -- same DI pattern as SyncProvider.
"""

from __future__ import annotations

from typing import Protocol


class Broadcaster(Protocol):
    def broadcast_token_update(
        self, *, token_id: str, token_num: int, dept_id: int, status: str
    ) -> bool:
        """Send a queue-token update to LAN display clients. Returns whether
        the broadcast was sent -- not whether it was received, since UDP is
        fire-and-forget.
        """
        ...

    def broadcast_doctor_status(
        self, *, doctor_id: str, name: str, dept_id: int, status: str
    ) -> bool:
        """Send a doctor's availability to LAN display clients."""
        ...


class NullBroadcaster:
    def broadcast_token_update(
        self, *, token_id: str, token_num: int, dept_id: int, status: str
    ) -> bool:
        return False

    def broadcast_doctor_status(
        self, *, doctor_id: str, name: str, dept_id: int, status: str
    ) -> bool:
        return False
