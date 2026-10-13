from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


def test_widget_lists_seeded_items(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)

    widget = PharmacyWidget(db_conn)
    assert widget.list_widget.count() == 1
    assert "Paracetamol" in widget.list_widget.item(0).text()


def test_low_stock_item_shows_warning_label(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(
        item_id="i1", name="Paracetamol", quantity=1, low_stock_threshold=10
    )

    widget = PharmacyWidget(db_conn)
    assert "[LOW STOCK]" in widget.list_widget.item(0).text()


def test_search_filters_the_list(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    PharmacyStockRepository(db_conn).insert(item_id="i2", name="Ibuprofen", quantity=5)

    widget = PharmacyWidget(db_conn)
    widget.search_input.setText("Ibu")

    assert widget.list_widget.count() == 1
    assert "Ibuprofen" in widget.list_widget.item(0).text()


def test_adjust_buttons_disabled_until_selection(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=5)
    widget = PharmacyWidget(db_conn)

    assert widget.increase_button.isEnabled() is False
    assert widget.decrease_button.isEnabled() is False


def test_decrease_at_zero_stock_does_not_crash_or_go_negative(qapp, db_conn):
    PharmacyStockRepository(db_conn).insert(item_id="i1", name="Paracetamol", quantity=0)
    widget = PharmacyWidget(db_conn)
    widget.list_widget.setCurrentRow(0)

    widget._adjust(-1)  # must be a safe no-op, not raise

    quantity = db_conn.execute(
        "SELECT quantity FROM pharmacy_stock WHERE item_id = 'i1'"
    ).fetchone()[0]
    assert quantity == 0
