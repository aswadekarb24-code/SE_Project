"""Verifies NFR-02 (local SQLite encrypted at rest): the DB file is actually
SQLCipher-encrypted, not just opened through a different driver that still
writes plaintext SQLite pages.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlcipher3 import dbapi2 as sqlcipher

from desktop.data.db import connect, migrate


def test_encrypted_db_file_is_unreadable_by_plain_sqlite3(tmp_path):
    db_path = tmp_path / "hms.db"
    conn = connect(db_path, encryption_key="test-key-1")
    migrate(conn)
    conn.execute(
        "INSERT INTO patients (patient_id, full_name, dob, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", "Jane Doe", "1990-01-01", "t", "t"),
    )
    conn.close()

    # Plain stdlib sqlite3 has no concept of SQLCipher's key -- an encrypted
    # file isn't valid SQLite to it at all.
    plain_conn = sqlite3.connect(str(db_path))
    with pytest.raises(sqlite3.DatabaseError):
        plain_conn.execute("SELECT * FROM patients").fetchall()
    plain_conn.close()


def test_reopening_with_correct_key_reads_data_back(tmp_path):
    db_path = tmp_path / "hms.db"
    conn = connect(db_path, encryption_key="test-key-2")
    migrate(conn)
    conn.execute(
        "INSERT INTO patients (patient_id, full_name, dob, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p1", "Jane Doe", "1990-01-01", "t", "t"),
    )
    conn.close()

    reopened = connect(db_path, encryption_key="test-key-2")
    row = reopened.execute("SELECT full_name FROM patients WHERE patient_id = 'p1'").fetchone()
    assert row == ("Jane Doe",)
    reopened.close()


def test_reopening_with_wrong_key_fails(tmp_path):
    db_path = tmp_path / "hms.db"
    conn = connect(db_path, encryption_key="correct-key")
    migrate(conn)
    conn.close()

    wrong_key_conn = sqlcipher.connect(str(db_path), isolation_level=None)
    wrong_key_conn.execute("PRAGMA key = 'wrong-key';")
    with pytest.raises(sqlcipher.DatabaseError):
        wrong_key_conn.execute("SELECT * FROM patients").fetchall()
    wrong_key_conn.close()


def test_connect_falls_back_to_dev_default_key_when_unset(tmp_path, monkeypatch):
    """connect() must still work with zero configuration (the insecure dev
    default), since most tests/dev runs never set HMS_DB_ENCRYPTION_KEY.
    """
    monkeypatch.delenv("HMS_DB_ENCRYPTION_KEY", raising=False)
    conn = connect(tmp_path / "hms.db")
    migrate(conn)  # must not raise
    conn.close()
