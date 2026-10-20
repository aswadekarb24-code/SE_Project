"""Real LAN broadcaster: sends token and doctor-status packets as UDP on
BROADCAST_PORT, matching the design doc's socket spec. Fire-and-forget --
UDP delivery isn't guaranteed, matching the Broadcaster Protocol's contract.
"""

from __future__ import annotations

import socket

from common.broadcast_protocol import BROADCAST_PORT, DoctorStatusPayload, TokenUpdatePayload


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
        return self._send(payload.encode())

    def broadcast_doctor_status(
        self, *, doctor_id: str, name: str, dept_id: int, status: str
    ) -> bool:
        payload = DoctorStatusPayload(
            doctor_id=doctor_id, name=name, dept_id=dept_id, status=status
        )
        return self._send(payload.encode())

    def _send(self, data: bytes) -> bool:
        try:
            self._sock.sendto(data, (self._address, self._port))
            return True
        except OSError:
            return False

    def close(self) -> None:
        self._sock.close()
