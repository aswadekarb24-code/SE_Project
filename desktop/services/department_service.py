"""Read-only department lookup. Departments are static reference data seeded
directly via DDL (common/schema/departments.py), not routed through the
sync_audit_log pipeline the way business-table mutations are.
"""

from __future__ import annotations

import sqlite3


def list_departments(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    rows = conn.execute("SELECT dept_id, name FROM departments ORDER BY dept_id").fetchall()
    return [(row[0], row[1]) for row in rows]
