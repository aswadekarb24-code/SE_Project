"""One-time MVP seed data for beds/pharmacy_stock/doctors -- idempotent (each
section checks its own table is empty before inserting), run once at startup.

Unlike departments (static reference data seeded directly in DDL), these are
real business rows and do flow through sync_audit_log like any other write,
since bed/stock/doctor-status changes are exactly the kind of state Cycle 4's
sync worker needs to know about.
"""

from __future__ import annotations

import sqlite3
from uuid import uuid4

from desktop.data.repositories.beds_repo import BedsRepository
from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository

BED_COUNT = 10

PHARMACY_ITEMS = [
    ("Paracetamol 500mg", 100),
    ("Ibuprofen 200mg", 80),
    ("Amoxicillin 250mg", 60),
    ("Cetirizine 10mg", 50),
    ("Omeprazole 20mg", 40),
    ("Metformin 500mg", 70),
    ("Amlodipine 5mg", 45),
    ("Atorvastatin 10mg", 55),
    ("Azithromycin 500mg", 30),
    ("ORS Sachets", 120),
    ("Insulin (Vial)", 20),
    ("Salbutamol Inhaler", 15),
    ("Vitamin D3", 90),
    ("Iron Folic Acid", 100),
    ("Diclofenac Gel", 35),
    ("Cough Syrup", 40),
    ("Antiseptic Solution", 25),
    ("IV Fluid (NS 500ml)", 50),
    ("Surgical Gloves (box)", 60),
    ("Face Masks (box)", 80),
]

DOCTORS = [
    ("Dr. Asha Rao", 1),
    ("Dr. Vikram Shah", 1),
    ("Dr. Meera Nair", 2),
    ("Dr. Rohan Gupta", 3),
]


def seed_default_data(conn: sqlite3.Connection) -> None:
    beds_repo = BedsRepository(conn)
    if beds_repo.count() == 0:
        for i in range(1, BED_COUNT + 1):
            beds_repo.insert(bed_id=str(uuid4()), label=f"Bed {i}")

    pharmacy_repo = PharmacyStockRepository(conn)
    if pharmacy_repo.count() == 0:
        for name, quantity in PHARMACY_ITEMS:
            pharmacy_repo.insert(item_id=str(uuid4()), name=name, quantity=quantity)

    doctors_repo = DoctorsRepository(conn)
    if doctors_repo.count() == 0:
        for name, dept_id in DOCTORS:
            doctors_repo.insert(doctor_id=str(uuid4()), full_name=name, dept_id=dept_id)
