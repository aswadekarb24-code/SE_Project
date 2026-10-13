# Cycle 2 — LAN Broadcast + Display Simulator

## Objectives & risks addressed

De-risk FR-02 (queue updates reach LAN display clients in <500ms) and the
UDP broadcast protocol's robustness against corrupted/dropped packets, ahead
of ever owning real Raspberry Pi/ESP32 hardware. Also completes the queue
token's full lifecycle (WAITING→CALLED→DONE) via the Doctor console, which
Cycle 1 deliberately left unbuilt.

## What shipped (demoable)

- `common/broadcast_protocol.py` — the shared `TokenUpdatePayload` wire
  format (JSON over UDP, port 5005) with `encode`/`decode`, raising
  `PacketDecodeError` on anything malformed so receivers can drop and
  continue rather than crash.
- `desktop/broadcast/udp_broadcaster.py` — the real `Broadcaster`
  implementation, swapped in for `NullBroadcaster` with zero changes to
  `queue_service`, exactly as the Cycle 1 DI seam was designed for.
- `display_sim/udp_listener.py` + `display_sim/display_state.py` +
  `display_sim/main.py` — a standalone Tkinter process that listens on the
  same protocol a real embedded display would, tracks latest status per
  token, and renders it live. Business logic (`DisplayState`) is kept
  Tkinter-free so it's unit-testable without a display/Xvfb.
- `desktop/services/queue_service.call_next()` / `complete_token()` — the
  rest of the queue-token state machine, each broadcasting its transition.
  Both reject invalid transitions via `InvalidTokenTransitionError`
  (completing an un-called token, double-completing, calling into an empty
  queue returns `None` rather than erroring — "no one waiting" is a normal
  state, not a failure).
- `desktop/ui/doctor_window.py` — Call Next / Complete Consultation screen,
  now a second tab alongside Reception in `desktop/main.py`, sharing one
  `UdpBroadcaster` instance.
- 23 new tests across `tests/unit/` (protocol encode/decode + corruption
  cases, `DisplayState` tracking, `call_next`/`complete_token` happy paths
  and boundary cases, Doctor-window UI flow including a duplicate-click
  scenario) and `tests/integration/test_lan_broadcast_latency.py` (two real
  UDP sockets over loopback: delivery-latency and packet-corruption tests).

Demo performed: `uv run pytest` full suite (42/42 pass); a standalone script
sent a real `255.255.255.255` broadcast from `UdpBroadcaster` and confirmed
`UdpListener` received and decoded it on the default port (5005) — the real
wire path, not just the loopback-scoped integration test.

## Metrics measured this cycle

- Unit + integration test coverage: 94% (305 statements, 19 missed —
  mostly `except OSError` branches and `if __name__ == "__main__"` guards).
- LAN broadcast latency: delivered well under the 500ms FR-02 target over
  loopback (test asserts `<500ms`; in practice sub-millisecond on localhost).
  Real default-broadcast-address delivery verified manually, consistent with
  the loopback-scoped automated test.
- Soak test: not yet applicable (Cycle 4, once sync + display are both live).
- Open defects: P1 0 / P2 0 / P3 0 / P4 0.
- Packet-corruption protocol: 1/1 test confirms a garbage UDP packet is
  dropped and a subsequent valid packet still arrives — the listener thread
  never crashes on malformed input.

## Carried-over risks / decisions for next cycle

- `display_sim`'s Tkinter widgets are not unit-tested in CI (no Xvfb
  configured) — only the Tkinter-free `DisplayState` logic is. This is an
  accepted gap, documented rather than silently skipped; a 72-hour soak test
  of the actual running display is still planned for Cycle 4 per the SQA
  plan, which would exercise the real widgets manually/on real hardware.
- Cycle 3 adds Doctor/Bed/Pharmacy modules and role-based access; the
  hardcoded `DEPARTMENTS` placeholder in `reception_window.py` and
  `doctor_window.py` gets replaced by a real departments table at that point.
- Cycle 3 is also where ≥80% coverage is formally reassessed per the plan;
  currently sitting at 94%, comfortably ahead of that gate.
