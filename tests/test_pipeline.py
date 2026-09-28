from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage

from cbv.core.book import Book
from cbv.ui import pipeline as pipeline_module
from cbv.ui.pipeline import RenderPipeline, pil_to_qimage

from .conftest import png_bytes


def qimage(w=100, h=100) -> QImage:
    return QImage(w, h, QImage.Format.Format_RGB32)


@pytest.fixture
def pipeline(qapp, make_zip):
    book = Book(make_zip("p", {f"{i}.png": png_bytes() for i in range(1, 5)}))
    p = RenderPipeline(book)
    yield p
    p.close()
    book.close()


def actual_bytes(p: RenderPipeline) -> int:
    return sum(img.sizeInBytes() for img in p._cache.values())


def test_duplicate_deliveries_do_not_inflate_the_byte_count(pipeline):
    for _ in range(50):
        pipeline._on_scaled(0, 100, 100, qimage())
    assert len(pipeline._cache) == 1
    assert pipeline._cache_bytes == actual_bytes(pipeline)


def test_images_on_screen_survive_duplicate_deliveries(pipeline, monkeypatch):
    """Regression: duplicate renders used to leave the byte counter above the limit for
    good, so every later delivery evicted the images currently displayed."""
    one = qimage().sizeInBytes()
    monkeypatch.setattr(pipeline_module, "_CACHE_LIMIT", one * 4)
    pipeline._on_scaled(0, 100, 100, qimage())  # left page
    pipeline._on_scaled(1, 100, 100, qimage())  # right page
    for _ in range(20):  # e.g. re-requested after fast navigation
        pipeline._on_scaled(1, 100, 100, qimage())
        pipeline._on_scaled(0, 100, 100, qimage())
    assert pipeline.image(0, 100, 100) is not None and pipeline.image(1, 100, 100) is not None
    assert pipeline._cache_bytes == actual_bytes(pipeline)


def test_eviction_still_respects_the_limit_and_keeps_recent(pipeline, monkeypatch):
    one = qimage().sizeInBytes()
    monkeypatch.setattr(pipeline_module, "_CACHE_LIMIT", one * 2)
    for page in range(4):
        pipeline._on_scaled(page, 100, 100, qimage())
    assert pipeline._cache_bytes == actual_bytes(pipeline) <= one * 2
    assert pipeline.image(3, 100, 100) is not None and pipeline.image(0, 100, 100) is None


def test_any_image_counts_as_use(pipeline, monkeypatch):
    one = qimage().sizeInBytes()
    monkeypatch.setattr(pipeline_module, "_CACHE_LIMIT", one * 2)
    pipeline._on_scaled(0, 100, 100, qimage())
    pipeline._on_scaled(1, 100, 100, qimage())
    assert pipeline.any_image(0) is not None  # touch page 0: page 1 is now the oldest
    pipeline._on_scaled(2, 100, 100, qimage())
    assert pipeline.image(0, 100, 100) is not None and pipeline.image(1, 100, 100) is None


def test_pil_to_qimage_colours_and_format():
    from PIL import Image

    im = Image.new("RGB", (3, 2), (10, 20, 30))
    im.putpixel((2, 1), (200, 100, 50))
    q = pil_to_qimage(im)
    assert q.format() == QImage.Format.Format_RGB32 and (q.width(), q.height()) == (3, 2)
    assert q.pixelColor(0, 0).getRgb()[:3] == (10, 20, 30)
    assert q.pixelColor(2, 1).getRgb()[:3] == (200, 100, 50)


def test_closing_a_book_with_signals_in_flight_does_not_crash(qapp, make_zip):
    """Regression: a lambda slot on the pipeline's `probed` signal ran after the pipeline had
    been deleted (queued signals outlive close()) and crashed the process."""
    from PyQt6.QtCore import QCoreApplication, QEvent

    from cbv.state import StateStore
    from cbv.ui.viewer import Viewer

    path = make_zip("many", {f"{i:02d}.png": png_bytes((60, 90)) for i in range(1, 30)})
    for _ in range(25):
        viewer = Viewer(StateStore(Path(tempfile.mkdtemp()) / "s.json"))
        viewer.resize(500, 700)
        assert viewer.open_path(path)
        viewer.show()
        qapp.processEvents()  # let probe results start arriving
        viewer.close()  # closes the book while more are queued
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
