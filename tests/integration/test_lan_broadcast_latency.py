"""Exercises FR-02 (queue updates reach display clients in <500ms) and the
SQA plan's packet-corruption protocol, using two real UDP sockets over
loopback -- no docker/network setup required, since this is testing two real
processes/sockets talking over a real (if local) network path.
"""

import queue
import socket
import time

from common.broadcast_protocol import BROADCAST_PORT
from desktop.broadcast.udp_broadcaster import UdpBroadcaster
from display_sim.udp_listener import UdpListener


def test_broadcast_delivered_under_500ms():
    port = BROADCAST_PORT + 1  # avoid clashing with a real listener on the default port
    received: queue.Queue = queue.Queue()

    listener = UdpListener(on_update=received.put_nowait, port=port, bind_address="127.0.0.1")
    listener.start()
    time.sleep(0.1)  # let the listener thread finish binding before sending

    broadcaster = UdpBroadcaster(port=port, broadcast_address="127.0.0.1")
    try:
        start = time.perf_counter()
        sent = broadcaster.broadcast_token_update(
            token_id="t1", token_num=1, dept_id=1, status="WAITING"
        )
        assert sent is True

        payload = received.get(timeout=0.5)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"broadcast took {elapsed_ms:.1f}ms, exceeding the FR-02 target"
        assert payload.token_id == "t1"
        assert payload.status == "WAITING"
    finally:
        broadcaster.close()
        listener.stop()


def test_corrupted_packet_is_dropped_and_listener_keeps_running():
    port = BROADCAST_PORT + 2
    received: queue.Queue = queue.Queue()

    listener = UdpListener(on_update=received.put_nowait, port=port, bind_address="127.0.0.1")
    listener.start()
    time.sleep(0.1)

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcaster = UdpBroadcaster(port=port, broadcast_address="127.0.0.1")
    try:
        raw_sock.sendto(b"not-json-garbage", ("127.0.0.1", port))
        broadcaster.broadcast_token_update(token_id="t2", token_num=2, dept_id=1, status="WAITING")

        payload = received.get(timeout=0.5)
        assert payload.token_id == "t2"  # the corrupted packet was skipped
        assert received.empty()  # nothing else arrived for the garbage packet
    finally:
        raw_sock.close()
        broadcaster.close()
        listener.stop()
