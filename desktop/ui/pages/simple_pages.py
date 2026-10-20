"""Pages that host one existing widget inside a card: beds, pharmacy,
doctor availability (doctors) and the read-only doctor list (reception).
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.auth_service import AuthenticatedUser
from desktop.services.pharmacy_service import search_stock
from desktop.ui.components import Badge, Card
from desktop.ui.pages.base import Page
from desktop.ui.widgets.bed_matrix_widget import BedMatrixWidget
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


def _single_card_layout(page: QWidget, card: Card) -> None:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(card, 1)


class BedsPage(Page):
    title = "Beds"
    subtitle = "Click a bed to cycle it: Available → Occupied → Maintenance."

    def __init__(self, conn: sqlite3.Connection, user: AuthenticatedUser) -> None:
        super().__init__()
        self.available = Badge("", "success")
        self.occupied = Badge("", "danger")
        self.maintenance = Badge("", "warning")
        summary = QWidget()
        row = QHBoxLayout(summary)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for badge in (self.available, self.occupied, self.maintenance):
            row.addWidget(badge)
        card = Card("Bed board", action=summary, padding=24, spacing=20)
        self.matrix = BedMatrixWidget(conn)
        self.matrix.changed.connect(self._update_summary)
        card.add(self.matrix, 1)
        _single_card_layout(self, card)

    def refresh(self) -> None:
        self.matrix.refresh()
        self._update_summary()

    def _update_summary(self) -> None:
        counts = self.matrix.counts()
        self.available.set(f"{counts['AVAILABLE']} available", "success")
        self.occupied.set(f"{counts['OCCUPIED']} occupied", "danger")
        self.maintenance.set(f"{counts['MAINTENANCE']} in maintenance", "warning")


class PharmacyPage(Page):
    title = "Pharmacy"
    subtitle = "Search stock, adjust quantities and receive deliveries."

    def __init__(self, conn: sqlite3.Connection, user: AuthenticatedUser) -> None:
        super().__init__()
        self.low_badge = Badge("", "danger")
        card = Card("Medicine stock", action=self.low_badge)
        self.stock = PharmacyWidget(conn)
        self.stock.changed.connect(self._update_badge)
        card.add(self.stock, 1)
        _single_card_layout(self, card)
        self._conn = conn

    def refresh(self) -> None:
        self.stock.refresh()
        self._update_badge()

    def focus_search(self) -> None:
        self.stock.search_input.setFocus()
        self.stock.search_input.selectAll()

    def _update_badge(self) -> None:
        low = sum(item["low_stock"] for item in search_stock(self._conn))
        self.low_badge.set(f"{low} low on stock", "danger" if low else "success")


class AvailabilityPage(Page):
    title = "Doctor availability"
    subtitle = "Set your status and OPD hours for the front desk."

    def __init__(
        self,
        conn: sqlite3.Connection,
        user: AuthenticatedUser,
        broadcaster: Broadcaster | None = None,
    ) -> None:
        super().__init__()
        card = Card("Doctors", padding=24)
        self.availability = DoctorAvailabilityWidget(
            conn, current_doctor_id=user.doctor_id, broadcaster=broadcaster
        )
        card.add(self.availability, 1)
        _single_card_layout(self, card)

    def refresh(self) -> None:
        self.availability.refresh()


class DoctorsPage(Page):
    """Reception's read-only view of who's available and their OPD hours."""

    title = "Doctors"
    subtitle = "Who's available right now, and each doctor's OPD hours."

    def __init__(self, conn: sqlite3.Connection, user: AuthenticatedUser) -> None:
        super().__init__()
        card = Card("Doctors", padding=24)
        self.availability = DoctorAvailabilityWidget(conn, read_only=True)
        card.add(self.availability, 1)
        _single_card_layout(self, card)

    def refresh(self) -> None:
        self.availability.refresh()
