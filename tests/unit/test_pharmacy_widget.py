from PyQt6.QtCore import Qt

from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


def _status_text(widget, row):
    badge = widget.table.cellWidget(row, 3).layout().itemAt(0).widget()
    return badge.text()


def test_widget_lists_seeded_items(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)

    widget = PharmacyWidget(db_conn)
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Paracetamol"
    assert widget.table.item(0, 1).text() == "5"


def test_low_stock_item_is_flagged(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(
        item_id="i1", name="Paracetamol", quantity=1, low_stock_threshold=10
    )
    PharmacyStockRepository(db_conn).insert(item_id="i2", name="Ibuprofen", quantity=50)

    widget = PharmacyWidget(db_conn)
    assert _status_text(widget, 0) == "In stock"  # Ibuprofen sorts first
    assert _status_text(widget, 1) == "Low stock"


def test_search_filters_the_list(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    PharmacyStockRepository(db_conn).insert(item_id="i2", name="Ibuprofen", quantity=5)

    widget = PharmacyWidget(db_conn)
    widget.search_input.setText("Ibu")

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 0).text() == "Ibuprofen"


def test_no_match_shows_empty_state(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    widget = PharmacyWidget(db_conn)
    widget.search_input.setText("zzz")
    assert widget.table.isHidden()
    assert not widget.empty.isHidden()


def test_plus_and_minus_buttons_adjust_that_row(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    widget = PharmacyWidget(db_conn)
    changes = []
    widget.changed.connect(lambda: changes.append(True))

    increase = widget.table.cellWidget(0, 4).layout().itemAt(1).widget()
    increase.click()

    assert widget.table.item(0, 1).text() == "6"
    assert widget.items()[0]["quantity"] == 6
    assert changes == [True]


def test_minus_is_disabled_at_zero_and_stock_never_goes_negative(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=0)
    widget = PharmacyWidget(db_conn)

    decrease = widget.table.cellWidget(0, 4).layout().itemAt(0).widget()
    assert decrease.isEnabled() is False
    widget._adjust("i1", -1)  # must be a safe no-op, not raise

    quantity = db_conn.execute(
        "SELECT quantity FROM pharmacy_stock WHERE item_id = 'i1'"
    ).fetchone()[0]
    assert quantity == 0
    assert widget.table.item(0, 0).data(Qt.ItemDataRole.UserRole)["quantity"] == 0
