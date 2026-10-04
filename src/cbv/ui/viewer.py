"""The viewer window: only the artwork, everything else on request."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QCursor, QDragEnterEvent, QDropEvent, QKeySequence, QPainter
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QLabel, QMenu, QMessageBox, QWidget

from ..archive import ArchiveError
from ..core.book import Book
from ..render.layout import build_groups, group_index, place, two_page_mode, typical_aspect
from ..state import BookState, StateStore
from .gallery import Gallery
from .info_overlay import InfoOverlay
from .magnifier import Magnifier
from .overlay import Overlay
from .pipeline import PRIORITY_PREFETCH, PRIORITY_VISIBLE, RenderPipeline

_BACKGROUND = QColor(0, 0, 0)
_PLACEHOLDER = QColor(28, 28, 28)
_OPEN_FILTER = "Comic books (*.cbz *.cbr *.cb7 *.cbt *.zip *.rar *.7z *.tar);;All files (*)"
_CURSOR_HIDE_MS = 2000
_SAVE_DELAY_MS = 3000
_RESIZE_DEBOUNCE_MS = 90
_HUD_MARGIN = 14
_HUD_STYLE = (
    "QLabel { background: rgba(0, 0, 0, 150); color: rgba(255, 255, 255, 215);"
    " border-radius: 6px; padding: 4px 10px; font-size: 15px; }"
)


class Viewer(QWidget):
    def __init__(self, store: StateStore) -> None:
        super().__init__()
        self.store = store
        self.book: Book | None = None
        self.pipeline: RenderPipeline | None = None
        self.page = 0
        self.cover_alone = True
        self._rtl_override: bool | None = None
        self.magnifier = Magnifier()
        self._wheel_accum = 0
        self._overlay: Overlay | None = None

        self.setWindowTitle("cbv")
        self.setMinimumSize(240, 180)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._resize_timer = QTimer(self, singleShot=True, interval=_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._sync)
        self._save_timer = QTimer(self, singleShot=True, interval=_SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._save_state)
        self._cursor_timer = QTimer(self, singleShot=True, interval=_CURSOR_HIDE_MS)
        self._cursor_timer.timeout.connect(self._hide_cursor)

        # Page indicator for fullscreen (where there is no title bar); shown only while
        # the pointer is visible, so it never competes with the artwork.
        self._hud = QLabel(self)
        self._hud.setStyleSheet(_HUD_STYLE)
        self._hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hud.move(_HUD_MARGIN, _HUD_MARGIN)
        self._hud.hide()

        self._build_actions()

    # ------------------------------------------------------------------ actions
    def _action(self, text: str, slot, *shortcuts: str, checkable: bool = False) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if shortcuts:
            action.setShortcuts([QKeySequence(s) for s in shortcuts])
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        self.act_next = self._action("Next page", self.next_page, "Space")
        self.act_prev = self._action("Previous page", self.prev_page, "Shift+Space", "Backspace")
        # Arrow keys follow on-screen direction, so they swap in right-to-left books.
        self.act_right = self._action("", lambda: self.step_screen(+1), "Right")
        self.act_left = self._action("", lambda: self.step_screen(-1), "Left")
        self.act_first = self._action("First page", lambda: self.goto(0), "Home")
        self.act_last = self._action("Last page", lambda: self.goto(self.book.count - 1 if self.book else 0), "End")
        self.act_goto = self._action("Go to page…", self.ask_page, "Ctrl+G")
        self.act_zoom_in = self._action("Zoom in (bubble)", lambda: self._magnify(+120), "Up")
        self.act_zoom_out = self._action("Zoom out", lambda: self._magnify(-120), "Down")
        self.act_fullscreen = self._action("Full screen", self.toggle_fullscreen, "F", "F11", checkable=True)
        self.act_rtl = self._action("Right-to-left", self.toggle_rtl, "R", checkable=True)
        self.act_cover = self._action("Cover page alone", self.toggle_cover_alone, "O", checkable=True)
        self.act_info = self._action("Information…", self.toggle_info, "PgUp", "I")
        self.act_gallery = self._action("Gallery…", self.toggle_gallery, "PgDown", "G")
        self.act_open = self._action("Open…", self.open_dialog, "Ctrl+O")
        self.act_escape = self._action("", self._escape, "Esc")
        self.act_quit = self._action("Quit", self.close, "Q", "Ctrl+Q")
        # Disabled while an overlay is open so its own keyboard navigation gets the keys.
        self._navigation_actions = [
            self.act_next, self.act_prev, self.act_right, self.act_left, self.act_first,
            self.act_last, self.act_goto, self.act_rtl, self.act_cover, self.act_zoom_in, self.act_zoom_out,
        ]  # fmt: skip

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        self.act_rtl.setChecked(self.rtl)
        self.act_cover.setChecked(self.cover_alone)
        self.act_fullscreen.setChecked(self.isFullScreen())
        for item in (
            self.act_info, self.act_gallery, None,
            self.act_zoom_in, self.act_zoom_out, None,
            self.act_next, self.act_prev, self.act_first, self.act_last, self.act_goto, None,
            self.act_rtl, self.act_cover, self.act_fullscreen, None,
            self.act_open, self.act_quit,
        ):  # fmt: skip
            menu.addSeparator() if item is None else menu.addAction(item)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        menu.exec(event.globalPos())

    # -------------------------------------------------------------------- state
    @property
    def rtl(self) -> bool:
        if self._rtl_override is not None:
            return self._rtl_override
        return bool(self.book and self.book.metadata.manga_rtl)

    def _save_state(self) -> None:
        if self.book is not None:
            self.store.put(
                self.book.state_key,
                BookState(page=self.page, rtl=self._rtl_override, cover_alone=self.cover_alone),
            )
            self.store.flush()

    def _schedule_save(self) -> None:
        self._save_timer.start()

    # ------------------------------------------------------------------ opening
    def open_dialog(self) -> None:
        start = str(Path(self.book.path).parent) if self.book else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open comic book", start, _OPEN_FILTER)
        if path:
            self.open_path(path)

    def open_path(self, path: str, page: int | None = None) -> bool:
        try:
            book = Book(path)
        except (ArchiveError, OSError) as e:
            QMessageBox.critical(self, "cbv", f"Cannot open {path}\n\n{e}")
            return False
        self._close_book()
        self.book = book
        state = self.store.get(book.state_key)
        self.cover_alone = state.cover_alone
        self._rtl_override = state.rtl
        self.page = min(page if page is not None else state.page, book.count - 1)
        self.pipeline = RenderPipeline(book, self)
        self.pipeline.image_ready.connect(self._on_image_ready)
        self.pipeline.full_ready.connect(self._on_image_ready)
        self.pipeline.sizes_changed.connect(self._sync)
        self.pipeline.start_size_scan(self.page)
        self._sync()
        return True

    def _close_book(self) -> None:
        self.close_overlay()
        if self.book is None:
            return
        self._save_timer.stop()
        self._save_state()
        if self.pipeline is not None:
            self.pipeline.close()
            self.pipeline.deleteLater()
            self.pipeline = None
        self.book.close()
        self.book = None

    def closeEvent(self, event) -> None:  # noqa: N802
        self._close_book()
        super().closeEvent(event)

    # ---------------------------------------------------------------- geometry
    def _device_size(self) -> tuple[int, int]:
        dpr = self.devicePixelRatioF()
        return round(self.width() * dpr), round(self.height() * dpr)

    def _groups(self) -> list[tuple[int, ...]]:
        assert self.book is not None
        sizes = self.book.sizes()
        two = two_page_mode(self._device_size(), typical_aspect(sizes))
        return build_groups(self.book.count, self.book.wide_flags(), two, self.cover_alone)

    def _current_group(self, groups=None) -> tuple[int, ...]:
        groups = groups or self._groups()
        return groups[group_index(groups, self.page)]

    # --------------------------------------------------------------- navigation
    def goto(self, page: int) -> None:
        if self.book is None:
            return
        page = max(0, min(self.book.count - 1, page))
        if page == self.page:
            return
        self.page = page
        self._after_navigation()

    def _step_groups(self, delta: int) -> None:
        if self.book is None:
            return
        groups = self._groups()
        gi = group_index(groups, self.page) + delta
        if 0 <= gi < len(groups):
            self.page = groups[gi][0]
            self._after_navigation()

    def _after_navigation(self) -> None:
        self.dismiss_magnifier()
        if self.pipeline is not None:
            self.pipeline.new_generation()
        self._schedule_save()
        self._sync()

    def next_page(self) -> None:
        self._step_groups(+1)

    def prev_page(self) -> None:
        self._step_groups(-1)

    def step_screen(self, direction: int) -> None:
        """+1 = towards the right of the screen."""
        self._step_groups(-direction if self.rtl else direction)

    def ask_page(self) -> None:
        if self.book is None:
            return
        value, ok = QInputDialog.getInt(
            self, "Go to page", f"Page (1–{self.book.count}):", self.page + 1, 1, self.book.count
        )
        if ok:
            self.goto(value - 1)

    def toggle_rtl(self) -> None:
        self._rtl_override = not self.rtl
        self._schedule_save()
        self._sync()

    def toggle_cover_alone(self) -> None:
        self.cover_alone = not self.cover_alone
        self._schedule_save()
        self._sync()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self._cursor_timer.stop()
            self.unsetCursor()
        else:
            self.showFullScreen()
            self._cursor_timer.start()

    def _escape(self) -> None:
        if self._overlay is not None:
            self.close_overlay()
        elif self.magnifier.active:
            self.dismiss_magnifier()
        elif self.isFullScreen():
            self.toggle_fullscreen()

    # ----------------------------------------------------------------- overlays
    def _show_overlay(self, overlay: Overlay) -> None:
        self.close_overlay()
        self.dismiss_magnifier()
        self._overlay = overlay
        # The pointer must stay visible over overlays: they need clicking, and mouse
        # moves over a child widget never reach us to un-hide a cursor blanked in
        # fullscreen (or by the bubble).
        self._cursor_timer.stop()
        self.unsetCursor()
        overlay.setCursor(Qt.CursorShape.ArrowCursor)
        self._update_hud()
        overlay.closed.connect(self.close_overlay)
        overlay.page_chosen.connect(self._overlay_chose_page)
        if overlay.captures_all_keys:
            # every key except the two below must reach the overlay (and close it)
            blocked = [a for a in self.actions() if a not in (self.act_info, self.act_gallery)]
        else:
            blocked = self._navigation_actions
        for action in blocked:
            action.setEnabled(False)
        overlay.show()
        overlay.raise_()
        overlay.setFocus()

    def close_overlay(self) -> None:
        overlay, self._overlay = self._overlay, None
        if overlay is None:
            return
        if isinstance(overlay, Gallery):
            overlay.dispose()
        overlay.hide()
        overlay.deleteLater()
        for action in self.actions():
            action.setEnabled(True)
        if self.isFullScreen():
            self._cursor_timer.start()
        self._update_hud()
        self.setFocus()

    def _overlay_chose_page(self, page: int) -> None:
        self.close_overlay()
        self.goto(page)

    def toggle_info(self) -> None:
        if isinstance(self._overlay, InfoOverlay):
            self.close_overlay()
        elif self.book is not None:
            self._show_overlay(InfoOverlay(self, self.book))

    def toggle_gallery(self) -> None:
        if isinstance(self._overlay, Gallery):
            self.close_overlay()
        elif self.book is not None and self.pipeline is not None:
            self._show_overlay(Gallery(self, self.book, self.pipeline, self.page))

    # ---------------------------------------------------------------- magnifier
    def dismiss_magnifier(self) -> None:
        if not self.magnifier.active:
            return
        dirty = self.magnifier.dirty_rect(self._device_size(), self.devicePixelRatioF())
        self.magnifier.dismiss()
        self.unsetCursor()
        self._update_hud()
        self.update(dirty) if dirty else self.update()

    def _pointer_pos(self) -> QPointF:
        """Mouse position in device pixels (window centre if the pointer is outside)."""
        local = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(local):
            local = self.rect().center()
        return QPointF(local) * self.devicePixelRatioF()

    def _magnify(self, delta: int) -> None:
        """Zoom the bubble in (delta > 0, opening it) or out around the pointer."""
        if self.book is None or self.pipeline is None:
            return
        dpr = self.devicePixelRatioF()
        old = self.magnifier.dirty_rect(self._device_size(), dpr)
        was_active = self.magnifier.active
        self.magnifier.wheel(delta, self._pointer_pos())
        if self.magnifier.active and not was_active:
            self.setCursor(Qt.CursorShape.BlankCursor)
            for pl in self._placements():
                self.pipeline.request_full(pl.page)
        elif was_active and not self.magnifier.active:
            self.unsetCursor()
        self._update_hud()
        new = self.magnifier.dirty_rect(self._device_size(), dpr)
        self.update(old.united(new) if old and new else old or new or self.rect())

    def wheelEvent(self, event) -> None:  # noqa: N802
        """The wheel turns pages; with Ctrl it zooms the bubble."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # With Shift also held some systems report the wheel horizontally.
            self._magnify(event.angleDelta().y() or event.angleDelta().x())
        else:
            self._wheel_accum += event.angleDelta().y()
            while abs(self._wheel_accum) >= 120:  # one notch; touchpads accumulate
                step = -1 if self._wheel_accum > 0 else 1
                self._wheel_accum -= 120 * -step
                self._step_groups(step)
        event.accept()

    # ----------------------------------------------------------------- rendering
    def _on_image_ready(self, _page: int) -> None:
        self.update()

    def _sync(self) -> None:
        """Request everything the current view needs (and a bit more), then repaint."""
        if self.book is None or self.pipeline is None:
            return
        groups = self._groups()
        gi = group_index(groups, self.page)
        sizes = self.book.sizes()
        win = self._device_size()
        placements = place(groups[gi], sizes, win, self.rtl)
        if not placements:
            self.pipeline.ensure_sizes(list(groups[gi]))
        for pl in placements:
            self.pipeline.request(pl.page, pl.w, pl.h, PRIORITY_VISIBLE)
        for offset in (1, -1, 2):  # prefetch neighbouring groups
            ni = gi + offset
            if 0 <= ni < len(groups):
                for pl in place(groups[ni], sizes, win, self.rtl):
                    self.pipeline.request(pl.page, pl.w, pl.h, PRIORITY_PREFETCH)
        self._update_title(groups[gi])
        self.update()

    def _placements(self) -> list:
        if self.book is None:
            return []
        return place(self._current_group(), self.book.sizes(), self._device_size(), self.rtl)

    def _update_title(self, group: tuple[int, ...]) -> None:
        assert self.book is not None
        meta = self.book.metadata
        name = meta.title or Path(self.book.path).stem
        if meta.series and meta.series not in name:
            index = f" #{meta.series_index:g}" if meta.series_index is not None else ""
            name = f"{name} ({meta.series}{index})"
        first, last = group[0] + 1, group[-1] + 1
        pages = f"{first}" if first == last else f"{first}–{last}"
        self.setWindowTitle(f"{name} — {pages} / {self.book.count}")
        self._hud.setText(f"{pages} / {self.book.count}")
        self._hud.adjustSize()
        self._update_hud()

    def _update_hud(self) -> None:
        pointer_visible = self.cursor().shape() != Qt.CursorShape.BlankCursor
        self._hud.setVisible(
            self.book is not None
            and self.isFullScreen()
            and pointer_visible
            and self._overlay is None
            and not self.magnifier.active
        )
        self._hud.raise_()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_hud()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), _BACKGROUND)
        if self.book is None or self.pipeline is None:
            return
        dpr = self.devicePixelRatioF()
        p.scale(1 / dpr, 1 / dpr)  # paint in device pixels, so images map 1:1
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        placements = self._placements()
        shown = {}
        for pl in placements:
            target = QRect(pl.x, pl.y, pl.w, pl.h)
            image = self.pipeline.image(pl.page, pl.w, pl.h) or self.pipeline.any_image(pl.page)
            if image is not None:
                p.drawImage(target, image)
                shown[pl.page] = image
            elif self.book.is_broken(pl.page):
                p.fillRect(target, _PLACEHOLDER)
        if self.magnifier.active:
            images = {
                pl.page: self.pipeline.full_image(pl.page) or shown[pl.page]
                for pl in placements
                if pl.page in shown
            }
            self.magnifier.paint(p, self._device_size(), placements, images)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._overlay is not None:
            self._overlay.setGeometry(self.rect())
        self._resize_timer.start()

    # -------------------------------------------------------------------- mouse
    def _zone(self, x: float) -> int:
        """-1 = left third, +1 = right third, 0 = middle."""
        third = self.width() / 3
        return -1 if x < third else 1 if x > 2 * third else 0

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.magnifier.active:
            self.dismiss_magnifier()  # the click only closes the bubble
            return
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._zone(event.position().x())
            if zone:
                self.step_screen(zone)
            else:
                self.toggle_fullscreen()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.magnifier.active:
            dpr = self.devicePixelRatioF()
            old = self.magnifier.dirty_rect(self._device_size(), dpr)
            self.magnifier.move(event.position() * dpr)
            new = self.magnifier.dirty_rect(self._device_size(), dpr)
            self.update(old.united(new) if old and new else new or self.rect())
        elif self.isFullScreen():
            self.unsetCursor()
            self._cursor_timer.start()
            self._update_hud()
        super().mouseMoveEvent(event)

    def _hide_cursor(self) -> None:
        if self.isFullScreen() and self._overlay is None:
            self.setCursor(Qt.CursorShape.BlankCursor)
            self._update_hud()

    # ---------------------------------------------------------------- drag&drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_path(url.toLocalFile())
                break
