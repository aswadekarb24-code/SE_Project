"""Date input that can be typed or picked from a calendar.

The field stays a plain text box holding YYYY-MM-DD, so typing (and the
services' validation) work exactly as before. A calendar button inside the
field, or Alt+Down, opens a small calendar popup; clicking a day fills the
field in. The popup's allowed range matches what the field accepts (e.g. no
future dates of birth, no past follow-ups).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, QPoint, QSize, Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence, QShortcut, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from common import design_tokens as tokens
from common.clock import local_today
from desktop.ui import icons
from desktop.ui.components import button


def to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def to_date(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def styled_calendar(
    *, minimum: date | None = None, maximum: date | None = None, parent: QWidget | None = None
) -> QCalendarWidget:
    """A QCalendarWidget set up to match the theme: Monday first, no week
    numbers, themed month arrows, and weekends in the normal text colour.
    """
    calendar = QCalendarWidget(parent)
    calendar.setGridVisible(False)
    calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    if minimum is not None:
        calendar.setMinimumDate(to_qdate(minimum))
    if maximum is not None:
        calendar.setMaximumDate(to_qdate(maximum))
    # Month arrows as theme icons (Fusion's default arrows vanish under the stylesheet).
    for name, icon_name in (
        ("qt_calendar_prevmonth", "chevron-left"),
        ("qt_calendar_nextmonth", "chevron-right"),
    ):
        arrow = calendar.findChild(QToolButton, name)
        if arrow is not None:
            arrow.setIcon(icons.icon(icon_name, tokens.TEXT_PRIMARY, size=18))
            arrow.setIconSize(QSize(18, 18))
    plain = QTextCharFormat()
    plain.setForeground(QColor(tokens.TEXT_PRIMARY))
    for weekend in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(weekend, plain)
    return calendar


class CalendarPopup(QFrame):
    """Small calendar under a DateField, with Today and Clear shortcuts."""

    def __init__(self, field: DateField) -> None:
        super().__init__(field, Qt.WindowType.Popup)
        self.setObjectName("calendarPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._field = field

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.calendar = styled_calendar(minimum=field.minimum, maximum=field.maximum)
        self.calendar.setFixedSize(300, 260)
        current = field.date_value()
        start = current or field.default or local_today()
        self.calendar.setSelectedDate(to_qdate(start))
        self.calendar.clicked.connect(self._choose)
        self.calendar.activated.connect(self._choose)  # Enter on a highlighted day
        layout.addWidget(self.calendar)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.today_button = button("Today", "ghost")
        today = local_today()
        self.today_button.setEnabled(field.allows(today))
        self.today_button.clicked.connect(lambda: self._choose(to_qdate(local_today())))
        self.clear_button = button("Clear", "ghost")
        self.clear_button.clicked.connect(self._clear)
        footer.addWidget(self.today_button)
        footer.addStretch(1)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)

    def _choose(self, value: QDate) -> None:
        self._field.setText(to_date(value).isoformat())
        self._field.setFocus()
        self.close()

    def _clear(self) -> None:
        self._field.clear()
        self._field.setFocus()
        self.close()


class DateField(QLineEdit):
    """YYYY-MM-DD text field with a calendar popup (button or Alt+Down)."""

    def __init__(
        self,
        placeholder: str = "YYYY-MM-DD",
        *,
        minimum: date | None = None,
        maximum: date | None = None,
        default: date | None = None,
    ) -> None:
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.minimum = minimum
        self.maximum = maximum
        self.default = default
        self.popup: CalendarPopup | None = None
        self.calendar_action = QAction(icons.icon("calendar-check", size=16), "Pick a date", self)
        self.calendar_action.setToolTip("Pick from a calendar (Alt+Down)")
        self.calendar_action.triggered.connect(self.open_calendar)
        self.addAction(self.calendar_action, QLineEdit.ActionPosition.TrailingPosition)
        QShortcut(
            QKeySequence("Alt+Down"),
            self,
            activated=self.open_calendar,
            context=Qt.ShortcutContext.WidgetShortcut,
        )

    def date_value(self) -> date | None:
        """The typed date, or None if the text isn't a valid YYYY-MM-DD date."""
        try:
            value = date.fromisoformat(self.text().strip())
        except ValueError:
            return None
        return value if len(self.text().strip()) == 10 else None

    def allows(self, value: date) -> bool:
        return (self.minimum is None or value >= self.minimum) and (
            self.maximum is None or value <= self.maximum
        )

    def open_calendar(self) -> None:
        self.popup = CalendarPopup(self)
        self.popup.adjustSize()
        # Below the field, nudged back on screen if it would overflow.
        position = self.mapToGlobal(QPoint(0, self.height() + 4))
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            size = self.popup.sizeHint()
            if position.y() + size.height() > area.bottom():
                position.setY(self.mapToGlobal(QPoint(0, 0)).y() - size.height() - 4)
            position.setX(min(position.x(), area.right() - size.width()))
        self.popup.move(position)
        self.popup.show()
        self.popup.calendar.setFocus()
