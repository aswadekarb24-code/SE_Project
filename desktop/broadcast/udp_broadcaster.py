"""Real LAN broadcaster: sends TokenUpdatePayload as UDP packets on
BROADCAST_PORT, matching the design doc's socket spec. Fire-and-forget --
UDP delivery isn't guaranteed, matching the Broadcaster Protocol's contract.
"""

from __future__ import annotations

import socket

from common.broadcast_protocol import BROADCAST_PORT, TokenUpdatePayload


class UdpBroadcaster:
    def __init__(
        self,
        port: int = BROADCAST_PORT,
        broadcast_address: str = "255.255.255.255",
    ) -> None:
        self._port = port
        self._address = broadcast_address
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if broadcast_address == "255.255.255.255":
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def broadcast_token_update(
        self, *, token_id: str, token_num: int, dept_id: int, status: str
    ) -> bool:
        payload = TokenUpdatePayload(
            token_id=token_id, token_num=token_num, dept_id=dept_id, status=status
        )
        try:
            self._sock.sendto(payload.encode(), (self._address, self._port))
            return True
        except OSError:
            return False

    def close(self) -> None:
        self._sock.close()
