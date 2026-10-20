from pathlib import Path

import pytest

from desktop.data.seed import seed_default_data
from desktop.services import auth_service
from desktop.services.auth_service import (
    AuthError,
    RegistrationError,
    Role,
    authenticate,
    has_accounts,
    hash_password,
    register_user,
    verify_password,
)


def _register(conn, **overrides):
    fields = {
        "full_name": "Riya Desk",
        "username": "riya",
        "password": "front-desk-1",
        "role": Role.RECEPTIONIST,
    }
    fields.update(overrides)
    return register_user(conn, **fields)


def test_production_iteration_count_meets_owasp_minimum():
    # conftest lowers the module attribute for speed, so check the shipped default.
    source = Path(auth_service.__file__).read_text(encoding="utf-8")
    assert "PBKDF2_ITERATIONS = 600_000" in source


def test_hash_is_salted_and_verifies():
    first = hash_password("correct horse")
    second = hash_password("correct horse")

    assert first != second  # random salt per hash
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse", first)
    assert not verify_password("wrong horse", first)


def test_hash_keeps_its_own_iteration_count():
    stored = hash_password("pw-12345678", iterations=2_000)
    assert stored.split("$")[1] == "2000"
    assert verify_password("pw-12345678", stored)


@pytest.mark.parametrize("bad_hash", ["", "nonsense", "md5$1$a$b", "pbkdf2_sha256$x$!!$!!"])
def test_malformed_hash_never_verifies(bad_hash):
    assert verify_password("anything", bad_hash) is False


def test_password_is_never_stored_in_plain_text(db_conn):
    _register(db_conn)
    stored = db_conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "front-desk-1" not in stored


def test_register_and_authenticate_receptionist(db_conn):
    created = _register(db_conn)
    assert created.role == Role.RECEPTIONIST
    assert created.doctor_id is None

    user = authenticate(db_conn, "riya", "front-desk-1")
    assert user.user_id == created.user_id
    assert user.full_name == "Riya Desk"
    last_login = db_conn.execute("SELECT last_login_at FROM users").fetchone()[0]
    assert last_login is not None


def test_username_is_case_insensitive_for_login_and_uniqueness(db_conn):
    _register(db_conn, username="Riya")
    assert authenticate(db_conn, "RIYA", "front-desk-1").username == "Riya"
    with pytest.raises(RegistrationError, match="taken"):
        _register(db_conn, username="riya")


def test_doctor_account_creates_linked_doctor_record(db_conn):
    user = _register(db_conn, full_name="Meera Nair", username="meera", role=Role.DOCTOR, dept_id=2)

    doctor = db_conn.execute(
        "SELECT full_name, dept_id FROM doctors WHERE doctor_id = ?", (user.doctor_id,)
    ).fetchone()
    assert doctor == ("Dr. Meera Nair", 2)
    assert user.display_name == "Dr. Meera Nair"

    signed_in = authenticate(db_conn, "meera", "front-desk-1")
    assert signed_in.dept_id == 2
    assert signed_in.doctor_name == "Dr. Meera Nair"


def test_doctor_account_takes_over_matching_seeded_doctor(db_conn):
    seed_default_data(db_conn)  # seeds an account-less "Dr. Asha Rao" in dept 1
    seeded_id = db_conn.execute(
        "SELECT doctor_id FROM doctors WHERE full_name = 'Dr. Asha Rao'"
    ).fetchone()[0]
    doctors_before = db_conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]

    user = _register(db_conn, full_name="asha rao", username="asha", role=Role.DOCTOR, dept_id=1)

    assert user.doctor_id == seeded_id
    assert db_conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == doctors_before

    # Already claimed now, so a second account with that name gets its own record.
    other = _register(db_conn, full_name="Asha Rao", username="asha2", role=Role.DOCTOR, dept_id=1)
    assert other.doctor_id != seeded_id


def test_seeded_doctor_in_another_department_is_not_taken_over(db_conn):
    seed_default_data(db_conn)
    seeded_id = db_conn.execute(
        "SELECT doctor_id FROM doctors WHERE full_name = 'Dr. Asha Rao'"
    ).fetchone()[0]
    user = _register(db_conn, full_name="Asha Rao", role=Role.DOCTOR, dept_id=2)
    assert user.doctor_id != seeded_id


def test_doctor_name_already_titled_is_not_doubled(db_conn):
    user = _register(db_conn, full_name="Dr. Rohan Gupta", role=Role.DOCTOR, dept_id=3)
    assert user.doctor_name == "Dr. Rohan Gupta"


def test_doctor_needs_a_valid_department(db_conn):
    with pytest.raises(RegistrationError, match="department"):
        _register(db_conn, role=Role.DOCTOR, dept_id=None)
    with pytest.raises(RegistrationError, match="department"):
        _register(db_conn, role=Role.DOCTOR, dept_id=999)
    assert not has_accounts(db_conn)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"full_name": "   "}, "full name"),
        ({"username": "ab"}, "Username"),
        ({"username": "has space"}, "Username"),
        ({"password": "short"}, "at least 8"),
        ({"password": " leading-space"}, "spaces"),
        ({"password": "x" * 129}, "at most 128"),
    ],
)
def test_registration_validation(db_conn, overrides, message):
    with pytest.raises(RegistrationError, match=message):
        _register(db_conn, **overrides)
    assert not has_accounts(db_conn)


def test_wrong_password_and_unknown_user_get_the_same_error(db_conn):
    _register(db_conn)
    with pytest.raises(AuthError) as wrong_password:
        authenticate(db_conn, "riya", "not-the-password")
    with pytest.raises(AuthError) as unknown_user:
        authenticate(db_conn, "nobody", "front-desk-1")
    assert str(wrong_password.value) == str(unknown_user.value)


def test_failed_doctor_registration_leaves_no_orphan_doctor(db_conn, monkeypatch):
    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("desktop.data.repositories.users_repo.UsersRepository.insert", fail_insert)
    before = db_conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]

    with pytest.raises(RuntimeError):
        _register(db_conn, role=Role.DOCTOR, dept_id=1)

    after = db_conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    assert after == before


def test_accounts_are_never_queued_for_sync(db_conn):
    _register(db_conn)
    entities = {row[0] for row in db_conn.execute("SELECT entity_name FROM sync_audit_log")}
    assert "users" not in entities
