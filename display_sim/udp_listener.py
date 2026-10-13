"""Listens for TokenUpdatePayload broadcasts on BROADCAST_PORT. Runs in its
own thread so the display's UI event loop stays responsive. Malformed or
corrupted packets are dropped (and listening continues) rather than crashing
the process -- the behavior the SQA plan's "packet corruption checks" protocol
exercises.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable

from common.broadcast_protocol import BROADCAST_PORT, PacketDecodeError, TokenUpdatePayload

OnUpdate = Callable[[TokenUpdatePayload], None]


class UdpListener:
    def __init__(
        self,
        on_update: OnUpdate,
        port: int = BROADCAST_PORT,
        bind_address: str = "0.0.0.0",
    ) -> None:
        self._on_update = on_update
        self._port = port
        self._bind_address = bind_address
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._bind_address, self._port))
        self._sock.settimeout(0.5)
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self) -> None:
        while self._running:
            try:
                data, _addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                payload = TokenUpdatePayload.decode(data)
            except PacketDecodeError:
                continue  # drop corrupted/malformed packets, keep listening

            self._on_update(payload)

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._sock is not None:
            self._sock.close()
