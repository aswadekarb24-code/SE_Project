"""Application-wide Qt theme built from common/design_tokens.py.

Widgets opt into styles through object names (`card`, `pageTitle`, ...)
and dynamic properties (`variant="primary"`, `tone="success"`), the Qt
equivalents of CSS ids and classes. desktop/ui/components.py sets them.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from PyQt6.QtCore import QDir
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

from common import design_tokens as tokens

_ASSETS_DIR = Path(__file__).parent / "assets"

# Text on the brand panel's dark gradient, and unselected segment text on
# its grey track -- each checked for >= 4.5:1 contrast.
_EXTRA = {
    "BRAND_TEXT": "#C8D3E6",
    "BRAND_SOFT": "#93A3BD",
    "SEGMENT_TEXT": "#5B6270",
    "NEUTRAL_TEXT": "#4B5260",
    "NEUTRAL_TINT": "#F1F2F4",
    "SERVING_BORDER": "#DCE9FB",
}

_STYLESHEET = Template("""
/* Canvas and shells ---------------------------------------------------- */
QMainWindow { background: $CANVAS; }
QFrame#shell, QFrame#authShell {
    background: $SHELL;
    border: none;
    border-radius: ${RADIUS_SHELL}px;
}
QLabel { color: $TEXT_PRIMARY; background: transparent; }

/* Sign-in brand panel --------------------------------------------------- */
QFrame#brandPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 $DARK_ACCENT, stop:1 #17325A);
    border-radius: 24px;
}
QFrame#brandPanel QLabel { color: $TEXT_ON_ACCENT; }
QLabel#brandName { font-size: 17px; font-weight: 600; }
QLabel#brandHeadline { font-size: 34px; font-weight: 600; letter-spacing: -0.6px; }
QFrame#brandPanel QLabel#brandText { color: $BRAND_TEXT; font-size: 15px; }
QFrame#brandPanel QLabel#brandFeature { color: $BRAND_TEXT; font-size: 14px; }
QFrame#brandPanel QLabel#brandFoot { color: $BRAND_SOFT; font-size: 12px; }
QLabel#brandIcon { background: rgba(255, 255, 255, 26); border-radius: 10px; }
QLabel#logoChip { background: $PRIMARY; border-radius: 13px; }
QLabel#authTitle { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; }

/* Sidebar --------------------------------------------------------------- */
QFrame#sidebar {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 22px;
}
QToolButton#navButton { background: transparent; border: none; border-radius: 13px; }
QToolButton#navButton:hover { background: $HOVER; }
QToolButton#navButton:checked { background: $PRIMARY_TINT; }

/* Header ---------------------------------------------------------------- */
QLabel#pageTitle { font-size: 30px; font-weight: 600; letter-spacing: -0.6px; }
QLabel#pageSubtitle { font-size: 14px; color: $TEXT_SECONDARY; }
QPushButton#dateChip {
    background: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 19px;
    min-height: 36px;
    padding: 0 16px;
    font-weight: 500;
}
QPushButton#dateChip:hover { background: $PRIMARY_TINT; border-color: #CFE3FD; }

/* Day-overview calendar --------------------------------------------------- */
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: $SURFACE;
    border-bottom: 1px solid $DIVIDER;
    min-height: 40px;
}
QCalendarWidget QToolButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    color: $TEXT_PRIMARY;
    font-weight: 600;
    padding: 4px 8px;
}
QCalendarWidget QToolButton:hover { background: $HOVER; }
QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }
QCalendarWidget QSpinBox {
    border: 1px solid $BORDER_STRONG;
    border-radius: 6px;
    padding: 2px 6px;
    selection-background-color: $PRIMARY_TINT;
    selection-color: $TEXT_PRIMARY;
}
QCalendarWidget QMenu { background: $SURFACE; border: 1px solid $BORDER; }
QCalendarWidget QMenu::item { padding: 6px 18px; }
QCalendarWidget QMenu::item:selected { background: $PRIMARY_TINT; color: $PRIMARY; }
QCalendarWidget QAbstractItemView {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    outline: 0;
    selection-background-color: $PRIMARY;
    selection-color: $TEXT_ON_ACCENT;
}
QCalendarWidget QAbstractItemView:disabled { color: $TEXT_DISABLED; }
QFrame#calendarPopup { background: $SURFACE; border: 1px solid $BORDER_STRONG; }
QCalendarWidget#dayCalendar {
    border: 1px solid $BORDER;
    border-radius: 12px;
}
QFrame#userChip {
    background: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 24px;
}
QLabel#chipName { font-size: 13px; font-weight: 600; }
QFrame#syncChip {
    background: $SURFACE;
    border: 1px solid $BORDER_STRONG;
    border-radius: 19px;
}
QFrame#syncChip[tone="synced"] { background: $PRIMARY_TINT; border-color: #CFE3FD; }
QFrame#syncChip[tone="offline"] { background: $WARNING_TINT; border-color: $WARNING_BORDER; }
QFrame#syncChip[tone="conflict"] { background: $DANGER_TINT; border-color: $DANGER_BORDER; }
QLabel#syncDot { border-radius: 4px; background: $TEXT_DISABLED; }
QLabel#syncDot[tone="synced"] { background: $ACCENT; }
QLabel#syncDot[tone="offline"] { background: #E8A10C; }
QLabel#syncDot[tone="conflict"] { background: $DANGER; }
QLabel#syncText { font-size: 13px; font-weight: 600; }
QLabel#syncText[tone="synced"] { color: $PRIMARY; }
QLabel#syncText[tone="offline"] { color: $WARNING; }
QLabel#syncText[tone="conflict"] { color: $DANGER; }
QToolButton#syncRetry { background: transparent; border: none; border-radius: 14px; }
QToolButton#syncRetry:hover { background: rgba(0, 0, 0, 15); }
QLabel#chipRole { font-size: 12px; color: $TEXT_SECONDARY; }

/* Cards and stat tiles -------------------------------------------------- */
QFrame#card, QFrame#statCard {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: ${RADIUS_CARD}px;
}
QLabel#cardTitle { font-size: 18px; font-weight: 600; letter-spacing: -0.2px; }
QLabel#statLabel { font-size: 14px; font-weight: 500; }
QLabel#statValue { font-size: 32px; font-weight: 600; letter-spacing: -0.8px; }
QLabel#statCaption { font-size: 13px; color: $TEXT_SECONDARY; }
QFrame#actionRow {
    background: $SURFACE_SUBTLE;
    border: 1px solid $BORDER;
    border-radius: 14px;
}
QFrame#listRow { border: none; border-bottom: 1px solid $DIVIDER; }

/* Text roles ------------------------------------------------------------ */
QLabel#fieldLabel { font-size: 13px; font-weight: 600; color: $TEXT_SECONDARY; }
QLabel#sectionLabel { font-size: 14px; font-weight: 600; }
QLabel#muted { font-size: 13px; color: $TEXT_SECONDARY; }
QLabel#cellTitle { font-size: 14px; font-weight: 500; }
QLabel#detailName { font-size: 21px; font-weight: 600; letter-spacing: -0.3px; }
QLabel#dialogTitle { font-size: 19px; font-weight: 600; }
QLabel#infoValue { font-size: 14px; }
QLabel#emptyTitle { font-size: 15px; font-weight: 600; }
QLabel#errorLabel {
    color: $DANGER;
    background: $DANGER_TINT;
    border: 1px solid $DANGER_BORDER;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 13px;
}
QLabel#successBanner {
    color: $SUCCESS;
    background: $SUCCESS_TINT;
    border: 1px solid $SUCCESS_BORDER;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 600;
}

/* Status badges --------------------------------------------------------- */
QLabel#badge {
    border-radius: ${RADIUS_BADGE}px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#badge[tone="success"] { background: $SUCCESS_TINT; color: $SUCCESS; }
QLabel#badge[tone="danger"] { background: $DANGER_TINT; color: $DANGER; }
QLabel#badge[tone="warning"] { background: $WARNING_TINT; color: $WARNING; }
QLabel#badge[tone="info"] { background: $PRIMARY_TINT; color: $PRIMARY; }
QLabel#badge[tone="neutral"] { background: $NEUTRAL_TINT; color: $NEUTRAL_TEXT; }

/* Check-in result and the doctor's now-serving panel --------------------- */
QFrame#tokenBanner {
    background: $SUCCESS_TINT;
    border: 1px solid $SUCCESS_BORDER;
    border-radius: 18px;
}
QLabel#tokenNumber { font-size: 40px; font-weight: 700; color: $SUCCESS; }
QLabel#bannerTitle { font-size: 17px; font-weight: 600; }
QLabel#bannerText { font-size: 13px; color: $SUCCESS; }
QFrame#servingPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F3F8FF, stop:1 #FAF6FF);
    border: 1px solid $SERVING_BORDER;
    border-radius: 16px;
}
QFrame#vDivider { background: $SERVING_BORDER; border: none; }
QLabel#tokenCaption { font-size: 12px; font-weight: 600; color: $PRIMARY; letter-spacing: 1px; }
QLabel#tokenHero { font-size: 64px; font-weight: 600; letter-spacing: -2px; }

/* Buttons --------------------------------------------------------------- */
QPushButton {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER_STRONG;
    border-radius: ${RADIUS_INPUT}px;
    min-height: 34px;
    padding: 0 16px;
    font-weight: 600;
}
QPushButton:hover { background: $HOVER; border-color: $BORDER_HOVER; }
QPushButton:pressed { background: $PRESSED; }
QPushButton:focus { border-color: $ACCENT; }
QPushButton:disabled { background: $HOVER; color: $TEXT_DISABLED; border-color: $BORDER; }
QPushButton[variant="primary"] {
    background: $PRIMARY;
    color: $TEXT_ON_ACCENT;
    border-color: $PRIMARY;
}
QPushButton[variant="primary"]:hover,
QPushButton[variant="primary"]:focus { background: $PRIMARY_HOVER; border-color: $PRIMARY_HOVER; }
QPushButton[variant="primary"]:disabled {
    background: $PRIMARY_DISABLED;
    border-color: $PRIMARY_DISABLED;
    color: $TEXT_ON_ACCENT;
}
QPushButton[variant="ghost"] {
    background: transparent;
    border: none;
    color: $PRIMARY;
    padding: 0 6px;
}
QPushButton[variant="ghost"]:hover { color: $PRIMARY_HOVER; text-decoration: underline; }
QPushButton[variant="ghost"]:disabled { color: $TEXT_DISABLED; background: transparent; }
QPushButton[size="tall"] { min-height: 42px; border-radius: 12px; padding: 0 20px; }
QPushButton#pillButton { min-height: 36px; border-radius: 19px; padding: 0 16px; }
QPushButton#stepButton {
    min-width: 32px;
    max-width: 32px;
    min-height: 30px;
    padding: 0;
    border-radius: 8px;
    font-size: 16px;
}

QPushButton#dayToggle { min-width: 46px; padding: 0 8px; border-radius: 10px; }
QPushButton#dayToggle:checked {
    background: $PRIMARY_TINT;
    border-color: $ACCENT;
    color: $PRIMARY;
}

QCheckBox { spacing: 10px; color: $TEXT_SECONDARY; font-size: 13px; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid $BORDER_HOVER;
    border-radius: 5px;
    background: $SURFACE;
}
QCheckBox::indicator:hover { border-color: $ACCENT; }
QCheckBox::indicator:checked {
    background: $PRIMARY;
    border-color: $PRIMARY;
    image: url(hms:check-white.svg);
}
QLabel#shortcutHint { font-size: 12px; color: $TEXT_SECONDARY; }

/* Segmented control ------------------------------------------------------ */
QFrame#segmented { background: $PRESSED; border-radius: 12px; }
QPushButton#segment {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    min-height: 32px;
    padding: 0 14px;
    color: $SEGMENT_TEXT;
}
QPushButton#segment:hover:!checked { color: $TEXT_PRIMARY; }
QPushButton#segment:checked {
    background: $SURFACE;
    border-color: $BORDER_STRONG;
    color: $TEXT_PRIMARY;
}

/* Inputs ---------------------------------------------------------------- */
QLineEdit, QComboBox, QPlainTextEdit {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER_STRONG;
    border-radius: ${RADIUS_INPUT}px;
    selection-background-color: $PRIMARY_TINT;
    selection-color: $TEXT_PRIMARY;
}
QLineEdit, QComboBox { min-height: 38px; padding: 0 12px; }
QPlainTextEdit { padding: 8px 10px; }
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: $BORDER_HOVER; }
/* Qt can't draw an outer focus ring, so focus thickens the border and
   trims the padding by the same 1px so text doesn't shift. */
QLineEdit:focus, QComboBox:focus, QComboBox:on { border: 2px solid $ACCENT; padding: 0 11px; }
QPlainTextEdit:focus { border: 2px solid $ACCENT; padding: 7px 9px; }
QLineEdit:disabled, QComboBox:disabled { background: $HOVER; color: $TEXT_DISABLED; }
QLineEdit#searchField { border-radius: 20px; padding-left: 6px; }
QLineEdit#searchField:focus { padding-left: 5px; }

QComboBox { padding-right: 36px; combobox-popup: 0; }
QComboBox:focus, QComboBox:on { padding-right: 35px; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 32px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow { image: url(hms:chevron-down.svg); width: 16px; height: 16px; }
QComboBox QAbstractItemView {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER;
    padding: 4px;
    outline: 0;
}
QComboBox QAbstractItemView::item { min-height: 34px; padding: 0 10px; border-radius: 6px; }
QComboBox QAbstractItemView::item:hover { background: $HOVER; color: $TEXT_PRIMARY; }
QComboBox QAbstractItemView::item:selected { background: $PRIMARY_TINT; color: $PRIMARY; }

/* Tables ---------------------------------------------------------------- */
QTableWidget {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: none;
    outline: 0;
    selection-background-color: $PRIMARY_TINT;
    selection-color: $TEXT_PRIMARY;
}
QTableWidget::item { border-bottom: 1px solid $DIVIDER; padding: 0 12px; }
QTableWidget::item:selected { background: $PRIMARY_TINT; color: $TEXT_PRIMARY; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: $SURFACE_SUBTLE;
    color: $TEXT_SECONDARY;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 0 12px;
    font-size: 13px;
    font-weight: 600;
}
QHeaderView::section:first { border-top-left-radius: 10px; }
QHeaderView::section:last { border-top-right-radius: 10px; }
QTableCornerButton::section { background: $SURFACE_SUBTLE; border: none; }

/* Lists ----------------------------------------------------------------- */
QListWidget#resultsList {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 12px;
    padding: 4px;
    outline: 0;
}
QListWidget#resultsList::item { border-radius: 10px; margin: 1px 0; }
QListWidget#resultsList::item:hover { background: $HOVER; }
QListWidget#resultsList::item:selected { background: $PRIMARY_TINT; }

/* Scrollbars ------------------------------------------------------------ */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle { background: $BORDER_HOVER; border-radius: 3px; }
QScrollBar::handle:vertical { min-height: 32px; }
QScrollBar::handle:horizontal { min-width: 32px; }
QScrollBar::handle:hover { background: $TEXT_DISABLED; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* Dialogs and tooltips -------------------------------------------------- */
QDialog { background: $SURFACE; }
QTextBrowser#reportPreview {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: 12px;
    padding: 18px;
}
QMessageBox QPushButton { min-width: 80px; }
QToolTip {
    background: $DARK_ACCENT;
    color: $TEXT_ON_ACCENT;
    border: none;
    padding: 6px 10px;
    font-size: 12px;
}
""")


def pick_font_family() -> str:
    """First family from the token stack that's installed, else Qt's default."""
    installed = set(QFontDatabase.families())
    for family in tokens.FONT_FAMILIES:
        if family in installed:
            return family
    return QApplication.font().family()


def build_stylesheet() -> str:
    values = {name: value for name, value in vars(tokens).items() if name.isupper()}
    values.update(_EXTRA)
    return _STYLESHEET.substitute(values)


def _build_palette() -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: tokens.SURFACE,
        QPalette.ColorRole.WindowText: tokens.TEXT_PRIMARY,
        QPalette.ColorRole.Base: tokens.SURFACE,
        QPalette.ColorRole.AlternateBase: tokens.SURFACE_SUBTLE,
        QPalette.ColorRole.Text: tokens.TEXT_PRIMARY,
        QPalette.ColorRole.Button: tokens.SURFACE,
        QPalette.ColorRole.ButtonText: tokens.TEXT_PRIMARY,
        QPalette.ColorRole.Highlight: tokens.PRIMARY_TINT,
        QPalette.ColorRole.HighlightedText: tokens.TEXT_PRIMARY,
        QPalette.ColorRole.PlaceholderText: tokens.TEXT_MUTED,
        QPalette.ColorRole.Link: tokens.PRIMARY,
        QPalette.ColorRole.ToolTipBase: tokens.DARK_ACCENT,
        QPalette.ColorRole.ToolTipText: tokens.TEXT_ON_ACCENT,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(tokens.TEXT_DISABLED))
    return palette


def apply_theme(app: QApplication) -> None:
    """Fusion as the base style (renders stylesheets most predictably on every
    OS), the token font, palette and stylesheet. Call once, before any
    window is created.
    """
    QDir.addSearchPath("hms", str(_ASSETS_DIR))
    app.setStyle("Fusion")

    font = QFont(pick_font_family())
    font.setPixelSize(tokens.FONT_SIZE_BODY)
    app.setFont(font)

    app.setPalette(_build_palette())
    app.setStyleSheet(build_stylesheet())
