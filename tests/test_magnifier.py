from __future__ import annotations

import io

import pytest
from PIL import Image
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from cbv.ui.magnifier import MAX_ZOOM, MIN_ZOOM, START_ZOOM, Magnifier

from .test_viewer import displayed, open_and_show, pump, viewer  # noqa: F401


def wheel(widget, pos: QPoint, delta: int, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    """Send a mouse wheel event (which turns pages)."""
    event = QWheelEvent(
        QPointF(pos), QPointF(widget.mapToGlobal(pos)), QPoint(), QPoint(0, delta),
        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False,
    )  # fmt: skip
    QApplication.sendEvent(widget, event)


def zoom_in(viewer, pos: QPoint) -> None:
    """Cursor-up with the mouse pointer at ``pos``."""
    viewer._pointer_pos = lambda: QPointF(pos)
    QTest.keyClick(viewer, Qt.Key.Key_Up)


def two_tone_png() -> bytes:
    """Left half red, right half blue."""
    im = Image.new("RGB", (200, 300), (255, 0, 0))
    im.paste((0, 0, 255), (100, 0, 200, 300))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_magnifier_state_machine():
    m = Magnifier()
    m.wheel(-120, QPointF(5, 5))
    assert not m.active  # wheel down while closed does nothing
    m.wheel(120, QPointF(5, 5))
    assert m.active and m.zoom == START_ZOOM
    m.wheel(120, QPointF(6, 6))
    assert m.zoom > START_ZOOM
    for _ in range(50):
        m.wheel(120, QPointF(0, 0))
    assert m.zoom == MAX_ZOOM
    for _ in range(80):
        m.wheel(-120, QPointF(0, 0))
    assert not m.active  # zooming out past the minimum closes the bubble
    assert MIN_ZOOM > 1


@pytest.fixture
def two_tone(make_zip):
    return make_zip("tt", {"1.png": two_tone_png()})


def pixel(viewer, x: int, y: int) -> tuple[int, int, int]:
    c = viewer.grab().toImage().pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def test_bubble_magnifies_around_pointer_and_dismisses(qapp, viewer, two_tone):  # noqa: F811
    open_and_show(qapp, viewer, two_tone, 500, 750)  # page fills the window exactly
    y = 375
    assert pixel(viewer, 240, y) == (255, 0, 0)  # colour boundary is at x = 250

    zoom_in(viewer, QPoint(270, y))
    assert viewer.magnifier.active
    assert pump(qapp, lambda: viewer.pipeline.full_image(0) is not None)
    qapp.processEvents()
    # zoom 2 around x=270: the boundary moves to 270 + (250-270)*2 = 230
    assert pixel(viewer, 240, y) == (0, 0, 255)
    assert pixel(viewer, 220, y) == (255, 0, 0)
    # outside the lens nothing changed
    assert pixel(viewer, 20, y) == (255, 0, 0) and pixel(viewer, 480, y) == (0, 0, 255)

    # the lens follows the pointer
    viewer.magnifier.move(QPointF(240, y))
    viewer.update()
    assert pixel(viewer, 240, y) == (0, 0, 255) or pixel(viewer, 240, y) == (255, 0, 0)

    # a left click only dismisses
    QTest.mouseClick(viewer, Qt.MouseButton.LeftButton, pos=QPoint(470, 300))
    assert not viewer.magnifier.active and viewer.page == 0
    assert pixel(viewer, 240, y) == (255, 0, 0)


def test_escape_dismisses_before_leaving_fullscreen(qapp, viewer, two_tone):  # noqa: F811
    open_and_show(qapp, viewer, two_tone, 500, 750)
    zoom_in(viewer, QPoint(250, 300))
    assert viewer.magnifier.active
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert not viewer.magnifier.active


def test_navigation_dismisses_bubble(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("two", {"1.png": two_tone_png(), "2.png": two_tone_png()})
    open_and_show(qapp, viewer, path, 500, 750)
    zoom_in(viewer, QPoint(250, 300))
    assert viewer.magnifier.active
    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert not viewer.magnifier.active and viewer.page == 1


def test_down_zooms_out_and_closes_bubble(qapp, viewer, two_tone):  # noqa: F811
    open_and_show(qapp, viewer, two_tone, 500, 750)
    zoom_in(viewer, QPoint(250, 300))
    zoom0 = viewer.magnifier.zoom
    QTest.keyClick(viewer, Qt.Key.Key_Up)
    assert viewer.magnifier.zoom > zoom0
    for _ in range(10):
        QTest.keyClick(viewer, Qt.Key.Key_Down)
    assert not viewer.magnifier.active and viewer.page == 0  # Down never turns pages


def test_down_alone_does_not_open_bubble_or_turn_page(qapp, viewer, two_tone):  # noqa: F811
    open_and_show(qapp, viewer, two_tone, 500, 750)
    QTest.keyClick(viewer, Qt.Key.Key_Down)
    assert not viewer.magnifier.active and viewer.page == 0


def test_wheel_turns_pages_and_never_opens_bubble(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("three", {f"{i}.png": two_tone_png() for i in (1, 2, 3)})
    open_and_show(qapp, viewer, path, 500, 750)
    wheel(viewer, QPoint(250, 300), -120)  # wheel down = next
    assert viewer.page == 1 and not viewer.magnifier.active
    wheel(viewer, QPoint(250, 300), -120)
    assert viewer.page == 2
    wheel(viewer, QPoint(250, 300), 120)  # wheel up = previous
    assert viewer.page == 1


def test_wheel_touchpad_deltas_accumulate(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("three", {f"{i}.png": two_tone_png() for i in (1, 2, 3)})
    open_and_show(qapp, viewer, path, 500, 750)
    for _ in range(3):
        wheel(viewer, QPoint(250, 300), -40)
    assert viewer.page == 1  # three 40-unit ticks make one notch


def test_ctrl_wheel_zooms_bubble(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("two", {"1.png": two_tone_png(), "2.png": two_tone_png()})
    open_and_show(qapp, viewer, path, 500, 750)
    viewer._pointer_pos = lambda: QPointF(250, 300)
    ctrl = Qt.KeyboardModifier.ControlModifier
    wheel(viewer, QPoint(250, 300), -120, ctrl)  # zooming out with no bubble: nothing
    assert not viewer.magnifier.active and viewer.page == 0
    wheel(viewer, QPoint(250, 300), 120, ctrl)  # zoom in opens it
    assert viewer.magnifier.active and viewer.page == 0
    zoom = viewer.magnifier.zoom
    wheel(viewer, QPoint(250, 300), 120, ctrl)
    assert viewer.magnifier.zoom > zoom
    for _ in range(10):
        wheel(viewer, QPoint(250, 300), -120, ctrl)
    assert not viewer.magnifier.active and viewer.page == 0


def test_bubble_diameter_is_proportional_to_zoom_without_limit():
    from cbv.ui.magnifier import START_SIZE

    win = (1600, 900)
    m = Magnifier()
    m.wheel(120, QPointF(0, 0))
    assert m.diameter(win) == pytest.approx(START_SIZE * 900)  # initial: 38% of shorter side
    region = m.diameter(win) / m.zoom
    previous = m.diameter(win)
    for _ in range(60):
        m.wheel(120, QPointF(0, 0))
        assert m.diameter(win) >= previous  # never shrinks while zooming in
        assert m.diameter(win) / m.zoom == pytest.approx(region)  # same area, shown larger
        previous = m.diameter(win)
    assert m.zoom == MAX_ZOOM
    assert m.diameter(win) > 1.5 * 900  # no cap: exceeds the window height


def test_ctrl_shift_wheel_with_horizontal_delta_still_zooms(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("two", {"1.png": two_tone_png(), "2.png": two_tone_png()})
    open_and_show(qapp, viewer, path, 500, 750)
    viewer._pointer_pos = lambda: QPointF(250, 300)
    mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    event = QWheelEvent(
        QPointF(250, 300), QPointF(250, 300), QPoint(), QPoint(120, 0),  # horizontal only
        Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False,
    )  # fmt: skip
    QApplication.sendEvent(viewer, event)
    assert viewer.magnifier.active and viewer.page == 0
