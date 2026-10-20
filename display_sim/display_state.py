"""Pure tracking logic for the display simulator -- deliberately free of
Tkinter so it's unit-testable without a display/Xvfb. main.py wraps this in
actual widgets.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.broadcast_protocol import DoctorStatusPayload, TokenUpdatePayload


@dataclass(frozen=True, slots=True)
class DisplayRow:
    dept_id: int
    token_num: int
    status: str

    @property
    def text(self) -> str:
        return f"Dept {self.dept_id} - Token #{self.token_num}: {self.status}"


_DOCTOR_STATUS_TEXT = {"AVAILABLE": "Available", "BUSY": "Busy", "OFF_DUTY": "Off duty"}


@dataclass(frozen=True, slots=True)
class DoctorRow:
    doctor_id: str
    name: str
    dept_id: int
    status: str

    @property
    def text(self) -> str:
        return f"{self.name}: {_DOCTOR_STATUS_TEXT.get(self.status, self.status.title())}"


class DisplayState:
    """Keeps the latest known status per token, keyed by (dept_id, token_id),
    and per doctor, keyed by doctor_id.
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[int, str], DisplayRow] = {}
        self._doctors: dict[str, DoctorRow] = {}

    def is_new_call(self, payload: TokenUpdatePayload) -> bool:
        """Whether this packet calls a patient who wasn't already being called
        -- the moment the display should chime. Repeated or late duplicate
        packets for an already-called token stay silent.
        """
        if payload.status != "CALLED":
            return False
        previous = self._rows.get((payload.dept_id, payload.token_id))
        return previous is None or previous.status != "CALLED"

    def apply(self, payload: TokenUpdatePayload) -> DisplayRow:
        row = DisplayRow(
            dept_id=payload.dept_id, token_num=payload.token_num, status=payload.status
        )
        self._rows[(payload.dept_id, payload.token_id)] = row
        return row

    def rows_for_department(self, dept_id: int) -> list[DisplayRow]:
        return [row for (dept, _token_id), row in self._rows.items() if dept == dept_id]

    def all_rows(self) -> list[DisplayRow]:
        return list(self._rows.values())

    def apply_doctor(self, payload: DoctorStatusPayload) -> DoctorRow:
        row = DoctorRow(
            doctor_id=payload.doctor_id,
            name=payload.name,
            dept_id=payload.dept_id,
            status=payload.status,
        )
        self._doctors[payload.doctor_id] = row
        return row

    def doctors(self) -> list[DoctorRow]:
        """Every known doctor, by name."""
        return sorted(self._doctors.values(), key=lambda row: row.name)
