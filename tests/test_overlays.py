from __future__ import annotations

import datetime as dt

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from cbv.metadata.model import Metadata
from cbv.ui.gallery import Gallery
from cbv.ui.info_overlay import InfoOverlay, human_size, info_rows

from .conftest import png_bytes
from .test_viewer import book6, open_and_show, pump, viewer  # noqa: F401


def test_info_rows_omit_empty_fields_and_format_series(tmp_path):
    meta = Metadata(
        title="T", series="S", series_index=4.0, series_count=12, authors=["A", "B"],
        date=dt.date(2001, 2, 3), description="line1\nline2",
    )  # fmt: skip
    book = tmp_path / "b.cbz"
    book.write_bytes(b"x" * 2048)
    rows = dict(info_rows(meta, str(book), 25))
    assert rows["Series"] == "S #4 of 12"
    assert rows["Authors"] == "A, B"
    assert rows["Published"] == "2001-02-03"
    assert rows["Pages"] == "25"
    assert rows["File"] == "b.cbz (2.0 KB)"
    assert "Publisher" not in rows and "Tags" not in rows


def test_human_size():
    assert human_size(10) == "10 B"
    assert human_size(3 * 1024 * 1024) == "3.0 MB"


def test_info_opens_with_pgup_and_any_key_closes(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 500, 900)
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Q, Qt.Key.Key_F, Qt.Key.Key_Escape, Qt.Key.Key_Right):
        QTest.keyClick(viewer, Qt.Key.Key_PageUp)
        assert isinstance(viewer._overlay, InfoOverlay)
        assert viewer._overlay.geometry() == viewer.rect()
        QTest.keyClick(viewer._overlay, key)
        assert viewer._overlay is None, key
    assert viewer.page == 0  # the closing key was consumed, not executed
    assert viewer.isVisible()  # ...so Q did not quit


def test_info_ignores_modifier_keys(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 500, 900)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    QTest.keyClick(viewer._overlay, Qt.Key.Key_Shift)
    QTest.keyClick(viewer._overlay, Qt.Key.Key_Control)
    assert isinstance(viewer._overlay, InfoOverlay)


def test_info_pgup_toggles_and_pgdn_switches_to_gallery(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 500, 900)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    assert viewer._overlay is None
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    assert isinstance(viewer._overlay, Gallery)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    assert isinstance(viewer._overlay, InfoOverlay)


def test_info_left_click_closes_but_right_click_does_not(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 500, 900)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    view = viewer._overlay.browser.viewport()
    QTest.mouseClick(view, Qt.MouseButton.RightButton, pos=view.rect().center())
    assert isinstance(viewer._overlay, InfoOverlay)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=view.rect().center())
    assert viewer._overlay is None and viewer.page == 0


def test_info_left_click_outside_panel_closes(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 900, 900)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    QTest.mouseClick(viewer._overlay, Qt.MouseButton.LeftButton, pos=viewer._overlay.rect().topLeft() + QPoint(3, 3))
    assert viewer._overlay is None


def test_navigation_keys_do_not_leak_through_gallery(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 900, 700)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    QTest.keyClick(viewer._overlay, Qt.Key.Key_Down)  # moves the highlight, not zoom
    assert viewer.page == 0 and not viewer.magnifier.active
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer._overlay is None


def test_gallery_shows_thumbnails_and_jumps(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 900, 700)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    gallery = viewer._overlay
    assert isinstance(gallery, Gallery)
    assert gallery.list.count() == 6
    assert pump(qapp, lambda: all(viewer.pipeline.thumbnail(i) is not None for i in range(6)))
    assert gallery.list.currentRow() == 0
    QTest.keyClick(gallery, Qt.Key.Key_Right)
    QTest.keyClick(gallery, Qt.Key.Key_Right)
    assert gallery.list.currentRow() == 2
    QTest.keyClick(gallery, Qt.Key.Key_Return)
    assert viewer._overlay is None and viewer.page == 2


def test_gallery_escape_keeps_page(qapp, viewer, book6):  # noqa: F811
    open_and_show(qapp, viewer, book6, 900, 700, page=3)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    assert viewer._overlay.list.currentRow() == 3
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer._overlay is None and viewer.page == 3


def test_bookmarks_listed_as_contents(qapp, viewer, make_zip):  # noqa: F811
    xml = b'<ComicInfo><Pages><Page Image="1" Bookmark="Act II"/></Pages></ComicInfo>'
    path = make_zip("bm", {"ComicInfo.xml": xml, "1.png": png_bytes(), "2.png": png_bytes()})
    open_and_show(qapp, viewer, path, 500, 900)
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    html = viewer._overlay.browser.toHtml()
    assert "Act II" in html and "cbv-page:1" in html
    viewer._overlay._on_link(__import__("PyQt6.QtCore", fromlist=["QUrl"]).QUrl("cbv-page:1"))
    assert viewer.page == 1 and viewer._overlay is None


def test_pointer_stays_visible_over_overlays_in_fullscreen(qapp, viewer, book6, monkeypatch):  # noqa: F811
    from PyQt6.QtCore import Qt as _Qt

    open_and_show(qapp, viewer, book6, 900, 700)
    monkeypatch.setattr(viewer, "isFullScreen", lambda: True)
    viewer.setCursor(_Qt.CursorShape.BlankCursor)  # what the idle timer does
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    assert viewer._overlay.cursor().shape() == _Qt.CursorShape.ArrowCursor
    assert viewer.cursor().shape() == _Qt.CursorShape.ArrowCursor
    viewer._hide_cursor()  # the idle timer firing must not hide it again
    assert viewer.cursor().shape() == _Qt.CursorShape.ArrowCursor
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    assert viewer._cursor_timer.isActive()  # auto-hide resumes after the overlay


def test_page_indicator_only_in_fullscreen_while_pointer_visible(qapp, viewer, book6, monkeypatch):  # noqa: F811
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtGui import QMouseEvent

    open_and_show(qapp, viewer, book6, 1600, 900)
    hud = viewer._hud
    assert hud.isHidden()  # windowed: the title bar shows the page

    monkeypatch.setattr(viewer, "isFullScreen", lambda: True)
    viewer._update_hud()
    assert not hud.isHidden() and hud.text() == "1 / 6"
    assert (hud.x(), hud.y()) == (14, 14)  # upper left corner

    QTest.keyClick(viewer, Qt.Key.Key_Space)
    assert hud.text() == "2–3 / 6"

    viewer._hide_cursor()  # idle timeout blanks the pointer...
    assert hud.isHidden()  # ...and the indicator goes with it
    move = QMouseEvent(
        QEvent.Type.MouseMove, QPointF(50, 50), _Qt.MouseButton.NoButton,
        _Qt.MouseButton.NoButton, _Qt.KeyboardModifier.NoModifier,
    )  # fmt: skip
    viewer.mouseMoveEvent(move)  # moving the mouse brings both back
    assert not hud.isHidden()

    QTest.keyClick(viewer, Qt.Key.Key_PageUp)  # overlay open: indicator hidden
    assert hud.isHidden()
    QTest.keyClick(viewer._overlay, Qt.Key.Key_Escape)  # any key closes the info screen
    assert viewer._overlay is None and not hud.isHidden()


def keys(widget, *seq):
    for k in seq:
        mods = Qt.KeyboardModifier.NoModifier
        if isinstance(k, tuple):
            k, mods = k
        QTest.keyClick(widget, k, mods)


def test_gallery_keys_match_page_view_and_up_down_move_by_row(qapp, viewer, make_zip):  # noqa: F811
    K = Qt.Key
    path = make_zip("many", {f"{i:02d}.png": png_bytes((200, 300)) for i in range(1, 21)})
    open_and_show(qapp, viewer, path, 1100, 700)
    QTest.keyClick(viewer, K.Key_PageDown)
    g = viewer._overlay
    cols = g._columns
    assert cols >= 3
    row = lambda: g.list.currentRow()  # noqa: E731

    keys(g, K.Key_Space, K.Key_Space)
    assert row() == 2
    keys(g, (K.Key_Space, Qt.KeyboardModifier.ShiftModifier))
    assert row() == 1
    keys(g, K.Key_Backspace)
    assert row() == 0
    keys(g, K.Key_Left)
    assert row() == 0  # clamps at the start
    keys(g, K.Key_Right)
    assert row() == 1
    keys(g, K.Key_Down)
    assert row() == 1 + cols
    keys(g, K.Key_Up)
    assert row() == 1
    keys(g, K.Key_Up)
    assert row() == 1  # already in the first row
    keys(g, K.Key_End)
    assert row() == 19
    keys(g, K.Key_Down)
    assert row() == 19
    keys(g, K.Key_Home)
    assert row() == 0
    # Down from a full row into a shorter last row lands on the last item
    last_row_start = (19 // cols) * cols
    g.list.setCurrentRow(last_row_start - 1)
    keys(g, K.Key_Down)
    assert row() == min(last_row_start - 1 + cols, 19)
    assert viewer.page == 0 and not viewer.magnifier.active  # nothing leaked to the page view


def test_gallery_navigation_scrolls_current_item_into_view(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("many", {f"{i:02d}.png": png_bytes((200, 300)) for i in range(1, 61)})
    open_and_show(qapp, viewer, path, 1100, 500)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    g = viewer._overlay
    QTest.keyClick(g, Qt.Key.Key_End)
    qapp.processEvents()
    item_rect = g.list.visualItemRect(g.list.item(59))
    assert g.list.viewport().rect().intersects(item_rect)


def test_info_description_keeps_basic_formatting(qapp, viewer, tmp_path, make_zip):  # noqa: F811
    from cbv.ui.info_overlay import info_html

    opf = (
        b"<?xml version='1.0'?><package xmlns='http://www.idpf.org/2007/opf' version='2.0'>"
        b"<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title>T</dc:title>"
        b"<dc:description>&lt;p&gt;An &lt;i&gt;odd&lt;/i&gt; tale&lt;/p&gt;"
        b"&lt;script&gt;x()&lt;/script&gt;&lt;p&gt;2nd &amp;amp; last&lt;/p&gt;</dc:description>"
        b"</metadata></package>"
    )
    (tmp_path / "metadata.opf").write_bytes(opf)
    path = make_zip("d", {"1.png": png_bytes()})
    open_and_show(qapp, viewer, path, 500, 900)
    html = info_html(viewer.book)
    assert "<p>An <i>odd</i> tale</p><p>2nd &amp; last</p>" in html
    assert "<script" not in html and "x()" not in html
    QTest.keyClick(viewer, Qt.Key.Key_PageUp)
    assert "font-style:italic" in viewer._overlay.browser.toHtml()


def test_cell_layout_never_overlaps_caption_and_thumbnail():
    from PyQt6.QtCore import QRect, QSize

    from cbv.ui.gallery import _CELL_HEIGHT, _CELL_MIN_WIDTH, _THUMB, cell_layout

    cell = QRect(50, 300, 260, _CELL_HEIGHT)
    baselines = set()
    sizes = [(200, 280), (200, 100), (60, 280), (200, 200), (1, 1), (900, 300), (150, 4000), (0, 0)]
    for w, h in sizes:
        thumb, caption = cell_layout(cell, QSize(w, h))
        assert not thumb.intersects(caption), (w, h)
        assert cell.contains(caption) and (thumb.isEmpty() or cell.contains(thumb)), (w, h)
        assert thumb.width() <= _THUMB.width() and thumb.height() <= _THUMB.height()
        assert thumb.bottom() < caption.top()  # the number is below the thumbnail
        baselines.add((caption.top(), caption.height()))
        if not thumb.isEmpty():  # thumbnails are aligned to the box bottom, centred horizontally
            assert thumb.bottom() == cell.y() + 8 + _THUMB.height() - 1
            assert abs((thumb.center().x() - cell.center().x())) <= 1
    assert len(baselines) == 1  # captions are on one line whatever the page sizes
    assert _CELL_MIN_WIDTH >= _THUMB.width()


def test_gallery_with_mixed_page_sizes_has_uniform_cells(qapp, viewer, make_zip):  # noqa: F811
    pages = {
        "1.png": png_bytes((200, 300)), "2.png": png_bytes((600, 200)),
        "3.png": png_bytes((100, 500)), "4.png": png_bytes((300, 300)),
    }  # fmt: skip
    open_and_show(qapp, viewer, make_zip("mixed", pages), 900, 700)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    g = viewer._overlay
    assert pump(qapp, lambda: all(viewer.pipeline.thumbnail(i) is not None for i in range(4)))
    qapp.processEvents()
    rects = [g.list.visualItemRect(g.list.item(i)) for i in range(4)]
    assert len({r.height() for r in rects}) == 1  # every cell has the same height
    row = g.list.gridSize().height()
    cols = g._columns
    assert [r.top() for r in rects] == [(i // cols) * row for i in range(4)]  # a regular grid


def scroll_wheel(widget, delta: int) -> None:
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QApplication

    pos = QPointF(widget.rect().center())
    QApplication.sendEvent(
        widget,
        QWheelEvent(
            pos, pos, QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
        ),
    )  # fmt: skip


def test_gallery_wheel_notch_scrolls_exactly_one_row(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("many", {f"{i:02d}.png": png_bytes((200, 300)) for i in range(1, 81)})
    open_and_show(qapp, viewer, path, 1100, 500)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    g = viewer._overlay
    bar, view = g.list.verticalScrollBar(), g.list.viewport()
    row = g.list.gridSize().height()
    assert bar.maximum() > 3 * row
    bar.setValue(0)
    scroll_wheel(view, -120)  # wheel down
    assert bar.value() == row
    scroll_wheel(view, -120)
    scroll_wheel(view, -120)
    assert bar.value() == 3 * row
    scroll_wheel(view, 120)  # wheel up
    assert bar.value() == 2 * row
    for _ in range(5):
        scroll_wheel(view, 120)
    assert bar.value() == 0  # clamps at the top
    for _ in range(200):
        scroll_wheel(view, -120)
    assert bar.value() == bar.maximum()  # ...and at the bottom


def test_gallery_wheel_snaps_to_rows_and_accumulates_touchpad_deltas(qapp, viewer, make_zip):  # noqa: F811
    path = make_zip("many", {f"{i:02d}.png": png_bytes((200, 300)) for i in range(1, 81)})
    open_and_show(qapp, viewer, path, 1100, 500)
    QTest.keyClick(viewer, Qt.Key.Key_PageDown)
    g = viewer._overlay
    bar, view = g.list.verticalScrollBar(), g.list.viewport()
    row = g.list.gridSize().height()
    bar.setValue(row + 37)  # mid-row, e.g. after keyboard navigation
    scroll_wheel(view, -120)
    assert bar.value() == 2 * row  # snaps to a whole row
    bar.setValue(0)
    for _ in range(3):
        scroll_wheel(view, -40)  # three small touchpad ticks make one notch
    assert bar.value() == row
