"""Embedded LAN display simulator: a standalone process that listens for
broadcasts exactly like a future Raspberry Pi/ESP32 client would. It shows
the live queue (WAITING/CALLED/DONE, coloured by status) and doctor
availability, and chimes when a patient is called. Run as a separate
process from the desktop app to demo live LAN updates:
`uv run python -m display_sim.main`.
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont

from common import design_tokens as tokens
from common.broadcast_protocol import DoctorStatusPayload, Packet, TokenUpdatePayload
from display_sim.display_state import DisplayState
from display_sim.udp_listener import UdpListener

# Row text colour per token status; anything else uses TEXT_PRIMARY.
_STATUS_COLORS = {"CALLED": tokens.PRIMARY, "DONE": tokens.TEXT_SECONDARY}
_DOCTOR_COLORS = {
    "AVAILABLE": tokens.SUCCESS,
    "BUSY": tokens.WARNING,
    "OFF_DUTY": tokens.TEXT_SECONDARY,
}


class DisplaySimApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HMS Display Simulator")
        self.root.configure(bg=tokens.CANVAS)
        self.root.minsize(900, 480)
        installed = set(tkfont.families(root))
        family = next((f for f in tokens.FONT_FAMILIES if f in installed), "TkDefaultFont")
        self._row_font = (family, 20)
        self._doctor_font = (family, 15)
        self._title_font = (family, 13, "bold")
        status_font = (family, 11)
        self.state = DisplayState()
        self._updates: queue.Queue[Packet] = queue.Queue()
        self._labels: dict[tuple[int, str], tk.Label] = {}
        self._doctor_labels: dict[str, tk.Label] = {}
        self.chimes = 0

        panels = tk.Frame(root, bg=tokens.CANVAS)
        panels.pack(padx=tokens.SPACE_3, pady=tokens.SPACE_3, fill="both", expand=True)
        self.list_frame = self._card(panels, "NOW SERVING / QUEUE")
        self.list_frame.master.pack(side="left", fill="both", expand=True)
        self.doctor_frame = self._card(panels, "DOCTORS")
        self.doctor_frame.master.pack(side="left", fill="y", padx=(tokens.SPACE_2, 0))
        self.doctor_frame.master.configure(width=300)

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

    def _card(self, parent: tk.Frame, title: str) -> tk.Frame:
        """A white card with a small heading; returns the frame rows go into."""
        card = tk.Frame(
            parent,
            bg=tokens.SURFACE,
            highlightthickness=1,
            highlightbackground=tokens.BORDER,
            padx=tokens.SPACE_3,
            pady=tokens.SPACE_2,
        )
        tk.Label(
            card,
            text=title,
            anchor="w",
            bg=tokens.SURFACE,
            fg=tokens.PRIMARY,
            font=self._title_font,
        ).pack(fill="x", pady=(0, tokens.SPACE_1))
        body = tk.Frame(card, bg=tokens.SURFACE)
        body.pack(fill="both", expand=True)
        return body

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

    def _render(self, payload: Packet) -> None:
        if isinstance(payload, DoctorStatusPayload):
            self._render_doctor(payload)
        else:
            self._render_token(payload)

    def _render_token(self, payload: TokenUpdatePayload) -> None:
        if self.state.is_new_call(payload):
            self.chime()
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

    def _render_doctor(self, payload: DoctorStatusPayload) -> None:
        row = self.state.apply_doctor(payload)
        label = self._doctor_labels.get(payload.doctor_id)
        if label is None:
            label = tk.Label(
                self.doctor_frame,
                anchor="w",
                justify="left",
                bg=tokens.SURFACE,
                font=self._doctor_font,
                pady=4,
            )
            self._doctor_labels[payload.doctor_id] = label
        label.config(text=row.text, fg=_DOCTOR_COLORS.get(row.status, tokens.TEXT_PRIMARY))
        # Re-pack in name order so the list stays alphabetical.
        for doctor in self.state.doctors():
            self._doctor_labels[doctor.doctor_id].pack_forget()
        for doctor in self.state.doctors():
            self._doctor_labels[doctor.doctor_id].pack(fill="x")

    def chime(self) -> None:
        """Audible cue that a new patient has been called."""
        self.chimes += 1
        self.root.bell()

    def _on_close(self) -> None:
        self.listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DisplaySimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
