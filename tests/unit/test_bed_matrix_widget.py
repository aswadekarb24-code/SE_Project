from desktop.data.repositories.beds_repo import BedsRepository
from desktop.ui.widgets.bed_matrix_widget import BedMatrixWidget


def test_widget_renders_one_button_per_bed(qapp, db_conn):
    BedsRepository(db_conn).insert(bed_id="b1", label="Bed 1")
    BedsRepository(db_conn).insert(bed_id="b2", label="Bed 2")

    widget = BedMatrixWidget(db_conn)
    assert len(widget._buttons) == 2
    assert widget._buttons["b1"].text() == "Bed 1\nAVAILABLE"


def test_clicking_a_bed_button_toggles_its_status(qapp, db_conn):
    BedsRepository(db_conn).insert(bed_id="b1", label="Bed 1")
    widget = BedMatrixWidget(db_conn)

    widget._on_toggle("b1")

    assert widget._buttons["b1"].text() == "Bed 1\nOCCUPIED"


def test_double_click_cycles_through_both_steps(qapp, db_conn):
    BedsRepository(db_conn).insert(bed_id="b1", label="Bed 1")
    widget = BedMatrixWidget(db_conn)

    widget._on_toggle("b1")
    widget._on_toggle("b1")

    assert widget._buttons["b1"].text() == "Bed 1\nMAINTENANCE"
