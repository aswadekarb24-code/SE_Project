"""Embedded LAN display simulator: a standalone process that listens for
queue-token broadcasts exactly like a future Raspberry Pi/ESP32 client would,
rendering live WAITING/CALLED/DONE status. Run as a separate process from the
desktop app to demo live LAN updates: `uv run python -m display_sim.main`.
"""

from __future__ import annotations

import queue
import tkinter as tk

from common.broadcast_protocol import TokenUpdatePayload
from display_sim.display_state import DisplayState
from display_sim.udp_listener import UdpListener


class DisplaySimApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HMS Display Simulator")
        self.state = DisplayState()
        self._updates: queue.Queue[TokenUpdatePayload] = queue.Queue()
        self._labels: dict[tuple[int, str], tk.Label] = {}

        self.list_frame = tk.Frame(root)
        self.list_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.status_var = tk.StringVar(value="Waiting for updates...")
        tk.Label(root, textvariable=self.status_var).pack()

        self.listener = UdpListener(on_update=self._updates.put_nowait)
        self.listener.start()
        self.root.after(100, self._poll_updates)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _poll_updates(self) -> None:
        drained = 0
        while True:
            try:
                payload = self._updates.get_nowait()
            except queue.Empty:
                break
            self._render(payload)
            drained += 1
        if drained:
            self.status_var.set(f"Last update: {drained} packet(s) processed")
        self.root.after(100, self._poll_updates)

    def _render(self, payload: TokenUpdatePayload) -> None:
        row = self.state.apply(payload)
        key = (payload.dept_id, payload.token_id)
        label = self._labels.get(key)
        if label is None:
            label = tk.Label(self.list_frame, text=row.text, anchor="w")
            label.pack(fill="x")
            self._labels[key] = label
        else:
            label.config(text=row.text)
        label.config(fg="gray" if row.status == "DONE" else "black")

    def _on_close(self) -> None:
        self.listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DisplaySimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
