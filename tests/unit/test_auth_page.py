import pytest

from desktop.services.auth_service import Role, register_user
from desktop.ui.auth_page import AuthPage


@pytest.fixture
def page(qapp, db_conn):
    return AuthPage(db_conn)


def _capture(page):
    signed_in = []
    page.authenticated.connect(signed_in.append)
    return signed_in


def test_fresh_install_opens_on_create_account(page):
    assert page.forms.currentWidget() is page.signup_form
    assert "No accounts" in page.signup_form.subtitle_label.text()
    assert not page.signup_form.switch_link.isEnabled()  # nobody to sign in as yet


def test_with_accounts_it_opens_on_sign_in(qapp, db_conn, receptionist):
    page = AuthPage(db_conn)
    assert page.forms.currentWidget() is page.login_form


def test_create_account_signs_the_user_in(page):
    signed_in = _capture(page)
    form = page.signup_form
    form.full_name_input.setText("Riya Desk")
    form.username_input.setText("riya")
    form.password_input.setText("front-desk-1")
    form.confirm_input.setText("front-desk-1")

    form.submit()

    assert len(signed_in) == 1
    assert signed_in[0].role == Role.RECEPTIONIST
    assert form.password_input.text() == ""  # form cleared for the next person


def test_doctor_sign_up_needs_and_stores_a_department(page, db_conn):
    signed_in = _capture(page)
    form = page.signup_form
    assert form.department_field.isHidden()
    form.role_select.set_index(1)
    assert not form.department_field.isHidden()

    form.full_name_input.setText("Meera Nair")
    form.username_input.setText("meera")
    form.department_select.setCurrentIndex(form.department_select.findData(2))
    form.password_input.setText("consult-room-1")
    form.confirm_input.setText("consult-room-1")
    form.submit()

    assert signed_in[0].role == Role.DOCTOR
    assert signed_in[0].dept_id == 2


def test_mismatched_passwords_are_caught_before_saving(page, db_conn):
    signed_in = _capture(page)
    form = page.signup_form
    form.full_name_input.setText("Riya Desk")
    form.username_input.setText("riya")
    form.password_input.setText("front-desk-1")
    form.confirm_input.setText("front-desk-2")

    form.submit()

    assert signed_in == []
    assert form.error_label.text() == "Passwords don't match."
    assert db_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_registration_errors_are_shown_inline(page):
    form = page.signup_form
    form.full_name_input.setText("Riya Desk")
    form.username_input.setText("x")
    form.password_input.setText("front-desk-1")
    form.confirm_input.setText("front-desk-1")
    form.submit()
    assert "Username" in form.error_label.text()
    assert not form.error_label.isHidden()


def test_sign_in_with_correct_password(qapp, db_conn):
    register_user(
        db_conn,
        full_name="Riya Desk",
        username="riya",
        password="front-desk-1",
        role=Role.RECEPTIONIST,
    )
    page = AuthPage(db_conn)
    signed_in = _capture(page)
    page.login_form.username_input.setText("Riya")
    page.login_form.password_input.setText("front-desk-1")

    page.login_form.submit()

    assert [user.username for user in signed_in] == ["riya"]


def test_wrong_password_shows_error_and_clears_the_field(qapp, db_conn, receptionist):
    page = AuthPage(db_conn)
    signed_in = _capture(page)
    page.login_form.username_input.setText("riya")
    page.login_form.password_input.setText("wrong-password")

    page.login_form.submit()

    assert signed_in == []
    assert page.login_form.error_label.text() == "Incorrect username or password."
    assert page.login_form.password_input.text() == ""


def test_empty_sign_in_is_rejected_without_lookup(qapp, db_conn, receptionist):
    page = AuthPage(db_conn)
    page.login_form.submit()
    assert page.login_form.error_label.text() == "Enter your username and password."


def test_switching_between_forms(qapp, db_conn, receptionist):
    page = AuthPage(db_conn)
    page.login_form.switch_link.click()
    assert page.forms.currentWidget() is page.signup_form
    page.signup_form.switch_link.click()
    assert page.forms.currentWidget() is page.login_form
