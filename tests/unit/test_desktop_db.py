from desktop.data.db import connect, migrate


def test_connect_creates_db_file_in_wal_mode(tmp_path):
    db_path = tmp_path / "hms.db"
    conn = connect(db_path)
    try:
        assert db_path.exists()
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()


def test_migrate_creates_sync_audit_log_table(tmp_path):
    conn = connect(tmp_path / "hms.db")
    try:
        migrate(conn)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        }
        assert "sync_audit_log" in tables
    finally:
        conn.close()


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "hms.db")
    try:
        migrate(conn)
        migrate(conn)  # should not raise
    finally:
        conn.close()
