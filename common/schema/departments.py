"""Static reference data. Departments rarely change in the MVP and aren't
routed through sync_audit_log the way business-table mutations are -- seeded
directly here rather than via a repository.
"""

DDL = """
CREATE TABLE IF NOT EXISTS departments (
    dept_id INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

INSERT OR IGNORE INTO departments (dept_id, name) VALUES
    (1, 'General OPD'),
    (2, 'Pediatrics'),
    (3, 'Orthopedics');
"""
