import pytest

from desktop.data.repositories.beds_repo import BedsRepository
from desktop.services.bed_service import list_beds, toggle_bed


def _seed_one_bed(db_conn, bed_id="bed-1", status="AVAILABLE"):
    BedsRepository(db_conn).insert(bed_id=bed_id, label="Bed 1", status=status)


def test_list_beds_returns_seeded_beds(db_conn):
    _seed_one_bed(db_conn)
    beds = list_beds(db_conn)
    assert len(beds) == 1
    assert beds[0]["label"] == "Bed 1"


def test_toggle_cycles_available_to_occupied(db_conn):
    _seed_one_bed(db_conn, status="AVAILABLE")
    result = toggle_bed(db_conn, "bed-1")
    assert result["status"] == "OCCUPIED"


def test_toggle_cycles_full_rotation(db_conn):
    _seed_one_bed(db_conn, status="AVAILABLE")
    first = toggle_bed(db_conn, "bed-1")
    second = toggle_bed(db_conn, "bed-1")
    third = toggle_bed(db_conn, "bed-1")

    assert [first["status"], second["status"], third["status"]] == [
        "OCCUPIED",
        "MAINTENANCE",
        "AVAILABLE",
    ]


def test_toggle_unknown_bed_raises(db_conn):
    with pytest.raises(ValueError):
        toggle_bed(db_conn, "does-not-exist")


def test_toggle_writes_sync_audit_log_update_row(db_conn):
    _seed_one_bed(db_conn)
    toggle_bed(db_conn, "bed-1")

    row = db_conn.execute(
        "SELECT action_type, sync_status FROM sync_audit_log "
        "WHERE entity_name = 'beds' AND record_id = 'bed-1' ORDER BY sync_id DESC LIMIT 1"
    ).fetchone()
    assert row == ("UPDATE", "PENDING")


def test_double_toggle_is_consistent_not_a_crash(db_conn):
    """Rapid double-clicking a bed button must not error -- each toggle is
    simply the next step in the cycle, never an invalid transition.
    """
    _seed_one_bed(db_conn, status="AVAILABLE")
    toggle_bed(db_conn, "bed-1")
    result = toggle_bed(db_conn, "bed-1")
    assert result["status"] == "MAINTENANCE"
