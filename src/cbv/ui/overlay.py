"""Base class for full-window overlays (info, gallery) shown on request."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

SCRIM = QColor(0, 0, 0, 246)


class Overlay(QWidget):
    """Covers its parent completely; closed with Esc (handled by the viewer)."""

    closed = pyqtSignal()
    page_chosen = pyqtSignal(int)
    #: If true the viewer disables all its shortcuts (except the info/gallery keys)
    #: while this overlay is open, so that any key press reaches the overlay.
    captures_all_keys = False

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setGeometry(parent.rect())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event) -> None:  # noqa: N802
        QPainter(self).fillRect(self.rect(), SCRIM)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()  # never let clicks fall through to the page below

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()
