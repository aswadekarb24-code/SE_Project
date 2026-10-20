"""Doctor availability list: status, department and weekly OPD hours.

Doctors can change any doctor's status (as before) and edit their own OPD
hours. Reception gets the same list read-only, to direct patients.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from common.clock import local_today
from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.department_service import list_departments
from desktop.services.doctor_service import (
    STATUSES,
    WEEKDAYS,
    ScheduleError,
    format_schedule,
    get_schedules,
    in_opd_on,
    list_doctors,
    schedule_days,
    set_doctor_status,
    set_schedule,
)
from desktop.ui.components import (
    STATUS_BADGES,
    Avatar,
    Badge,
    button,
    combo_box,
    field,
    label,
)

# OPD time choices: every 30 minutes from 06:00 to 23:30.
TIME_CHOICES = [f"{hour:02d}:{minute:02d}" for hour in range(6, 24) for minute in (0, 30)]


class ScheduleDialog(QDialog):
    """Edit one doctor's weekly OPD days and hours."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        doctor: dict,
        schedule: dict | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"OPD hours: {doctor['full_name']}")
        self.setModal(True)
        self._conn = conn
        self._doctor = doctor
        self.saved: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label("OPD hours", "dialogTitle"))
        layout.addWidget(label("Reception sees these on the Doctors page.", "muted", wrap=True))

        current_days = schedule_days(schedule) if schedule else WEEKDAYS[:5]
        days_row = QHBoxLayout()
        days_row.setSpacing(6)
        self.day_buttons: dict[str, QPushButton] = {}
        for day in WEEKDAYS:
            toggle = QPushButton(day)
            toggle.setObjectName("dayToggle")
            toggle.setCheckable(True)
            toggle.setChecked(day in current_days)
            days_row.addWidget(toggle)
            self.day_buttons[day] = toggle
        days_box = QWidget()
        days_box.setLayout(days_row)
        days_row.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field("Days", days_box))

        self.start_select = combo_box()
        self.end_select = combo_box()
        for combo in (self.start_select, self.end_select):
            combo.addItems(TIME_CHOICES)
        self.start_select.setCurrentText(schedule["start_time"] if schedule else "09:00")
        self.end_select.setCurrentText(schedule["end_time"] if schedule else "13:00")
        times = QHBoxLayout()
        times.setSpacing(12)
        times.addWidget(field("From", self.start_select))
        times.addWidget(field("To", self.end_select))
        layout.addLayout(times)

        self.error_label = label("", "errorLabel", wrap=True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_button = button("Save hours", "primary", "check")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)
        footer.addWidget(cancel)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

    def save(self) -> None:
        days = [day for day, toggle in self.day_buttons.items() if toggle.isChecked()]
        try:
            self.saved = set_schedule(
                self._conn,
                self._doctor["doctor_id"],
                days,
                self.start_select.currentText(),
                self.end_select.currentText(),
            )
        except ScheduleError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        self.accept()


class DoctorAvailabilityWidget(QWidget):
    def __init__(
        self,
        conn: sqlite3.Connection,
        parent=None,
        *,
        current_doctor_id: str | None = None,
        read_only: bool = False,
        broadcaster: Broadcaster | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._current_doctor_id = current_doctor_id
        self._read_only = read_only
        self._broadcaster = broadcaster
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._combos: dict[str, QComboBox] = {}
        self._badges: dict[str, Badge] = {}
        self._details: dict[str, object] = {}
        self._today_labels: dict[str, object] = {}
        self.edit_hours_button: QPushButton | None = None
        self.refresh()

    def refresh(self) -> None:
        departments = dict(list_departments(self._conn))
        schedules = get_schedules(self._conn)
        today = local_today()
        doctors = list_doctors(self._conn)
        # The signed-in doctor first, then everyone else alphabetically.
        doctors.sort(key=lambda d: (d["doctor_id"] != self._current_doctor_id, d["full_name"]))
        for doctor in doctors:
            doctor_id = doctor["doctor_id"]
            if doctor_id not in self._badges:
                self._add_row(doctor)
            schedule = schedules.get(doctor_id)
            department = departments.get(doctor["dept_id"], "")
            self._details[doctor_id].setText(f"{department}  ·  OPD {format_schedule(schedule)}")
            self._today_labels[doctor_id].setText(
                f"Today {schedule['start_time']}–{schedule['end_time']}"
                if in_opd_on(schedule, today)
                else "Not in OPD today"
            )
            self._badges[doctor_id].set(*STATUS_BADGES[doctor["status"]])
            combo = self._combos.get(doctor_id)
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentIndex(STATUSES.index(doctor["status"]))
                combo.blockSignals(False)

    def _add_row(self, doctor: dict) -> None:
        doctor_id = doctor["doctor_id"]
        row = QFrame()
        row.setObjectName("listRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 12, 4, 12)
        layout.setSpacing(14)
        layout.addWidget(Avatar(doctor["full_name"], 40))
        text = QVBoxLayout()
        text.setSpacing(2)
        is_me = doctor_id == self._current_doctor_id
        text.addWidget(label(doctor["full_name"] + ("  (you)" if is_me else ""), "cellTitle"))
        detail = label("", "muted")
        text.addWidget(detail)
        layout.addLayout(text, 1)
        self._details[doctor_id] = detail

        today = label("", "muted")
        layout.addWidget(today)
        self._today_labels[doctor_id] = today
        badge = Badge()
        layout.addWidget(badge)
        self._badges[doctor_id] = badge

        if not self._read_only:
            if is_me:
                edit = button("Edit hours", "ghost")
                edit.clicked.connect(lambda: self.edit_hours(doctor_id))
                layout.addWidget(edit)
                self.edit_hours_button = edit
            combo = combo_box()
            combo.setFixedWidth(170)
            for status in STATUSES:
                combo.addItem(STATUS_BADGES[status][0], status)
            combo.currentIndexChanged.connect(
                lambda index, did=doctor_id, c=combo: self._on_status_changed(
                    did, c.itemData(index)
                )
            )
            layout.addWidget(combo)
            self._combos[doctor_id] = combo
        self._layout.addWidget(row)

    def edit_hours(self, doctor_id: str) -> None:
        doctor = next(d for d in list_doctors(self._conn) if d["doctor_id"] == doctor_id)
        dialog = ScheduleDialog(self._conn, doctor, get_schedules(self._conn).get(doctor_id), self)
        if dialog.exec():
            self.refresh()

    def _on_status_changed(self, doctor_id: str, status: str) -> None:
        set_doctor_status(self._conn, doctor_id, status, broadcaster=self._broadcaster)
        self._badges[doctor_id].set(*STATUS_BADGES[status])
