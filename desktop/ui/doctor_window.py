"""Doctor console: Call Next / Complete Consultation, driving the queue-token
state machine (WAITING -> CALLED -> DONE) and broadcasting each transition to
LAN display clients.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.department_service import list_departments
from desktop.services.queue_service import call_next, complete_token


class DoctorWindow(QWidget):
    def __init__(
        self,
        conn: sqlite3.Connection,
        broadcaster: Broadcaster | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._broadcaster = broadcaster
        self._current_token_id: str | None = None

        self.department_select = QComboBox()
        for dept_id, name in list_departments(conn):
            self.department_select.addItem(name, dept_id)

        self.call_next_button = QPushButton("Call Next")
        self.call_next_button.setProperty("variant", "primary")
        self.call_next_button.clicked.connect(self._on_call_next)
        self.complete_button = QPushButton("Complete Consultation")
        self.complete_button.clicked.connect(self._on_complete)
        self.complete_button.setEnabled(False)

        self.status_label = QLabel("No patient called")
        self.status_label.setObjectName("statusLabel")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.department_select)
        layout.addWidget(self.call_next_button)
        layout.addWidget(self.complete_button)
        layout.addWidget(self.status_label)

    def _on_call_next(self) -> None:
        department_id = self.department_select.currentData()
        result = call_next(self._conn, department_id, broadcaster=self._broadcaster)

        if result is None:
            self.status_label.setText("Queue is empty for this department")
            self.complete_button.setEnabled(False)
            self._current_token_id = None
            return

        self._current_token_id = result.token_id
        self.status_label.setText(f"Now serving token #{result.token_num} ({result.status.value})")
        self.complete_button.setEnabled(True)

    def _on_complete(self) -> None:
        if self._current_token_id is None:
            return

        result = complete_token(self._conn, self._current_token_id, broadcaster=self._broadcaster)
        self.status_label.setText(f"Token #{result.token_num} complete ({result.status.value})")
        self.complete_button.setEnabled(False)
        self._current_token_id = None
