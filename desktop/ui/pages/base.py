"""Base class for the screens hosted by the app shell."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget


class Page(QWidget):
    """A screen in the shell. The shell shows `title`/`subtitle` in its
    header and calls refresh() every time the page is shown, so figures are
    never stale after work done on another page.
    """

    title = ""
    subtitle = ""
    # Ask the shell to switch pages: (page key, optional patient_id to open).
    navigate = pyqtSignal(str, object)

    def refresh(self) -> None:
        """Reload data from the database. Override in pages that show data."""
