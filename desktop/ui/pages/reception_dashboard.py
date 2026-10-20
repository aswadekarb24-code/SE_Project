"""Front-desk overview: today's numbers, the live queue and quick actions."""

from __future__ import annotations

import sqlite3

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QHeaderView, QStackedWidget, QVBoxLayout

from desktop.services.auth_service import AuthenticatedUser
from desktop.services.dashboard_service import reception_summary, todays_queue
from desktop.ui.components import (
    Badge,
    Card,
    IconTile,
    StatCard,
    button,
    cell,
    empty_state,
    label,
    person_cell,
    table,
    table_item,
)
from desktop.ui.pages.base import Page


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class ReceptionDashboard(Page):
    title = "Dashboard"

    def __init__(self, conn: sqlite3.Connection, user: AuthenticatedUser) -> None:
        super().__init__()
        self._conn = conn
        self.subtitle = f"Welcome back, {user.first_name}! Here's today at the front desk."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        self.patients_stat = StatCard("Total patients", "users", "info")
        self.waiting_stat = StatCard("Waiting now", "clock", "warning")
        self.beds_stat = StatCard("Beds available", "bed", "success")
        self.stock_stat = StatCard("Low-stock medicines", "pill", "danger")
        stats = QHBoxLayout()
        stats.setSpacing(16)
        for stat in (self.patients_stat, self.waiting_stat, self.beds_stat, self.stock_stat):
            stats.addWidget(stat)
        layout.addLayout(stats)

        lower = QHBoxLayout()
        lower.setSpacing(20)

        check_in = button("Check in patient", "ghost", "plus")
        check_in.clicked.connect(lambda: self.navigate.emit("check_in", None))
        queue_card = Card("Today's queue", action=check_in)
        self.queue_table = table(["Token", "Patient", "Department", "Status"], row_height=56)
        header = self.queue_table.horizontalHeader()
        for column, width in ((0, 80), (2, 150), (3, 140)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.queue_table.setColumnWidth(column, width)
        self.queue_stack = QStackedWidget()
        self.queue_stack.addWidget(self.queue_table)
        self.queue_stack.addWidget(
            empty_state("No patients in the queue yet", "Checked-in patients appear here.", "clock")
        )
        queue_card.add(self.queue_stack, 1)
        lower.addWidget(queue_card, 3)

        actions_card = Card("Quick actions")
        self.action_details: dict[str, object] = {}
        for key, icon_name, tone, title, action_text in (
            ("check_in", "user-plus", "info", "Register a new patient", "Add"),
            ("patients", "users", "lavender", "Find a patient", "Open"),
            ("beds", "bed", "success", "Bed board", "Open"),
            ("pharmacy", "pill", "danger", "Pharmacy stock", "Open"),
        ):
            row = QFrame()
            row.setObjectName("actionRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(12)
            row_layout.addWidget(IconTile(icon_name, tone, 36))
            text = QVBoxLayout()
            text.setSpacing(1)
            text.addWidget(label(title, "cellTitle"))
            detail = label("", "muted")
            text.addWidget(detail)
            self.action_details[key] = detail
            row_layout.addLayout(text, 1)
            go = button(action_text)
            go.setObjectName("pillButton")
            go.clicked.connect(lambda _c, k=key: self.navigate.emit(k, None))
            row_layout.addWidget(go)
            actions_card.add(row)
        actions_card.body.addStretch(1)
        lower.addWidget(actions_card, 2)
        layout.addLayout(lower, 1)

    def refresh(self) -> None:
        summary = reception_summary(self._conn)
        self.patients_stat.set(
            summary["total_patients"], f"{summary['registered_today']} registered today"
        )
        self.waiting_stat.set(
            summary["waiting"],
            f"{summary['in_consultation']} with a doctor · {summary['seen_today']} seen today",
        )
        self.beds_stat.set(summary["beds_available"], f"of {summary['beds_total']} beds")
        self.stock_stat.set(
            summary["low_stock"], f"of {summary['stock_items']} items need restocking"
        )
        self.action_details["check_in"].setText("Create a record and issue a token")
        self.action_details["patients"].setText("History by patient no., name or phone")
        self.action_details["beds"].setText(
            f"{summary['beds_available']} of {summary['beds_total']} beds free"
        )
        self.action_details["pharmacy"].setText(
            f"{_plural(summary['low_stock'], 'item')} running low"
        )

        queue = todays_queue(self._conn)
        self.queue_table.setRowCount(0)
        for row, token in enumerate(queue):
            self.queue_table.insertRow(row)
            self.queue_table.setItem(row, 0, table_item(f"#{token['token_num']}"))
            self.queue_table.setCellWidget(
                row, 1, person_cell(token["full_name"], token["patient_number"])
            )
            self.queue_table.setItem(row, 2, table_item(token["dept_name"], muted=True))
            self.queue_table.setCellWidget(row, 3, cell(Badge.for_status(token["status"])))
        self.queue_stack.setCurrentIndex(0 if queue else 1)
