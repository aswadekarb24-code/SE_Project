"""Application-wide Qt theme built from common/design_tokens.py.

Visual only. Widgets opt into variants through a dynamic property
(`variant="primary"`) or an object name (`statusLabel`), the Qt equivalent
of CSS classes and ids, so no widget structure has to change.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from PyQt6.QtCore import QDir
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication, QComboBox, QStyledItemDelegate, QWidget

from common import design_tokens as tokens

_ASSETS_DIR = Path(__file__).parent / "assets"

# Pill tabs: content height + vertical padding + border, so the radius can be
# exactly half the height (Qt squares off radii larger than that).
_TAB_CONTENT_HEIGHT = 20
_TAB_PADDING_Y = 8
_TAB_HEIGHT = _TAB_CONTENT_HEIGHT + 2 * _TAB_PADDING_Y + 2

_STYLESHEET = Template("""
/* Canvas, shell and card ------------------------------------------------ */
QMainWindow { background: $CANVAS; }
QMainWindow > QTabWidget {
    background: $SHELL;
    border: none;
    border-radius: ${RADIUS_SHELL}px;
}
QTabWidget::tab-bar { left: ${SPACE_3}px; }
QTabWidget::pane {
    background: $SURFACE;
    border: 1px solid $BORDER;
    border-radius: ${RADIUS_CARD}px;
    margin: ${SPACE_2}px ${SPACE_3}px ${SPACE_3}px ${SPACE_3}px;
    padding: ${SPACE_3}px;
}

/* Top tabs: separate pills, dark fill when active ----------------------- */
QTabBar { qproperty-drawBase: 0; background: transparent; }
QTabBar::tab {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER_STRONG;
    border-radius: ${TAB_RADIUS}px;
    height: ${TAB_CONTENT_HEIGHT}px;
    padding: ${TAB_PADDING_Y}px 18px;
    margin-top: ${SPACE_3}px;
    margin-right: ${SPACE_1}px;
    font-weight: 500;
    text-transform: uppercase; /* font capitalization only; label text unchanged */
}
QTabBar::tab:hover:!selected { background: $HOVER; }
QTabBar::tab:selected {
    background: $DARK_ACCENT;
    border-color: $DARK_ACCENT;
    color: $TEXT_ON_ACCENT;
}

/* Text ------------------------------------------------------------------ */
QLabel { color: $TEXT_PRIMARY; background: transparent; }
ReceptionWindow QLabel {
    min-height: 40px; /* same as the inputs, so form labels centre on them */
    color: $TEXT_SECONDARY;
    font-size: ${FONT_SIZE_LABEL}px;
    font-weight: 500;
}
QLabel#statusLabel {
    color: $TEXT_PRIMARY;
    font-size: ${FONT_SIZE_LEAD}px;
    font-weight: 400;
}
DoctorWindow QLabel#statusLabel {
    background: $SURFACE;
    border: 1px solid qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 $HIGHLIGHT_START, stop:1 $HIGHLIGHT_END);
    border-radius: ${RADIUS_TILE}px;
    padding: 20px 22px;
    font-size: ${FONT_SIZE_FEATURE}px;
}

/* Buttons: outlined by default, solid blue for the primary action ------- */
QPushButton {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER_STRONG;
    border-radius: ${RADIUS_BUTTON}px;
    min-height: 30px;
    padding: 0 16px;
    font-weight: 500;
}
QPushButton:hover { background: $HOVER; border-color: $BORDER_HOVER; }
QPushButton:pressed { background: $PRESSED; }
QPushButton:focus { border-color: $ACCENT; }
QPushButton:disabled {
    background: $HOVER;
    color: $TEXT_DISABLED;
    border-color: $BORDER;
}
QPushButton[variant="primary"] {
    background: $PRIMARY;
    color: $TEXT_ON_ACCENT;
    border-color: $PRIMARY;
}
QPushButton[variant="primary"]:hover,
QPushButton[variant="primary"]:focus {
    background: $PRIMARY_HOVER;
    border-color: $PRIMARY_HOVER;
}
QPushButton[variant="primary"]:disabled {
    background: $PRIMARY_DISABLED;
    border-color: $PRIMARY_DISABLED;
    color: $TEXT_ON_ACCENT;
}
PharmacyWidget QPushButton { min-width: 48px; }

/* Inputs and dropdowns -------------------------------------------------- */
QLineEdit, QComboBox {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER_STRONG;
    border-radius: ${RADIUS_INPUT}px;
    min-height: 38px;
    padding: 0 12px;
    selection-background-color: $PRIMARY_TINT;
    selection-color: $TEXT_PRIMARY;
}
QLineEdit:hover, QComboBox:hover { border-color: $BORDER_HOVER; }
/* Qt stylesheets cannot draw an outer focus ring, so focus thickens the
   border instead, with 1px less padding so the text does not shift. */
QLineEdit:focus, QComboBox:focus, QComboBox:on {
    border: 2px solid $ACCENT;
    padding: 0 11px;
}
QLineEdit:disabled, QComboBox:disabled { background: $HOVER; color: $TEXT_DISABLED; }
/* Form-style screens read as one comfortable column inside the card. */
ReceptionWindow, DoctorWindow, DoctorAvailabilityWidget { max-width: 640px; }
DoctorAvailabilityWidget QComboBox { min-width: 200px; max-width: 240px; }

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
    border-radius: ${RADIUS_INPUT}px;
    padding: 4px;
    outline: 0;
    selection-background-color: $PRIMARY_TINT;
    selection-color: $PRIMARY;
}
QComboBox QAbstractItemView::item {
    min-height: 34px;
    padding: 0 10px;
    border-radius: ${RADIUS_BADGE}px;
}
QComboBox QAbstractItemView::item:hover { background: $HOVER; color: $TEXT_PRIMARY; }
QComboBox QAbstractItemView::item:selected { background: $PRIMARY_TINT; color: $PRIMARY; }

/* Lists: airy rows, faint dividers, tinted selection -------------------- */
QListWidget {
    background: $SURFACE;
    color: $TEXT_PRIMARY;
    border: 1px solid $BORDER;
    border-radius: ${RADIUS_TILE}px;
    padding: 4px 8px;
    outline: 0;
}
QListWidget::item {
    padding: 14px 8px;
    border-bottom: 1px solid $DIVIDER;
}
QListWidget::item:hover { background: $HOVER; }
QListWidget::item:selected {
    background: $PRIMARY_TINT;
    color: $PRIMARY;
    border-bottom-color: $PRIMARY_TINT;
}

/* Scrollbars ------------------------------------------------------------ */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle { background: $BORDER_HOVER; border-radius: 3px; }
QScrollBar::handle:vertical { min-height: 32px; }
QScrollBar::handle:horizontal { min-width: 32px; }
QScrollBar::handle:hover { background: $TEXT_DISABLED; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* Dialogs: role picker and message boxes -------------------------------- */
QDialog { background: $SURFACE; }
RoleSelectDialog QLabel {
    font-size: ${FONT_SIZE_TITLE}px;
    letter-spacing: -0.2px;
}
RoleSelectDialog QPushButton {
    min-height: 46px;
    min-width: 280px;
    border-radius: ${RADIUS_TILE}px;
    font-size: 15px;
}
RoleSelectDialog QPushButton:hover,
RoleSelectDialog QPushButton:focus {
    background: $PRIMARY_TINT;
    border-color: $ACCENT;
    color: $PRIMARY;
}
QMessageBox QPushButton { min-width: 72px; }
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
    values.update(
        TAB_CONTENT_HEIGHT=_TAB_CONTENT_HEIGHT,
        TAB_PADDING_Y=_TAB_PADDING_Y,
        TAB_RADIUS=_TAB_HEIGHT // 2,
    )
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


def style_combo_popups(root: QWidget) -> None:
    """QComboBox popups default to a QItemDelegate, which ignores the
    stylesheet's ::item rules (row height, padding). Give every combo under
    `root` a QStyledItemDelegate so its popup rows match the theme.
    """
    for combo in root.findChildren(QComboBox):
        combo.setItemDelegate(QStyledItemDelegate(combo))


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
