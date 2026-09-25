from __future__ import annotations

import sys

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication, QFileDialog

from ..state import StateStore
from .viewer import _OPEN_FILTER, Viewer


def run(path: str | None, fullscreen: bool = False, page: int | None = None) -> int:
    app = QApplication(sys.argv[:1])
    app.setApplicationName("cbv")
    app.setDesktopFileName("cbv")
    if path is None:
        path, _ = QFileDialog.getOpenFileName(None, "Open comic book", "", _OPEN_FILTER)
        if not path:
            return 0
    viewer = Viewer(StateStore())
    screen = app.primaryScreen().availableGeometry()
    w, h = int(screen.width() * 0.8), int(screen.height() * 0.85)
    viewer.setGeometry(QRect(screen.x() + (screen.width() - w) // 2, screen.y() + (screen.height() - h) // 2, w, h))
    if not viewer.open_path(path, None if page is None else page - 1):
        return 1
    viewer.showFullScreen() if fullscreen else viewer.show()
    return app.exec()
