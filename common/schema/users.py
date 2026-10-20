"""DDL for users: staff login accounts (receptionists and doctors).

Passwords are stored only as salted PBKDF2-SHA256 hashes (see
desktop/services/auth_service.py). Accounts are local to this station and
deliberately not routed through sync_audit_log: credential hashes never
leave the device. A doctor account links to its doctors row, so the
doctor shows up in availability and authors reports under that identity.
"""

DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name      TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('RECEPTIONIST', 'DOCTOR')),
    doctor_id      TEXT REFERENCES doctors(doctor_id),
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    last_login_at  TEXT,
    CHECK ((role = 'DOCTOR') = (doctor_id IS NOT NULL))
);
"""
