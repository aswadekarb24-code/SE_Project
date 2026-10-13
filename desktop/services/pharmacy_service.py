"""Medicine stock search + quantity adjustment with low-stock detection."""

from __future__ import annotations

import sqlite3

from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository


def search_stock(conn: sqlite3.Connection, query: str = "") -> list[dict]:
    items = PharmacyStockRepository(conn).search(query)
    for item in items:
        item["low_stock"] = item["quantity"] <= item["low_stock_threshold"]
    return items


def adjust_stock(conn: sqlite3.Connection, item_id: str, delta: int) -> dict:
    """Raises ValueError (no mutation applied) if the item doesn't exist or
    the adjustment would take quantity below zero.
    """
    repo = PharmacyStockRepository(conn)
    conn.execute("BEGIN")
    try:
        new_quantity = repo.adjust_quantity(item_id, delta)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"item_id": item_id, "quantity": new_quantity}
