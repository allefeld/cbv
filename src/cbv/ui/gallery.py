"""Window-filling thumbnail gallery, shown on request."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ..core.book import Book
from .overlay import Overlay
from .pipeline import RenderPipeline

_THUMB = QSize(200, 280)  # logical pixels: box each thumbnail is fitted into
_CELL_MIN_WIDTH = 220
_PAD = 8
_GAP = 6  # between the thumbnail and its number
_CAPTION_HEIGHT = 22
_CELL_HEIGHT = _PAD + _THUMB.height() + _GAP + _CAPTION_HEIGHT + _PAD
_THUMB_ROLE = Qt.ItemDataRole.UserRole  # the item's QPixmap (None until it is made)
_CAPTION = QColor(154, 154, 154)
_CAPTION_SELECTED = QColor(255, 255, 255)
_HIGHLIGHT = QColor(255, 255, 255, 45)
_PLACEHOLDER = QColor(30, 30, 30)


def cell_layout(cell: QRect, thumb: QSize) -> tuple[QRect, QRect]:
    """Where to draw a thumbnail of logical size ``thumb`` and its caption in ``cell``.

    Independent of Qt's icon/text layout so that pages of any size are laid out the same:
    the thumbnail is fitted into a fixed box, centred horizontally and aligned to the box's
    bottom, and the caption always sits in its own strip below that box, so the two can never
    overlap."""
    box = QRect(
        cell.x() + (cell.width() - _THUMB.width()) // 2, cell.y() + _PAD, _THUMB.width(), _THUMB.height()
    )
    fitted = thumb.scaled(_THUMB, Qt.AspectRatioMode.KeepAspectRatio) if not thumb.isEmpty() else QSize()
    rect = QRect(
        QPoint(box.x() + (box.width() - fitted.width()) // 2, box.bottom() + 1 - fitted.height()), fitted
    )
    caption = QRect(cell.x(), box.bottom() + 1 + _GAP, cell.width(), _CAPTION_HEIGHT)
    return rect, caption


class _ThumbDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(_CELL_MIN_WIDTH, _CELL_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        cell: QRect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        pixmap = index.data(_THUMB_ROLE)
        logical = pixmap.deviceIndependentSize().toSize() if isinstance(pixmap, QPixmap) else _THUMB
        thumb_rect, caption_rect = cell_layout(cell, logical)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_HIGHLIGHT)
            painter.drawRoundedRect(cell.adjusted(4, 4, -4, -4), 6, 6)
        if isinstance(pixmap, QPixmap):
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(thumb_rect, pixmap)
        else:
            painter.fillRect(thumb_rect, _PLACEHOLDER)
        painter.setPen(_CAPTION_SELECTED if selected else _CAPTION)
        painter.drawText(caption_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, str(index.data()))
        painter.restore()


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
        self.list.setItemDelegate(_ThumbDelegate(self.list))
        self._wheel_accum = 0
        self.list.viewport().installEventFilter(self)
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setStyleSheet(
            "QListWidget { background: transparent; font-size: 12px; outline: 0; }"
            "QScrollBar:vertical { width: 10px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,70); border-radius: 5px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )

        for page in range(book.count):
            self.list.addItem(QListWidgetItem(str(page + 1)))
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
        self.list.item(page).setData(_THUMB_ROLE, pixmap)

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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """One wheel notch scrolls exactly one row of thumbnails."""
        if obj is self.list.viewport() and event.type() == QEvent.Type.Wheel:
            self._wheel_accum += event.angleDelta().y()
            while abs(self._wheel_accum) >= 120:  # touchpads deliver small deltas: accumulate
                direction = 1 if self._wheel_accum < 0 else -1  # wheel down scrolls down
                self._wheel_accum += 120 * direction
                self._scroll_rows(direction)
            return True
        return super().eventFilter(obj, event)

    def _scroll_rows(self, rows: int) -> None:
        bar = self.list.verticalScrollBar()
        height = self.list.gridSize().height() or _CELL_HEIGHT
        target = (round(bar.value() / height) + rows) * height  # stay aligned to whole rows
        bar.setValue(max(bar.minimum(), min(bar.maximum(), target)))

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
