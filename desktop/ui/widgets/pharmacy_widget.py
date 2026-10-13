"""Medicine stock search with low-stock warning + quantity adjustment."""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.services.pharmacy_service import adjust_stock, search_stock


class PharmacyWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search medicine...")
        self.search_input.textChanged.connect(self.refresh)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)

        self.increase_button = QPushButton("+1")
        self.increase_button.clicked.connect(lambda: self._adjust(1))
        self.decrease_button = QPushButton("-1")
        self.decrease_button.clicked.connect(lambda: self._adjust(-1))
        self.increase_button.setEnabled(False)
        self.decrease_button.setEnabled(False)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.decrease_button)
        buttons_row.addWidget(self.increase_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons_row)

        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for item in search_stock(self._conn, self.search_input.text().strip()):
            label = f"{item['name']} -- qty {item['quantity']}"
            if item["low_stock"]:
                label += "  [LOW STOCK]"
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.ItemDataRole.UserRole, item["item_id"])
            self.list_widget.addItem(list_item)
        self.increase_button.setEnabled(False)
        self.decrease_button.setEnabled(False)

    def _on_selection_changed(self, current, _previous) -> None:
        enabled = current is not None
        self.increase_button.setEnabled(enabled)
        self.decrease_button.setEnabled(enabled)

    def _adjust(self, delta: int) -> None:
        current = self.list_widget.currentItem()
        if current is None:
            return
        item_id = current.data(Qt.ItemDataRole.UserRole)
        try:
            adjust_stock(self._conn, item_id, delta)
        except ValueError:
            pass  # e.g. tried to go below zero -- ignore, UI just stays as-is
        self.refresh()
