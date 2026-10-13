"""1-click bed status toggle grid (Available/Occupied/Maintenance)."""

from __future__ import annotations

import sqlite3

from PyQt6.QtWidgets import QGridLayout, QPushButton, QWidget

from desktop.services.bed_service import list_beds, toggle_bed

_COLORS = {
    "AVAILABLE": "#2e7d32",
    "OCCUPIED": "#c62828",
    "MAINTENANCE": "#f9a825",
}
_COLUMNS = 5


class BedMatrixWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._layout = QGridLayout(self)
        self._buttons: dict[str, QPushButton] = {}
        self.refresh()

    def refresh(self) -> None:
        for bed in list_beds(self._conn):
            button = self._buttons.get(bed["bed_id"])
            if button is None:
                button = QPushButton()
                button.clicked.connect(lambda _checked, bid=bed["bed_id"]: self._on_toggle(bid))
                index = len(self._buttons)
                self._layout.addWidget(button, index // _COLUMNS, index % _COLUMNS)
                self._buttons[bed["bed_id"]] = button
            self._style_button(button, bed)

    def _style_button(self, button: QPushButton, bed: dict) -> None:
        button.setText(f"{bed['label']}\n{bed['status']}")
        button.setStyleSheet(f"background-color: {_COLORS[bed['status']]}; color: white;")

    def _on_toggle(self, bed_id: str) -> None:
        toggle_bed(self._conn, bed_id)
        self.refresh()
