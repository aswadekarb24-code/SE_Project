import os

# Run Qt headless in tests/CI -- no X server required.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402 (must follow the QT_QPA_PLATFORM env var above)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from desktop.data.db import connect, migrate  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def db_conn(tmp_path):
    """A fresh, migrated local SQLite DB for each test."""
    conn = connect(tmp_path / "hms.db")
    migrate(conn)
    yield conn
    conn.close()
