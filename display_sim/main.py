"""Embedded LAN display simulator: a standalone process that listens for
queue-token broadcasts exactly like a future Raspberry Pi/ESP32 client would,
rendering live WAITING/CALLED/DONE status. Run as a separate process from the
desktop app to demo live LAN updates: `uv run python -m display_sim.main`.
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont

from common import design_tokens as tokens
from common.broadcast_protocol import TokenUpdatePayload
from display_sim.display_state import DisplayState
from display_sim.udp_listener import UdpListener

# Row text colour per token status; anything else uses TEXT_PRIMARY.
_STATUS_COLORS = {"CALLED": tokens.PRIMARY, "DONE": tokens.TEXT_SECONDARY}


class DisplaySimApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HMS Display Simulator")
        self.root.configure(bg=tokens.CANVAS)
        self.root.minsize(640, 420)
        installed = set(tkfont.families(root))
        family = next((f for f in tokens.FONT_FAMILIES if f in installed), "TkDefaultFont")
        self._row_font = (family, 20)
        status_font = (family, 11)
        self.state = DisplayState()
        self._updates: queue.Queue[TokenUpdatePayload] = queue.Queue()
        self._labels: dict[tuple[int, str], tk.Label] = {}

        self.list_frame = tk.Frame(
            root,
            bg=tokens.SURFACE,
            highlightthickness=1,
            highlightbackground=tokens.BORDER,
            padx=tokens.SPACE_3,
            pady=tokens.SPACE_2,
        )
        self.list_frame.pack(padx=tokens.SPACE_3, pady=tokens.SPACE_3, fill="both", expand=True)
        self.status_var = tk.StringVar(value="Waiting for updates...")
        tk.Label(
            root,
            textvariable=self.status_var,
            bg=tokens.CANVAS,
            fg=tokens.TEXT_SECONDARY,
            font=status_font,
        ).pack(pady=(0, tokens.SPACE_2))

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
            label = tk.Label(
                self.list_frame,
                text=row.text,
                anchor="w",
                bg=tokens.SURFACE,
                font=self._row_font,
                pady=6,
            )
            label.pack(fill="x")
            self._labels[key] = label
        else:
            label.config(text=row.text)
        label.config(fg=_STATUS_COLORS.get(row.status, tokens.TEXT_PRIMARY))

    def _on_close(self) -> None:
        self.listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DisplaySimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
