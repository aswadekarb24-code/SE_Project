"""Outline icon set (24x24, round 1.8px strokes) rendered from inline SVG,
so any icon can be drawn in any token colour at any size and stays crisp
on high-DPI screens. Keeping the shapes inline means no icon font or image
files to bundle.
"""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from common import design_tokens as tokens

_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7"'
    ' height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14"'
    ' width="7" height="7" rx="2"/>',
    "user-plus": '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-3.9 3.1-7 7-7s7 3.1 7 7"/>'
    '<path d="M19 8v6M16 11h6"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-3.9 3.1-7 7-7s7 3.1 7 7"/>'
    '<path d="M16 4.1a4 4 0 0 1 0 7.8M18 14.3c2.4.9 4 3.3 4 6.7"/>',
    "bed": '<path d="M3 5v14M3 15h18v4M21 15v-3a3 3 0 0 0-3-3h-7v6"/>'
    '<circle cx="7" cy="11" r="2"/>',
    "pill": '<path d="M10.5 20.5a5 5 0 0 1-7-7l10-10a5 5 0 0 1 7 7z"/><path d="M8.5 8.5l7 7"/>',
    "stethoscope": '<path d="M6 3H5v6a5 5 0 0 0 10 0V3h-1"/><path d="M10 14v1a5 5 0 0 0 10 0v-2"/>'
    '<circle cx="20" cy="11" r="2"/>',
    "calendar-check": '<rect x="3" y="4" width="18" height="17" rx="3"/>'
    '<path d="M8 2v4M16 2v4M3 10h18M9 15.5l2 2 4-4"/>',
    "file-text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/>'
    '<circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2'
    ' 4.2M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>'
    '<path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4"/>'
    '<path d="M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4"/>',
    "printer": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/>'
    '<path d="M7 14h10v7H7z"/>',
    # Filled glyph: the brand mark (a medical cross).
    "logo": '<path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z"/>',
}
_FILLED = {"logo"}


def _svg(name: str, color: str) -> QByteArray:
    paint = (
        f'fill="{color}" stroke="none"'
        if name in _FILLED
        else f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round"'
        ' stroke-linejoin="round"'
    )
    return QByteArray(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" {paint}>'
        f"{_PATHS[name]}</svg>".encode()
    )


def _device_ratio() -> float:
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    return max(ratio, 2.0)  # at least 2x, so icons stay sharp when Qt scales them


def pixmap(name: str, color: str = tokens.TEXT_SECONDARY, size: int = 20) -> QPixmap:
    # Not cached on purpose: pixmaps held in a module-level cache outlive
    # the QApplication at interpreter exit, which can crash on teardown.
    ratio = _device_ratio()
    image = QPixmap(round(size * ratio), round(size * ratio))
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(_svg(name, color)).render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()
    image.setDevicePixelRatio(ratio)
    return image


def icon(
    name: str,
    color: str = tokens.TEXT_SECONDARY,
    *,
    checked_color: str | None = None,
    size: int = 20,
) -> QIcon:
    """An icon in `color`; with `checked_color`, checkable buttons (like the
    sidebar's) switch to that colour while checked.
    """
    result = QIcon()
    result.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(pixmap(name, color, size), QIcon.Mode.Active, QIcon.State.Off)
    if checked_color:
        on = pixmap(name, checked_color, size)
        result.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
        result.addPixmap(on, QIcon.Mode.Active, QIcon.State.On)
    return result


def names() -> list[str]:
    return sorted(_PATHS)
