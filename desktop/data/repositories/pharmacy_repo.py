from __future__ import annotations

import sqlite3

from common.clock import now_iso
from desktop.data.repositories.sync_audit_log_repo import log_mutation


class PharmacyStockRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search(self, query: str = "") -> list[dict]:
        rows = self._conn.execute(
            """SELECT item_id, name, quantity, low_stock_threshold FROM pharmacy_stock
               WHERE name LIKE ? ORDER BY name""",
            (f"%{query}%",),
        ).fetchall()
        return [
            {"item_id": r[0], "name": r[1], "quantity": r[2], "low_stock_threshold": r[3]}
            for r in rows
        ]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM pharmacy_stock").fetchone()[0]

    def insert(
        self, *, item_id: str, name: str, quantity: int, low_stock_threshold: int = 10
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO pharmacy_stock
               (item_id, name, quantity, low_stock_threshold, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item_id, name, quantity, low_stock_threshold, timestamp, timestamp),
        )
        log_mutation(
            self._conn, entity_name="pharmacy_stock", record_id=item_id, action_type="INSERT"
        )

    def adjust_quantity(self, item_id: str, delta: int) -> int:
        row = self._conn.execute(
            "SELECT quantity FROM pharmacy_stock WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"pharmacy item {item_id} does not exist")

        new_quantity = row[0] + delta
        if new_quantity < 0:
            raise ValueError("stock quantity cannot go negative")

        timestamp = now_iso()
        self._conn.execute(
            "UPDATE pharmacy_stock SET quantity = ?, updated_at = ? WHERE item_id = ?",
            (new_quantity, timestamp, item_id),
        )
        log_mutation(
            self._conn, entity_name="pharmacy_stock", record_id=item_id, action_type="UPDATE"
        )
        return new_quantity
