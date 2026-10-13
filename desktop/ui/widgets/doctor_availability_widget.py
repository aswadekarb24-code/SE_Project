"""Doctor availability list with self-service status toggle."""

from __future__ import annotations

import sqlite3

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop.services.doctor_service import STATUSES, list_doctors, set_doctor_status


class DoctorAvailabilityWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._layout = QVBoxLayout(self)
        self._combos: dict[str, QComboBox] = {}
        self.refresh()

    def refresh(self) -> None:
        for doctor in list_doctors(self._conn):
            combo = self._combos.get(doctor["doctor_id"])
            if combo is None:
                row = QHBoxLayout()
                row.addWidget(QLabel(doctor["full_name"]))
                combo = QComboBox()
                combo.addItems(STATUSES)
                combo.currentTextChanged.connect(
                    lambda status, did=doctor["doctor_id"]: self._on_status_changed(did, status)
                )
                row.addWidget(combo)
                self._layout.addLayout(row)
                self._combos[doctor["doctor_id"]] = combo
            combo.blockSignals(True)
            combo.setCurrentText(doctor["status"])
            combo.blockSignals(False)

    def _on_status_changed(self, doctor_id: str, status: str) -> None:
        set_doctor_status(self._conn, doctor_id, status)
