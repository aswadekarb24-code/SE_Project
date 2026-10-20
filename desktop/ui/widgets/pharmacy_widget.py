"""Medicine stock table: search, low-stock flag, +/- buttons for single
units and "Receive" for a delivery of any size, on every row.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHeaderView, QInputDialog, QVBoxLayout, QWidget

from desktop.services.pharmacy_service import adjust_stock, search_stock
from desktop.ui.components import Badge, button, cell, empty_state, search_field, table, table_item

_NAME, _QUANTITY, _THRESHOLD, _STATUS, _ADJUST = range(5)


class PharmacyWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn

        self.search_input = search_field("Search medicine...")
        self.search_input.textChanged.connect(self.refresh)

        self.table = table(["Medicine", "In stock", "Low-stock at", "Status", "Adjust"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_NAME, QHeaderView.ResizeMode.Stretch)
        for column, width in ((_QUANTITY, 110), (_THRESHOLD, 130), (_STATUS, 130), (_ADJUST, 220)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.empty = empty_state("No medicines match", "Try a different search.", "pill")
        self.empty.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.search_input)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty, 1)

        self.refresh()

    def items(self) -> list[dict]:
        return [
            self.table.item(row, _NAME).data(Qt.ItemDataRole.UserRole)
            for row in range(self.table.rowCount())
        ]

    def refresh(self) -> None:
        scroll = self.table.verticalScrollBar().value()
        stock = search_stock(self._conn, self.search_input.text().strip())
        self.table.setRowCount(0)
        for row, item in enumerate(stock):
            self.table.insertRow(row)
            self.table.setItem(row, _NAME, table_item(item["name"], data=item))
            self.table.setItem(row, _QUANTITY, table_item(str(item["quantity"])))
            self.table.setItem(
                row, _THRESHOLD, table_item(str(item["low_stock_threshold"]), muted=True)
            )
            badge = (
                Badge("Low stock", "danger") if item["low_stock"] else Badge("In stock", "success")
            )
            self.table.setCellWidget(row, _STATUS, cell(badge))
            decrease = button("−")
            decrease.setObjectName("stepButton")
            decrease.setToolTip(f"Remove one {item['name']}")
            decrease.setEnabled(item["quantity"] > 0)
            decrease.clicked.connect(lambda _c, iid=item["item_id"]: self._adjust(iid, -1))
            increase = button("+")
            increase.setObjectName("stepButton")
            increase.setToolTip(f"Add one {item['name']}")
            increase.clicked.connect(lambda _c, iid=item["item_id"]: self._adjust(iid, 1))
            receive = button("Receive", "ghost")
            receive.setToolTip(f"Add a delivery of {item['name']}")
            receive.clicked.connect(lambda _c, it=item: self.receive(it))
            self.table.setCellWidget(row, _ADJUST, cell(decrease, increase, receive, spacing=8))
        self.table.setVisible(bool(stock))
        self.empty.setVisible(not stock)
        self.table.verticalScrollBar().setValue(scroll)

    def receive(self, item: dict) -> None:
        """Add a delivery: ask how many units arrived, then add them at once."""
        quantity, accepted = QInputDialog.getInt(
            self,
            "Receive stock",
            f"Units of {item['name']} received:",
            value=10,
            min=1,
            max=100_000,
        )
        if accepted:
            self._adjust(item["item_id"], quantity)

    def _adjust(self, item_id: str, delta: int) -> None:
        try:
            adjust_stock(self._conn, item_id, delta)
        except ValueError:
            return  # e.g. would go below zero -- nothing changes
        self.refresh()
        self.changed.emit()
