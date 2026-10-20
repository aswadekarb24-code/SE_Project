"""Sign-in / create-account screen shown at launch and after logging out.

It replaces the old role picker: the role now comes from the account, so
whoever signs in gets their role's screens. On a fresh install with no
accounts yet it opens on "Create account".
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from common import design_tokens as tokens
from desktop.data.numbering import station_code
from desktop.services.auth_service import (
    MIN_PASSWORD_LENGTH,
    AuthError,
    RegistrationError,
    Role,
    authenticate,
    has_accounts,
    register_user,
)
from desktop.services.department_service import list_departments
from desktop.ui import icons
from desktop.ui.components import Segmented, button, combo_box, field, label, line_edit

FORM_WIDTH = 380


def _password_field(placeholder: str) -> QLineEdit:
    """Password input with a show/hide toggle at its right edge."""
    field_widget = line_edit(placeholder)
    field_widget.setEchoMode(QLineEdit.EchoMode.Password)
    toggle = QAction(icons.icon("eye", size=16), "Show password", field_widget)
    toggle.setCheckable(True)

    def on_toggled(shown: bool) -> None:
        field_widget.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        toggle.setIcon(icons.icon("eye-off" if shown else "eye", size=16))
        toggle.setText("Hide password" if shown else "Show password")

    toggle.toggled.connect(on_toggled)
    field_widget.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
    return field_widget


def _with_busy_cursor(work):
    """Password hashing takes a moment on purpose; show that it's working."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return work()
    finally:
        QApplication.restoreOverrideCursor()


class _FormBase(QWidget):
    authenticated = pyqtSignal(object)
    switch_requested = pyqtSignal()

    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(16)
        self.layout_.addStretch(1)
        self.title_label = label(title, "authTitle")
        self.subtitle_label = label(subtitle, "muted", wrap=True)
        heading = QVBoxLayout()
        heading.setSpacing(6)
        heading.addWidget(self.title_label)
        heading.addWidget(self.subtitle_label)
        self.layout_.addLayout(heading)
        self.layout_.addSpacing(8)
        self.error_label = label("", "errorLabel", wrap=True)
        self.error_label.hide()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def _footer(self, prompt: str, link_text: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addStretch(1)
        row.addWidget(label(prompt, "muted"))
        self.switch_link = button(link_text, "ghost")
        self.switch_link.clicked.connect(self.switch_requested.emit)
        row.addWidget(self.switch_link)
        row.addStretch(1)
        self.layout_.addSpacing(4)
        self.layout_.addLayout(row)
        self.layout_.addStretch(1)


class LoginForm(_FormBase):
    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__("Welcome back", "Sign in to your account to continue.")
        self._conn = conn
        self.username_input = line_edit("Your username")
        self.password_input = _password_field("Your password")
        self.submit_button = button("Sign in", "primary", tall=True)

        self.layout_.addWidget(field("Username", self.username_input))
        self.layout_.addWidget(field("Password", self.password_input))
        self.layout_.addWidget(self.error_label)
        self.layout_.addSpacing(4)
        self.layout_.addWidget(self.submit_button)
        self._footer("New here?", "Create an account")

        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.submit)
        self.submit_button.clicked.connect(self.submit)

    def reset(self) -> None:
        self.username_input.clear()
        self.password_input.clear()
        self.show_error("")

    def submit(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.show_error("Enter your username and password.")
            return
        try:
            user = _with_busy_cursor(lambda: authenticate(self._conn, username, password))
        except AuthError as error:
            self.show_error(str(error))
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.reset()
        self.authenticated.emit(user)


class SignUpForm(_FormBase):
    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__(
            "Create your account",
            "Set up a login for the front desk or a consulting doctor.",
        )
        self._conn = conn
        self.full_name_input = line_edit("e.g. Asha Rao")
        self.username_input = line_edit("Letters, numbers, . _ -")
        self.role_select = Segmented([Role.RECEPTIONIST.label, Role.DOCTOR.label])
        self.department_select = combo_box()
        for dept_id, name in list_departments(conn):
            self.department_select.addItem(name, dept_id)
        self.password_input = _password_field(f"At least {MIN_PASSWORD_LENGTH} characters")
        self.confirm_input = _password_field("Type it again")
        self.submit_button = button("Create account", "primary", tall=True)

        self.layout_.addWidget(field("Full name", self.full_name_input))
        self.layout_.addWidget(field("Username", self.username_input))
        self.layout_.addWidget(field("I work as", self.role_select))
        self.department_field = field("Department", self.department_select)
        self.layout_.addWidget(self.department_field)
        passwords = QHBoxLayout()
        passwords.setSpacing(12)
        passwords.addWidget(field("Password", self.password_input))
        passwords.addWidget(field("Confirm password", self.confirm_input))
        self.layout_.addLayout(passwords)
        self.layout_.addWidget(self.error_label)
        self.layout_.addSpacing(4)
        self.layout_.addWidget(self.submit_button)
        self._footer("Already have an account?", "Sign in")

        for option in self.role_select.buttons:
            option.toggled.connect(self._update_department_visibility)
        self._update_department_visibility()
        self.confirm_input.returnPressed.connect(self.submit)
        self.submit_button.clicked.connect(self.submit)

    @property
    def role(self) -> Role:
        return (Role.RECEPTIONIST, Role.DOCTOR)[self.role_select.index()]

    def _update_department_visibility(self) -> None:
        self.department_field.setVisible(self.role == Role.DOCTOR)

    def set_first_run(self, first_run: bool) -> None:
        self.subtitle_label.setText(
            "No accounts on this station yet. Create the first one to get started."
            if first_run
            else "Set up a login for the front desk or a consulting doctor."
        )
        # Nobody can sign in until an account exists.
        self.switch_link.setEnabled(not first_run)

    def reset(self) -> None:
        for widget in (
            self.full_name_input,
            self.username_input,
            self.password_input,
            self.confirm_input,
        ):
            widget.clear()
        self.role_select.set_index(0)
        self.department_select.setCurrentIndex(0)
        self.show_error("")

    def submit(self) -> None:
        if self.password_input.text() != self.confirm_input.text():
            self.show_error("Passwords don't match.")
            return
        dept_id = self.department_select.currentData() if self.role == Role.DOCTOR else None
        try:
            user = _with_busy_cursor(
                lambda: register_user(
                    self._conn,
                    full_name=self.full_name_input.text(),
                    username=self.username_input.text(),
                    password=self.password_input.text(),
                    role=self.role,
                    dept_id=dept_id,
                )
            )
        except RegistrationError as error:
            self.show_error(str(error))
            return
        self.reset()
        self.authenticated.emit(user)


class AuthPage(QFrame):
    """Brand panel on the left, sign-in or sign-up form on the right."""

    authenticated = pyqtSignal(object)

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self.setObjectName("authShell")
        self._conn = conn

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        layout.addWidget(self._brand_panel(), 5)

        self.login_form = LoginForm(conn)
        self.signup_form = SignUpForm(conn)
        self.forms = QStackedWidget()
        self.forms.setFixedWidth(FORM_WIDTH)
        self.forms.addWidget(self.login_form)
        self.forms.addWidget(self.signup_form)

        form_side = QHBoxLayout()
        form_side.addStretch(1)
        form_side.addWidget(self.forms)
        form_side.addStretch(1)
        layout.addLayout(form_side, 6)

        for form in (self.login_form, self.signup_form):
            form.authenticated.connect(self.authenticated.emit)
        self.login_form.switch_requested.connect(self.show_signup)
        self.signup_form.switch_requested.connect(self.show_login)
        self.reset()

    def reset(self) -> None:
        """Back to the starting state: sign-in, or sign-up on a fresh install."""
        self.login_form.reset()
        self.signup_form.reset()
        if has_accounts(self._conn):
            self.signup_form.set_first_run(False)
            self.show_login()
        else:
            self.signup_form.set_first_run(True)
            self.show_signup()

    def show_login(self) -> None:
        self.login_form.show_error("")
        self.forms.setCurrentWidget(self.login_form)
        self.login_form.username_input.setFocus()

    def show_signup(self) -> None:
        self.signup_form.show_error("")
        self.forms.setCurrentWidget(self.signup_form)
        self.signup_form.full_name_input.setFocus()

    def _brand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("brandPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(0)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(12)
        logo = label("", "logoChip")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(icons.pixmap("logo", tokens.TEXT_ON_ACCENT, 20))
        logo_row.addWidget(logo)
        logo_row.addWidget(label("Hybrid HMS", "brandName"))
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addStretch(2)

        layout.addWidget(
            label("Care that keeps working, even offline.", "brandHeadline", wrap=True)
        )
        layout.addSpacing(14)
        layout.addWidget(
            label(
                "Register patients, run the queue and record consultations on this "
                "station. Everything syncs to the cloud when a connection is available.",
                "brandText",
                wrap=True,
            )
        )
        layout.addSpacing(28)
        for icon_name, text in (
            ("users", "Every patient gets a permanent patient number"),
            ("file-text", "Consultation reports, exportable as PDF"),
            ("shield", "Records encrypted on this device"),
        ):
            row = QHBoxLayout()
            row.setSpacing(12)
            tile = label("", "brandIcon")
            tile.setFixedSize(34, 34)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setPixmap(icons.pixmap(icon_name, tokens.TEXT_ON_ACCENT, 18))
            row.addWidget(tile)
            row.addWidget(label(text, "brandFeature", wrap=True), 1)
            layout.addLayout(row)
            layout.addSpacing(12)
        layout.addStretch(3)
        layout.addWidget(label(f"Station {station_code(self._conn)}", "brandFoot"))
        return panel
