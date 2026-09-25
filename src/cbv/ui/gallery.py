"""Window-filling thumbnail gallery, shown on request."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem, QWidget

from ..core.book import Book
from .overlay import Overlay
from .pipeline import RenderPipeline

_THUMB = QSize(200, 280)  # logical pixels: box each thumbnail is fitted into
_CELL_MIN_WIDTH = 220
_CELL_HEIGHT = 322


class Gallery(Overlay):
    def __init__(self, parent: QWidget, book: Book, pipeline: RenderPipeline, current: int) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.book = book
        self.dpr = self.devicePixelRatioF()

        self.list = QListWidget(self)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the overlay handles the keys
        self._columns = 1
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setWrapping(True)
        self.list.setIconSize(_THUMB)
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setStyleSheet(
            "QListWidget { background: transparent; color: #9a9a9a; font-size: 12px; outline: 0; }"
            "QListWidget::item { border-radius: 4px; padding: 4px; }"
            "QListWidget::item:selected { background: rgba(255,255,255,45); color: white; }"
            "QScrollBar:vertical { width: 10px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,70); border-radius: 5px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )

        blank = QPixmap(_THUMB)
        blank.fill(QColor(30, 30, 30))
        self._blank = QIcon(blank)
        for page in range(book.count):
            item = QListWidgetItem(self._blank, str(page + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.list.addItem(item)
            if (image := pipeline.thumbnail(page)) is not None:
                self._set_thumb(page, image)
        self.list.setCurrentRow(current)
        self.list.itemActivated.connect(lambda item: self.page_chosen.emit(self.list.row(item)))
        self.list.itemClicked.connect(lambda item: self.page_chosen.emit(self.list.row(item)))

        pipeline.thumb_ready.connect(self._on_thumb_ready)
        box = (round(_THUMB.width() * self.dpr), round(_THUMB.height() * self.dpr))
        order = sorted(range(book.count), key=lambda i: (abs(i - current), i))
        pipeline.request_thumbnails(order, box)
        self._layout()
        self.list.scrollToItem(self.list.item(current), QAbstractItemView.ScrollHint.PositionAtCenter)

    def _set_thumb(self, page: int, image) -> None:
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(self.dpr)
        self.list.item(page).setIcon(QIcon(pixmap))

    def _on_thumb_ready(self, page: int) -> None:
        image = self.pipeline.thumbnail(page)
        if image is not None and 0 <= page < self.list.count():
            self._set_thumb(page, image)

    def _layout(self) -> None:
        margin = 24
        self.list.setGeometry(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        usable = max(1, self.list.viewport().width() - 12)
        self._columns = max(1, usable // _CELL_MIN_WIDTH)
        self.list.setGridSize(QSize(usable // self._columns, _CELL_HEIGHT))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout()

    def _select(self, row: int) -> None:
        row = max(0, min(self.list.count() - 1, row))
        self.list.setCurrentRow(row)
        self.list.scrollToItem(self.list.item(row), QAbstractItemView.ScrollHint.EnsureVisible)

    def _row_down(self, row: int) -> int:
        target = row + self._columns
        if target < self.list.count():
            return target
        last = self.list.count() - 1
        return last if row // self._columns < last // self._columns else row

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Same keys as the page view; they move the highlight, Enter opens the page.
        Left/Right/Up/Down follow the on-screen grid."""
        key = event.key()
        row = self.list.currentRow()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        K = Qt.Key
        if key == K.Key_Escape:
            self.closed.emit()
        elif key in (K.Key_Return, K.Key_Enter):
            self.page_chosen.emit(row)
        elif key == K.Key_Space:
            self._select(row - 1 if shift else row + 1)
        elif key in (K.Key_Backspace, K.Key_Left):
            self._select(row - 1)
        elif key == K.Key_Right:
            self._select(row + 1)
        elif key == K.Key_Up:
            self._select(row - self._columns if row >= self._columns else row)
        elif key == K.Key_Down:
            self._select(self._row_down(row))
        elif key == K.Key_Home:
            self._select(0)
        elif key == K.Key_End:
            self._select(self.list.count() - 1)
        else:
            super().keyPressEvent(event)

    def dispose(self) -> None:
        self.pipeline.cancel_thumbnails()
        try:
            self.pipeline.thumb_ready.disconnect(self._on_thumb_ready)
        except TypeError:
            pass
