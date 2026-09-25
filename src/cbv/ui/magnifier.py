"""The zoom bubble: a round lens that magnifies the area around the pointer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from ..render.layout import Placement

MIN_ZOOM = 1.25
MAX_ZOOM = 10.0
START_ZOOM = 2.0
ZOOM_PER_NOTCH = 1.2
# Lens diameter at START_ZOOM, as a fraction of the shorter window side. The bubble is
# not sized independently: its diameter is proportional to the zoom factor.
START_SIZE = 0.38
_RING = QColor(255, 255, 255, 190)


class Magnifier:
    """State and painting of the lens. Coordinates are device pixels unless noted."""

    def __init__(self) -> None:
        self.active = False
        self.zoom = START_ZOOM
        self.pos: QPointF | None = None  # device pixels

    def dismiss(self) -> None:
        self.active = False
        self.pos = None

    def move(self, pos: QPointF) -> None:
        self.pos = pos

    def wheel(self, delta: int, pos: QPointF) -> None:
        """One zoom step: 120 units = one notch. Zooming out below the minimum
        closes the bubble."""
        notches = delta / 120
        self.pos = pos
        if not self.active:
            if delta > 0:
                self.active = True
                self.zoom = START_ZOOM
            return
        self.zoom = min(MAX_ZOOM, self.zoom * ZOOM_PER_NOTCH**notches)
        if self.zoom < MIN_ZOOM:
            self.dismiss()

    def diameter(self, window: tuple[int, int]) -> float:
        """The bubble grows in proportion to the zoom, so zooming in enlarges the same
        area of the page. There is deliberately no upper limit (the zoom range bounds
        it): the window edge clips the bubble."""
        return START_SIZE * self.zoom / START_ZOOM * min(window)

    def lens_rect(self, window: tuple[int, int]) -> QRectF | None:
        if not self.active or self.pos is None:
            return None
        r = self.diameter(window) / 2
        return QRectF(self.pos.x() - r, self.pos.y() - r, 2 * r, 2 * r)

    def dirty_rect(self, window: tuple[int, int], dpr: float) -> QRect | None:
        """Logical (device-independent) rectangle covering the lens plus its ring."""
        lens = self.lens_rect(window)
        if lens is None:
            return None
        pad = 4
        return QRect(
            int(lens.x() / dpr) - pad,
            int(lens.y() / dpr) - pad,
            int(lens.width() / dpr) + 2 * pad,
            int(lens.height() / dpr) + 2 * pad,
        )

    def paint(
        self,
        painter: QPainter,
        window: tuple[int, int],
        placements: Sequence[Placement],
        images: Mapping[int, QImage],
    ) -> None:
        """Draw the lens; ``images`` maps page -> the best available image of it
        (full resolution when decoded, else the displayed one)."""
        lens = self.lens_rect(window)
        if lens is None or self.pos is None:
            return
        c = self.pos
        half = lens.width() / 2 / self.zoom
        region = QRectF(c.x() - half, c.y() - half, 2 * half, 2 * half)

        painter.save()
        clip = QPainterPath()
        clip.addEllipse(lens)
        painter.setClipPath(clip)
        painter.fillRect(lens, QColor(0, 0, 0))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for pl in placements:
            image = images.get(pl.page)
            visible = region.intersected(QRectF(pl.x, pl.y, pl.w, pl.h))
            if image is None or visible.isEmpty():
                continue
            sx, sy = image.width() / pl.w, image.height() / pl.h
            source = QRectF(
                (visible.x() - pl.x) * sx,
                (visible.y() - pl.y) * sy,
                visible.width() * sx,
                visible.height() * sy,
            )
            target = QRectF(
                c.x() + (visible.x() - c.x()) * self.zoom,
                c.y() + (visible.y() - c.y()) * self.zoom,
                visible.width() * self.zoom,
                visible.height() * self.zoom,
            )
            painter.drawImage(target, image, source)
        painter.restore()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(_RING, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(lens.adjusted(1, 1, -1, -1))
        painter.restore()
