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


@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch):
    """Real hashing (600k PBKDF2 iterations) costs ~0.4s per call, which adds
    up across the suite. Tests use a cheap count instead; the production
    default is asserted separately in test_auth_service.py.
    """
    monkeypatch.setattr("desktop.services.auth_service.PBKDF2_ITERATIONS", 1_000)


@pytest.fixture
def receptionist(db_conn):
    from desktop.services.auth_service import Role, register_user

    return register_user(
        db_conn,
        full_name="Riya Desk",
        username="riya",
        password="front-desk-1",
        role=Role.RECEPTIONIST,
    )


@pytest.fixture
def doctor(db_conn):
    from desktop.services.auth_service import Role, register_user

    return register_user(
        db_conn,
        full_name="Asha Rao",
        username="asha",
        password="consult-room-1",
        role=Role.DOCTOR,
        dept_id=1,
    )
