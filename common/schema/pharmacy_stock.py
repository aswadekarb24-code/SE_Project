"""DDL for pharmacy_stock: a core medicine stock ledger (~20 essential
items per the MVP scope -- no batch/expiry/purchase-order complexity).
"""

DDL = """
CREATE TABLE IF NOT EXISTS pharmacy_stock (
    item_id             TEXT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    quantity            INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 10,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pharmacy_stock_name
    ON pharmacy_stock (name);
"""
