"""Shortened display-node soak test. The SQA plan's real 72-hour hardware
soak isn't feasible in CI (no Xvfb for the Tkinter widgets -- see
docs/progress/cycle-2.md); this is a scoped-down proxy that proves the
listener thread survives sustained, bursty traffic -- including interleaved
corrupted packets -- without leaking the thread or dropping the connection.
Now that both the display path (Cycle 2) and sync path (Cycle 4) are live,
this is the point the SQA plan calls for this check to happen.
"""

from __future__ import annotations

import queue
import socket
import time

from common.broadcast_protocol import BROADCAST_PORT, TokenUpdatePayload
from display_sim.udp_listener import UdpListener

SOAK_DURATION_SECONDS = 3
PACKETS_PER_BURST = 50


def test_listener_survives_sustained_bursty_traffic():
    port = BROADCAST_PORT + 3
    received: queue.Queue = queue.Queue()

    listener = UdpListener(on_update=received.put_nowait, port=port, bind_address="127.0.0.1")
    listener.start()
    time.sleep(0.1)

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent_count = 0
    deadline = time.monotonic() + SOAK_DURATION_SECONDS
    try:
        while time.monotonic() < deadline:
            for _ in range(PACKETS_PER_BURST):
                payload = TokenUpdatePayload(
                    token_id=f"soak-{sent_count}", token_num=sent_count, dept_id=1, status="WAITING"
                )
                sender.sendto(payload.encode(), ("127.0.0.1", port))
                sent_count += 1
            sender.sendto(b"garbage-packet-should-be-dropped", ("127.0.0.1", port))
            time.sleep(0.05)
    finally:
        sender.close()

    time.sleep(0.3)  # drain remaining in-flight packets
    received_count = received.qsize()

    assert listener._thread.is_alive()
    assert received_count > 0
    # UDP has no delivery guarantee even on loopback under load; assert most
    # packets arrived rather than requiring every single one.
    assert received_count >= sent_count * 0.9

    listener.stop()
    assert not listener._thread.is_alive()
