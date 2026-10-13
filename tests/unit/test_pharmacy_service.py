import pytest

from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.services.pharmacy_service import adjust_stock, search_stock


def _seed_item(db_conn, item_id="item-1", name="Paracetamol", quantity=5, threshold=10):
    PharmacyStockRepository(db_conn).insert(
        item_id=item_id, name=name, quantity=quantity, low_stock_threshold=threshold
    )


def test_search_with_empty_query_returns_all(db_conn):
    _seed_item(db_conn, "a", "Paracetamol")
    _seed_item(db_conn, "b", "Ibuprofen")
    assert len(search_stock(db_conn, "")) == 2


def test_search_filters_by_substring_case_sensitivity_aside(db_conn):
    _seed_item(db_conn, "a", "Paracetamol")
    _seed_item(db_conn, "b", "Ibuprofen")
    results = search_stock(db_conn, "Para")
    assert [item["name"] for item in results] == ["Paracetamol"]


def test_search_marks_low_stock_at_threshold_boundary(db_conn):
    _seed_item(db_conn, "a", "At threshold", quantity=10, threshold=10)
    _seed_item(db_conn, "b", "Above threshold", quantity=11, threshold=10)
    _seed_item(db_conn, "c", "Zero stock", quantity=0, threshold=10)

    results = {item["name"]: item["low_stock"] for item in search_stock(db_conn)}
    assert results["At threshold"] is True  # <=, boundary counts as low
    assert results["Above threshold"] is False
    assert results["Zero stock"] is True


def test_adjust_stock_increases_quantity(db_conn):
    _seed_item(db_conn, quantity=5)
    result = adjust_stock(db_conn, "item-1", 3)
    assert result["quantity"] == 8


def test_adjust_stock_decreases_quantity(db_conn):
    _seed_item(db_conn, quantity=5)
    result = adjust_stock(db_conn, "item-1", -3)
    assert result["quantity"] == 2


def test_adjust_stock_cannot_go_below_zero(db_conn):
    _seed_item(db_conn, quantity=0)
    with pytest.raises(ValueError):
        adjust_stock(db_conn, "item-1", -1)

    # no partial mutation happened
    quantity = db_conn.execute(
        "SELECT quantity FROM pharmacy_stock WHERE item_id = 'item-1'"
    ).fetchone()[0]
    assert quantity == 0


def test_adjust_stock_unknown_item_raises(db_conn):
    with pytest.raises(ValueError):
        adjust_stock(db_conn, "does-not-exist", 1)


def test_adjust_stock_writes_sync_audit_log_update_row(db_conn):
    _seed_item(db_conn, quantity=5)
    adjust_stock(db_conn, "item-1", 1)

    row = db_conn.execute(
        "SELECT action_type, sync_status FROM sync_audit_log "
        "WHERE entity_name = 'pharmacy_stock' AND record_id = 'item-1' "
        "ORDER BY sync_id DESC LIMIT 1"
    ).fetchone()
    assert row == ("UPDATE", "PENDING")
