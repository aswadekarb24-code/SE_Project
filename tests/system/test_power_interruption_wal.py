"""Simulates the SQA plan's power-interruption scenario: a transaction that
never commits (process dies mid-write) must leave no partial state behind
when the DB is reopened -- the standard guarantee WAL mode is relied on for.
"""

from desktop.data.db import connect, migrate


def test_uncommitted_transaction_leaves_no_partial_patient_row(tmp_path):
    db_path = tmp_path / "hms.db"
    conn = connect(db_path)
    migrate(conn)

    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO patients (patient_id, full_name, dob, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", "Jane Doe", "1990-01-01", "t", "t"),
    )
    conn.close()  # simulated crash: no COMMIT, no ROLLBACK

    reopened = connect(db_path)
    try:
        row = reopened.execute("SELECT 1 FROM patients WHERE patient_id = 'p1'").fetchone()
        assert row is None
    finally:
        reopened.close()


def test_uncommitted_transaction_leaves_no_orphaned_token(tmp_path):
    """A crash between the patient insert and the token insert (both inside
    issue_queue_token's single transaction) must not leave a queue_tokens row
    whose patient never made it to disk.
    """
    db_path = tmp_path / "hms.db"
    conn = connect(db_path)
    migrate(conn)

    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO patients (patient_id, full_name, dob, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", "Jane Doe", "1990-01-01", "t", "t"),
    )
    conn.execute(
        "INSERT INTO queue_tokens "
        "(token_id, patient_id, dept_id, token_num, status, issued_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("tok1", "p1", 1, 1, "WAITING", "2026-01-01", "t", "t"),
    )
    conn.close()  # simulated crash before COMMIT

    reopened = connect(db_path)
    try:
        patients = reopened.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        tokens = reopened.execute("SELECT COUNT(*) FROM queue_tokens").fetchone()[0]
        assert (patients, tokens) == (0, 0)
    finally:
        reopened.close()
