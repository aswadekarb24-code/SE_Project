from desktop.data.repositories.beds_repo import BedsRepository
from desktop.sync.entity_registry import ENTITY_ROW_FETCHERS, overwrite_row


def test_fetcher_returns_full_row_for_known_entity(db_conn):
    BedsRepository(db_conn).insert(bed_id="b1", label="Bed 1")
    fetcher = ENTITY_ROW_FETCHERS["beds"]

    row = fetcher(db_conn, "b1")

    assert row["label"] == "Bed 1"
    assert row["status"] == "AVAILABLE"


def test_fetcher_returns_none_for_missing_record(db_conn):
    fetcher = ENTITY_ROW_FETCHERS["beds"]
    assert fetcher(db_conn, "does-not-exist") is None


def test_overwrite_row_applies_payload(db_conn):
    BedsRepository(db_conn).insert(bed_id="b1", label="Bed 1", status="AVAILABLE")

    overwrite_row(
        db_conn,
        "beds",
        "b1",
        {
            "bed_id": "b1",
            "label": "Bed 1",
            "status": "OCCUPIED",
            "created_at": "t",
            "updated_at": "t",
        },
    )

    status = db_conn.execute("SELECT status FROM beds WHERE bed_id = 'b1'").fetchone()[0]
    assert status == "OCCUPIED"


def test_overwrite_row_unknown_entity_is_a_no_op(db_conn):
    overwrite_row(db_conn, "not-a-table", "x", {"foo": "bar"})  # must not raise
