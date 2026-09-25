"""Background decoding/scaling of pages, with an image cache and prefetch."""

from __future__ import annotations

import logging
import os
from collections import OrderedDict

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage

from ..core.book import Book
from ..render.decode import decode_full, render

log = logging.getLogger(__name__)

_CACHE_LIMIT = 512 << 20
_FULL_CACHE_PAGES = 4
PRIORITY_VISIBLE = 10
PRIORITY_PREFETCH = 0


def pil_to_qimage(im) -> QImage:
    """RGB PIL image -> QImage in Qt's native 32-bit format (blits without conversion)."""
    w, h = im.size
    data = im.tobytes("raw", "BGRX")  # little-endian 0xffRRGGBB, i.e. Format_RGB32
    image = QImage(data, w, h, w * 4, QImage.Format.Format_RGB32).copy()
    del data  # only after the copy: QImage(data) borrows the buffer
    return image


class _Signals(QObject):
    scaled = pyqtSignal(int, int, int, object)  # page, width, height, QImage | None
    probed = pyqtSignal(int)
    full = pyqtSignal(int, object)  # page, QImage | None
    thumb = pyqtSignal(int, object)  # page, QImage | None


class _ScaleJob(QRunnable):
    def __init__(self, pipeline: RenderPipeline, page: int, w: int, h: int, gen: int) -> None:
        super().__init__()
        self.pipeline, self.page, self.w, self.h, self.gen = pipeline, page, w, h, gen

    def run(self) -> None:
        p = self.pipeline
        image = None
        if self.gen >= p.min_generation and not p.closed:
            try:
                image = pil_to_qimage(render(p.book.page_bytes(self.page), self.w, self.h))
            except Exception:
                log.warning("cannot render page %d at %dx%d", self.page + 1, self.w, self.h, exc_info=True)
                image = None
        p.signals.scaled.emit(self.page, self.w, self.h, image)


class _FullJob(QRunnable):
    def __init__(self, pipeline: RenderPipeline, page: int) -> None:
        super().__init__()
        self.pipeline, self.page = pipeline, page

    def run(self) -> None:
        p = self.pipeline
        image = None
        if not p.closed:
            try:
                image = pil_to_qimage(decode_full(p.book.page_bytes(self.page)))
            except Exception:
                log.warning("cannot decode page %d", self.page + 1, exc_info=True)
                image = None
        p.signals.full.emit(self.page, image)


class _ThumbJob(QRunnable):
    def __init__(self, pipeline: RenderPipeline, page: int, box: tuple[int, int], gen: int) -> None:
        super().__init__()
        self.pipeline, self.page, self.box, self.gen = pipeline, page, box, gen

    def run(self) -> None:
        p = self.pipeline
        image = None
        if self.gen == p.thumb_generation and not p.closed:
            try:
                w, h = p.book.probe(self.page)
                scale = min(self.box[0] / w, self.box[1] / h)
                tw, th = max(1, round(w * scale)), max(1, round(h * scale))
                image = pil_to_qimage(render(p.book.page_bytes(self.page), tw, th))
            except Exception:
                log.warning("cannot make thumbnail of page %d", self.page + 1, exc_info=True)
                image = None
        p.signals.thumb.emit(self.page, image)


class _ProbeJob(QRunnable):
    def __init__(self, pipeline: RenderPipeline, pages: list[int]) -> None:
        super().__init__()
        self.pipeline, self.pages = pipeline, pages

    def run(self) -> None:
        p = self.pipeline
        for page in self.pages:
            if p.closed:
                return
            p.book.probe(page)
            p.signals.probed.emit(page)


class RenderPipeline(QObject):
    """Owns worker threads and the scaled-image cache. Main-thread API only."""

    image_ready = pyqtSignal(int)
    full_ready = pyqtSignal(int)
    thumb_ready = pyqtSignal(int)
    sizes_changed = pyqtSignal()

    def __init__(self, book: Book, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.book = book
        self.closed = False
        self.min_generation = 0
        self._generation = 0
        self.signals = _Signals(self)
        self.signals.scaled.connect(self._on_scaled)
        self.signals.probed.connect(lambda _page: self.sizes_changed.emit())
        self.signals.full.connect(self._on_full)
        self.signals.thumb.connect(self._on_thumb)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, min(4, os.cpu_count() or 2)))
        self._probe_pool = QThreadPool(self)
        self._probe_pool.setMaxThreadCount(1)
        self._thumb_pool = QThreadPool(self)
        self._thumb_pool.setMaxThreadCount(2)
        self.thumb_generation = 0
        self._thumbs: dict[int, QImage] = {}
        self._thumb_box: tuple[int, int] | None = None
        self._cache: OrderedDict[tuple[int, int, int], QImage] = OrderedDict()
        self._cache_bytes = 0
        self._latest: dict[int, tuple[int, int]] = {}
        self._pending: set[tuple[int, int, int]] = set()
        self._full: OrderedDict[int, QImage] = OrderedDict()
        self._full_pending: set[int] = set()
        self._probing: set[int] = set()

    # -- sizes -----------------------------------------------------------
    def start_size_scan(self, first: int) -> None:
        """Probe every page in the background, nearest to ``first`` first."""
        order = sorted(range(self.book.count), key=lambda i: (abs(i - first), i))
        self._probe_pool.start(_ProbeJob(self, order))

    def ensure_sizes(self, pages: list[int]) -> None:
        """High-priority probe of pages needed right now."""
        missing = [p for p in pages if self.book.size(p) is None and p not in self._probing]
        if missing:
            self._probing.update(missing)
            self._pool.start(_ProbeJob(self, missing), PRIORITY_VISIBLE + 1)

    # -- images ----------------------------------------------------------
    def new_generation(self) -> int:
        """Invalidate queued work of earlier generations (e.g. the user moved on)."""
        self._generation += 1
        self.min_generation = self._generation
        self._pending.clear()
        return self._generation

    def image(self, page: int, w: int, h: int) -> QImage | None:
        key = (page, w, h)
        img = self._cache.get(key)
        if img is not None:
            self._cache.move_to_end(key)
        return img

    def any_image(self, page: int) -> QImage | None:
        """Best available image of a page, whatever size (for instant previews)."""
        size = self._latest.get(page)
        if not size:
            return None
        key = (page, *size)
        img = self._cache.get(key)
        if img is not None:
            self._cache.move_to_end(key)  # being displayed: keep it out of eviction's way
        return img

    def request(self, page: int, w: int, h: int, priority: int = PRIORITY_VISIBLE) -> None:
        key = (page, w, h)
        if key in self._cache or key in self._pending or w <= 0 or h <= 0:
            return
        self._pending.add(key)
        self._pool.start(_ScaleJob(self, page, w, h, self._generation), priority)

    def _on_scaled(self, page: int, w: int, h: int, image: object) -> None:
        self._pending.discard((page, w, h))
        if not isinstance(image, QImage) or self.closed:
            return
        key = (page, w, h)
        if key in self._cache:  # a duplicate render (e.g. requested again after navigating)
            self._cache.move_to_end(key)
            self._latest[page] = (w, h)
            return
        self._cache[key] = image
        self._cache_bytes += image.sizeInBytes()
        self._latest[page] = (w, h)
        while self._cache_bytes > _CACHE_LIMIT and len(self._cache) > 1:
            _, old = self._cache.popitem(last=False)
            self._cache_bytes -= old.sizeInBytes()
        self.image_ready.emit(page)

    # -- full-resolution originals (magnifier) ------------------------------
    def full_image(self, page: int) -> QImage | None:
        img = self._full.get(page)
        if img is not None:
            self._full.move_to_end(page)
        return img

    def request_full(self, page: int) -> None:
        if page in self._full or page in self._full_pending:
            return
        self._full_pending.add(page)
        self._pool.start(_FullJob(self, page), PRIORITY_VISIBLE + 2)

    def _on_full(self, page: int, image: object) -> None:
        self._full_pending.discard(page)
        if not isinstance(image, QImage) or self.closed:
            return
        self._full[page] = image
        while len(self._full) > _FULL_CACHE_PAGES:
            self._full.popitem(last=False)
        self.full_ready.emit(page)

    # -- thumbnails (gallery) ------------------------------------------------
    def thumbnail(self, page: int) -> QImage | None:
        return self._thumbs.get(page)

    def request_thumbnails(self, pages: list[int], box: tuple[int, int]) -> None:
        """Queue thumbnails (fit inside ``box`` device pixels), in the given order."""
        if box != self._thumb_box:
            self._thumbs.clear()
            self._thumb_box = box
        self.thumb_generation += 1
        for page in pages:
            if page not in self._thumbs:
                self._thumb_pool.start(_ThumbJob(self, page, box, self.thumb_generation))

    def cancel_thumbnails(self) -> None:
        self.thumb_generation += 1

    def _on_thumb(self, page: int, image: object) -> None:
        if isinstance(image, QImage) and not self.closed:
            self._thumbs[page] = image
            self.thumb_ready.emit(page)

    def close(self) -> None:
        self.closed = True
        self._thumb_pool.clear()
        self._thumb_pool.waitForDone(2000)
        self._pool.clear()
        self._probe_pool.clear()
        self._pool.waitForDone(2000)
        self._probe_pool.waitForDone(2000)
        self._cache.clear()
        self._full.clear()
