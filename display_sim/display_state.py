"""Pure tracking logic for the display simulator -- deliberately free of
Tkinter so it's unit-testable without a display/Xvfb. main.py wraps this in
actual widgets.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.broadcast_protocol import TokenUpdatePayload


@dataclass(frozen=True, slots=True)
class DisplayRow:
    dept_id: int
    token_num: int
    status: str

    @property
    def text(self) -> str:
        return f"Dept {self.dept_id} - Token #{self.token_num}: {self.status}"


class DisplayState:
    """Keeps the latest known status per token, keyed by (dept_id, token_id)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[int, str], DisplayRow] = {}

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
