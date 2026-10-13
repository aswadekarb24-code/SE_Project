"""Shown once at startup: picks which role's screens to show. No password --
matches the MVP's lightweight dual-role interface, not a full auth system.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from desktop.services.auth_service import Role


class RoleSelectDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Role")
        self.selected_role: Role | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Who is signing in?"))

        receptionist_button = QPushButton("Receptionist")
        receptionist_button.clicked.connect(lambda: self._select(Role.RECEPTIONIST))
        layout.addWidget(receptionist_button)

        doctor_button = QPushButton("Doctor")
        doctor_button.clicked.connect(lambda: self._select(Role.DOCTOR))
        layout.addWidget(doctor_button)

    def _select(self, role: Role) -> None:
        self.selected_role = role
        self.accept()
