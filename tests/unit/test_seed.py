from desktop.data.repositories.beds_repo import BedsRepository
from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.repositories.pharmacy_repo import PharmacyStockRepository
from desktop.data.seed import BED_COUNT, DOCTORS, PHARMACY_ITEMS, seed_default_data


def test_seed_inserts_expected_counts(db_conn):
    seed_default_data(db_conn)

    assert BedsRepository(db_conn).count() == BED_COUNT == 10
    assert PharmacyStockRepository(db_conn).count() == len(PHARMACY_ITEMS) == 20
    assert DoctorsRepository(db_conn).count() == len(DOCTORS)


def test_seed_is_idempotent(db_conn):
    seed_default_data(db_conn)
    seed_default_data(db_conn)  # calling twice must not duplicate rows

    assert BedsRepository(db_conn).count() == BED_COUNT
    assert PharmacyStockRepository(db_conn).count() == len(PHARMACY_ITEMS)
    assert DoctorsRepository(db_conn).count() == len(DOCTORS)


def test_seeded_departments_exist_for_seeded_doctors(db_conn):
    seed_default_data(db_conn)
    dept_ids = {row[0] for row in db_conn.execute("SELECT dept_id FROM departments")}
    doctor_dept_ids = {row[0] for row in db_conn.execute("SELECT dept_id FROM doctors")}
    assert doctor_dept_ids <= dept_ids  # every seeded doctor's dept_id is valid
