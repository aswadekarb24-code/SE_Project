"""Staff accounts: sign-up, sign-in, and the role each account works as.

The role a user signs in with decides which screens they get -- this is
still UI-level gating on a single station, matching the MVP's dual-role
interface (Receptionist: intake/queue; Doctor: consultations/records), but
now behind real per-person accounts instead of a role picker.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib, no extra dependency)
using a random 16-byte salt per password and OWASP's recommended iteration
count. The iteration count is stored inside each hash, so it can be raised
later without breaking existing accounts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.repositories.users_repo import UsersRepository


class Role(str, Enum):
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"

    @property
    def label(self) -> str:
        return self.value.title()


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The signed-in user. doctor_id/dept_id are set only for doctors."""

    user_id: str
    username: str
    full_name: str
    role: Role
    doctor_id: str | None = None
    doctor_name: str | None = None
    dept_id: int | None = None

    @property
    def display_name(self) -> str:
        return self.doctor_name or self.full_name

    @property
    def first_name(self) -> str:
        return self.full_name.split()[0]


class AuthError(ValueError):
    """Wrong username or password. Deliberately doesn't say which."""


class RegistrationError(ValueError):
    """Sign-up input that can't be accepted; the message is user-facing."""


PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
_ALGORITHM = "pbkdf2_sha256"

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_NAME_LENGTH = 80


def hash_password(password: str, *, iterations: int | None = None) -> str:
    iterations = iterations or PBKDF2_ITERATIONS
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{_ALGORITHM}${iterations}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except ValueError:  # malformed hash (includes binascii.Error)
        return False
    return hmac.compare_digest(digest, expected)


_dummy_hash: str | None = None


def _burn_equal_time(password: str) -> None:
    """Spend the same time verifying as for a real account, so response time
    doesn't reveal whether a username exists.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_hex(16))
    verify_password(password, _dummy_hash)


def doctor_display_name(full_name: str) -> str:
    """ "Asha Rao" -> "Dr. Asha Rao"; names already titled are kept as is."""
    if re.match(r"(?i)^dr\.?\s", full_name):
        return full_name
    return f"Dr. {full_name}"


def _unclaimed_doctor_id(conn: sqlite3.Connection, doctor_name: str, dept_id: int) -> str | None:
    """A doctors row with this name in this department that no account is
    linked to yet (e.g. seeded before the doctor signed up). The new account
    takes it over instead of creating a duplicate doctor.
    """
    row = conn.execute(
        """SELECT doctor_id FROM doctors
           WHERE full_name = ? COLLATE NOCASE AND dept_id = ?
             AND doctor_id NOT IN (SELECT doctor_id FROM users WHERE doctor_id IS NOT NULL)
           ORDER BY created_at LIMIT 1""",
        (doctor_name, dept_id),
    ).fetchone()
    return row[0] if row else None


def register_user(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    username: str,
    password: str,
    role: Role,
    dept_id: int | None = None,
) -> AuthenticatedUser:
    """Create an account. A doctor account is linked to a doctors row in
    `dept_id`: an unclaimed one with the same name if it exists, otherwise
    a new one. Raises RegistrationError on invalid input or a taken
    username; nothing is written in that case.
    """
    full_name = " ".join(full_name.split())
    username = username.strip()
    if not full_name:
        raise RegistrationError("Enter your full name.")
    if len(full_name) > MAX_NAME_LENGTH:
        raise RegistrationError(f"Full name can be at most {MAX_NAME_LENGTH} characters.")
    if not USERNAME_PATTERN.match(username):
        raise RegistrationError(
            "Username must be 3-32 characters: letters, numbers, dots, dashes or underscores."
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RegistrationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise RegistrationError(f"Password can be at most {MAX_PASSWORD_LENGTH} characters.")
    if password.strip() != password or not password.strip():
        raise RegistrationError("Password can't start or end with spaces.")
    role = Role(role)
    if role == Role.DOCTOR:
        known_depts = {row[0] for row in conn.execute("SELECT dept_id FROM departments")}
        if dept_id not in known_depts:
            raise RegistrationError("Choose your department.")

    users = UsersRepository(conn)
    if users.get_by_username(username) is not None:
        raise RegistrationError("That username is taken. Try another.")

    password_hash = hash_password(password)  # slow on purpose; keep it outside the transaction
    user_id = str(uuid4())
    doctor_id = doctor_name = None

    conn.execute("BEGIN")
    try:
        if role == Role.DOCTOR:
            doctor_name = doctor_display_name(full_name)
            doctor_id = _unclaimed_doctor_id(conn, doctor_name, dept_id)
            if doctor_id is None:
                doctor_id = str(uuid4())
                DoctorsRepository(conn).insert(
                    doctor_id=doctor_id, full_name=doctor_name, dept_id=dept_id
                )
        users.insert(
            user_id=user_id,
            username=username,
            full_name=full_name,
            role=role.value,
            password_hash=password_hash,
            doctor_id=doctor_id,
        )
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        # Lost a race with another sign-up for the same username.
        raise RegistrationError("That username is taken. Try another.") from None
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return AuthenticatedUser(
        user_id=user_id,
        username=username,
        full_name=full_name,
        role=role,
        doctor_id=doctor_id,
        doctor_name=doctor_name,
        dept_id=dept_id if role == Role.DOCTOR else None,
    )


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> AuthenticatedUser:
    """Raises AuthError for an unknown username or wrong password alike."""
    users = UsersRepository(conn)
    row = users.get_by_username(username.strip())
    if row is None:
        _burn_equal_time(password)
        raise AuthError("Incorrect username or password.")
    if not verify_password(password, row["password_hash"]):
        raise AuthError("Incorrect username or password.")

    users.record_login(row["user_id"])
    doctor = DoctorsRepository(conn).get(row["doctor_id"]) if row["doctor_id"] else None
    return AuthenticatedUser(
        user_id=row["user_id"],
        username=row["username"],
        full_name=row["full_name"],
        role=Role(row["role"]),
        doctor_id=row["doctor_id"],
        doctor_name=doctor["full_name"] if doctor else None,
        dept_id=doctor["dept_id"] if doctor else None,
    )


def has_accounts(conn: sqlite3.Connection) -> bool:
    return UsersRepository(conn).count() > 0
