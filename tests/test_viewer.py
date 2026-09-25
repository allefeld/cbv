from __future__ import annotations

import time
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from cbv.state import StateStore
from cbv.ui.viewer import Viewer

from .conftest import png_bytes


def pump(qapp, until=lambda: False, timeout=5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if until():
            return True
        time.sleep(0.005)
    return until()


def displayed(viewer: Viewer) -> bool:
    """All images for the current view are rendered at their exact size."""
    from cbv.render.layout import place

    group = viewer._current_group()
    pls = place(group, viewer.book.sizes(), viewer._device_size(), viewer.rtl)
    return bool(pls) and all(viewer.pipeline.image(p.page, p.w, p.h) for p in pls)


@pytest.fixture
def book6(make_zip):
    pages = {f"p{i:02d}.png": png_bytes((200, 300)) for i in range(1, 7)}
    return make_zip("six", pages)


@pytest.fixture
def viewer(qapp, tmp_path: Path):
    v = Viewer(StateStore(tmp_path / "state.json"))
    yield v
    v.close()


def open_and_show(qapp, v: Viewer, path: str, w: int, h: int, **kw) -> None:
    v.resize(w, h)
    assert v.open_path(path, **kw)
    v.show()
    assert pump(qapp, lambda: displayed(v)), "page never rendered"


def test_wide_window_shows_pairs_with_cover_alone(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 1600, 900)
    assert viewer.windowTitle().endswith("1 / 6")
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert viewer.windowTitle().endswith("2–3 / 6")
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert viewer.windowTitle().endswith("4–5 / 6")
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert viewer.windowTitle().endswith("6 / 6")
    QTest.keyClick(viewer, Qt.Key.Key_Space)  # already last
    assert viewer.windowTitle().endswith("6 / 6")
    QTest.keyClick(viewer, Qt.Key.Key_Backspace)
    assert viewer.windowTitle().endswith("4–5 / 6")


def test_narrow_window_shows_single_pages(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 500, 900)
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert viewer.windowTitle().endswith("2 / 6")


def test_arrow_keys_mirror_in_rtl(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 500, 900, page=2)
    QTest.keyClick(viewer, Qt.Key.Key_Right)
    assert viewer.page == 3  # Right is "next" in left-to-right
    QTest.keyClick(viewer, Qt.Key.Key_R)
    assert viewer.rtl
    QTest.keyClick(viewer, Qt.Key.Key_Left)
    assert viewer.page == 4  # Left is "next" in right-to-left
    QTest.keyClick(viewer, Qt.Key.Key_Right)
    assert viewer.page == 3


def test_zero_based_page_argument(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 500, 900, page=0)
    assert viewer.windowTitle().endswith("1 / 6")


def test_click_zones_turn_pages(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 500, 900)
    toggled = []
    viewer.toggle_fullscreen = lambda: toggled.append(True)
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=viewer.rect().center())
    assert viewer.page == 0 and toggled == [True]  # middle third: fullscreen, no page turn
    right = viewer.rect().center().__class__(viewer.width() - 20, 400)
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=right)
    assert viewer.page == 1
    left = right.__class__(20, 400)
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=left)
    assert viewer.page == 0


def test_resize_switches_between_single_and_pair(qapp, viewer, book6):
    open_and_show(qapp, viewer, book6, 500, 900, page=2)
    assert viewer.windowTitle().endswith("3 / 6")
    viewer.resize(1600, 900)
    assert pump(qapp, lambda: viewer.windowTitle().endswith("2–3 / 6") and displayed(viewer))


def test_broken_page_does_not_block_layout(qapp, viewer, make_zip):
    pages = {"1.png": png_bytes((200, 300)), "2.png": b"not an image", "3.png": png_bytes((200, 300))}
    open_and_show(qapp, viewer, make_zip("broken", pages), 500, 900, page=2)
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert viewer.page == 2
    assert viewer.book.is_broken(1)


def test_state_is_remembered_by_book_identity(qapp, tmp_path: Path, book6):
    store = StateStore(tmp_path / "state.json")
    v = Viewer(store)
    open_and_show(qapp, v, book6, 500, 900, page=4)  # 0-based index
    v.toggle_cover_alone()
    v.toggle_rtl()
    v.close()
    v2 = Viewer(StateStore(tmp_path / "state.json"))
    assert v2.open_path(book6)
    assert (v2.page, v2.cover_alone, v2.rtl) == (4, False, True)
    v2.close()


def test_open_error_is_reported_not_raised(qapp, viewer, tmp_path: Path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a))
    bad = tmp_path / "bad.cbz"
    bad.write_bytes(b"garbage" * 100)
    assert not viewer.open_path(str(bad))
    assert shown
