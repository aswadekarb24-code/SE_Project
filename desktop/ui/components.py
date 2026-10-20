"""Shared building blocks for every screen: cards, stat tiles, badges,
avatars, form fields and tables. Their look lives in theme.py; these set
the object names and properties the stylesheet keys on.
"""

from __future__ import annotations

import zlib

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common import design_tokens as tokens
from desktop.ui import icons

# Status value -> (badge text, badge tone)
STATUS_BADGES = {
    "WAITING": ("Waiting", "warning"),
    "CALLED": ("With doctor", "info"),
    "DONE": ("Done", "success"),
    "AVAILABLE": ("Available", "success"),
    "BUSY": ("Busy", "warning"),
    "OFF_DUTY": ("Off duty", "neutral"),
    "OCCUPIED": ("Occupied", "danger"),
    "MAINTENANCE": ("Maintenance", "warning"),
}

# Avatar tints: (background, text) -- the spec's pastel event tints.
_AVATAR_TONES = (
    (tokens.PRIMARY_TINT, tokens.PRIMARY),
    ("#F0EAFE", "#5B3FB8"),
    ("#FDEAE7", "#A23B2A"),
    (tokens.SUCCESS_TINT, tokens.SUCCESS),
)


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after changing a property it selects on."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def button(
    text: str,
    variant: str = "secondary",
    icon_name: str | None = None,
    *,
    tall: bool = False,
) -> QPushButton:
    """variant: primary (solid blue), secondary (outlined), ghost (text link)."""
    widget = QPushButton(text)
    widget.setProperty("variant", variant)
    if tall:
        widget.setProperty("size", "tall")
    widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    if icon_name:
        color = tokens.TEXT_ON_ACCENT if variant == "primary" else tokens.TEXT_PRIMARY
        if variant == "ghost":
            color = tokens.PRIMARY
        widget.setIcon(icons.icon(icon_name, color, size=16))
    return widget


def set_variant(widget: QPushButton, variant: str) -> None:
    widget.setProperty("variant", variant)
    repolish(widget)


def combo_box() -> QComboBox:
    """A QComboBox whose popup rows follow the stylesheet (the default
    QItemDelegate ignores ::item rules like row height and padding).
    """
    combo = QComboBox()
    combo.setItemDelegate(QStyledItemDelegate(combo))
    combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return combo


def line_edit(placeholder: str = "") -> QLineEdit:
    field = QLineEdit()
    field.setPlaceholderText(placeholder)
    return field


def search_field(placeholder: str) -> QLineEdit:
    field = QLineEdit()
    field.setObjectName("searchField")
    field.setPlaceholderText(placeholder)
    field.setClearButtonEnabled(True)
    field.addAction(icons.icon("search", size=16), QLineEdit.ActionPosition.LeadingPosition)
    return field


def label(text: str = "", role: str | None = None, *, wrap: bool = False) -> QLabel:
    """role: the label's objectName in theme.py (e.g. fieldLabel, muted)."""
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def field(caption: str, widget: QWidget) -> QWidget:
    """A form field with its caption above it."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    caption_label = label(caption, "fieldLabel")
    caption_label.setBuddy(widget)
    layout.addWidget(caption_label)
    layout.addWidget(widget)
    return box


class Card(QFrame):
    """White rounded surface with an optional title row."""

    def __init__(
        self,
        title: str | None = None,
        *,
        action: QWidget | None = None,
        padding: int = 20,
        spacing: int = 14,
    ) -> None:
        super().__init__()
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding - 2, padding, padding)
        self.body.setSpacing(spacing)
        if title is not None:
            header = QHBoxLayout()
            header.setSpacing(12)
            self.title_label = label(title, "cardTitle")
            header.addWidget(self.title_label)
            header.addStretch(1)
            if action is not None:
                header.addWidget(action)
            self.body.addLayout(header)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget


class Badge(QLabel):
    """Soft-tinted status pill. tone: success, danger, warning, info, neutral."""

    def __init__(self, text: str = "", tone: str = "neutral") -> None:
        super().__init__()
        self.setObjectName("badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set(text, tone)

    def set(self, text: str, tone: str) -> None:
        self.setText(text)
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            repolish(self)

    @classmethod
    def for_status(cls, status: str) -> Badge:
        text, tone = STATUS_BADGES.get(status, (status.title(), "neutral"))
        return cls(text, tone)


def initials(name: str) -> str:
    words = [w for w in name.replace("Dr.", "").split() if w[:1].isalpha()]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


class Avatar(QLabel):
    """Initials in a tinted circle; the tint is stable per name."""

    def __init__(self, name: str, size: int = 36) -> None:
        super().__init__(initials(name))
        background, color = _AVATAR_TONES[zlib.crc32(name.encode()) % len(_AVATAR_TONES)]
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: {background}; color: {color}; border-radius: {size // 2}px;"
            f" font-size: {max(11, round(size * 0.36))}px; font-weight: 600;"
        )


class IconTile(QLabel):
    """A tinted rounded square holding an icon (stat cards, quick actions)."""

    def __init__(self, icon_name: str, tone: str = "info", size: int = 40) -> None:
        super().__init__()
        background, color = {
            "info": (tokens.PRIMARY_TINT, tokens.PRIMARY),
            "success": (tokens.SUCCESS_TINT, tokens.SUCCESS),
            "warning": (tokens.WARNING_TINT, tokens.WARNING),
            "danger": (tokens.DANGER_TINT, tokens.DANGER),
            "lavender": ("#F0EAFE", "#5B3FB8"),
        }[tone]
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPixmap(icons.pixmap(icon_name, color, round(size * 0.5)))
        self.setStyleSheet(f"background: {background}; border-radius: {round(size * 0.3)}px;")


class StatCard(QFrame):
    """KPI tile: icon, label, big number and a caption line."""

    def __init__(self, label_text: str, icon_name: str, tone: str = "info") -> None:
        super().__init__()
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(label(label_text, "statLabel"))
        top.addStretch(1)
        top.addWidget(IconTile(icon_name, tone, 36))
        layout.addLayout(top)
        layout.addSpacing(6)
        self.value_label = label("0", "statValue")
        layout.addWidget(self.value_label)
        self.caption_label = label("", "statCaption")
        layout.addWidget(self.caption_label)

    def set(self, value: object, caption: str = "") -> None:
        self.value_label.setText(str(value))
        self.caption_label.setText(caption)


class Segmented(QFrame):
    """Two or more mutually exclusive pill options on a grey track."""

    def __init__(self, options: list[str]) -> None:
        super().__init__()
        self.setObjectName("segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.buttons: list[QPushButton] = []
        for text in options:
            option = QPushButton(text)
            option.setObjectName("segment")
            option.setCheckable(True)
            option.setAutoExclusive(True)
            option.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            layout.addWidget(option)
            self.buttons.append(option)
        self.buttons[0].setChecked(True)

    def index(self) -> int:
        return next(i for i, b in enumerate(self.buttons) if b.isChecked())

    def set_index(self, index: int) -> None:
        self.buttons[index].setChecked(True)


def table(headers: list[str], *, row_height: int = 52) -> QTableWidget:
    """Read-only, row-selecting table styled like the reference tables."""
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setDefaultSectionSize(row_height)
    widget.setShowGrid(False)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    widget.setWordWrap(False)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header = widget.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    header.setFixedHeight(40)
    return widget


def table_item(text: str, *, muted: bool = False, data: object = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    if muted:
        item.setForeground(QColor(tokens.TEXT_SECONDARY))
    if data is not None:
        item.setData(Qt.ItemDataRole.UserRole, data)
    return item


def cell(*widgets: QWidget, spacing: int = 10) -> QWidget:
    """Wrap widgets for a table cell: vertically centred, left aligned."""
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(12, 0, 12, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addStretch(1)
    return box


def person_cell(name: str, detail: str | None = None) -> QWidget:
    """Avatar + name (and an optional muted second line) for a table cell."""
    text = QWidget()
    lines = QVBoxLayout(text)
    lines.setContentsMargins(0, 0, 0, 0)
    lines.setSpacing(0)
    lines.addWidget(label(name, "cellTitle"))
    if detail:
        lines.addWidget(label(detail, "muted"))
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(12, 0, 8, 0)
    layout.setSpacing(10)
    layout.addWidget(Avatar(name, 30), 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)
    return box


def empty_state(title: str, detail: str = "", icon_name: str = "search") -> QWidget:
    box = QWidget()
    box.setObjectName("emptyState")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 28, 16, 28)
    layout.setSpacing(6)
    layout.addStretch(1)
    tile = IconTile(icon_name, "info", 44)
    layout.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
    layout.addSpacing(6)
    title_label = label(title, "emptyTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    if detail:
        detail_label = label(detail, "muted", wrap=True)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail_label)
    layout.addStretch(1)
    return box
