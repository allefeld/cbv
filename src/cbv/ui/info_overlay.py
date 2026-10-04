"""Metadata table and bookmark contents, shown on request."""

from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QTextBrowser, QWidget

from ..core.book import Book
from ..metadata.model import Metadata
from ..metadata.richtext import plain_to_html
from .overlay import Overlay

_PANEL_WIDTH = 720


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def info_rows(meta: Metadata, book_path: str, page_count: int) -> list[tuple[str, str]]:
    """Label/value pairs for the info table; empty fields are omitted."""
    rows: list[tuple[str, str]] = []

    def add(label: str, value: str | None) -> None:
        if value:
            rows.append((label, value))

    add("Title", meta.title)
    if meta.series:
        index = f" #{meta.series_index:g}" if meta.series_index is not None else ""
        count = f" of {meta.series_count}" if meta.series_count else ""
        add("Series", f"{meta.series}{index}{count}")
    add("Author" if len(meta.authors) == 1 else "Authors", ", ".join(meta.authors))
    for role, names in meta.credits.items():
        if role != "Writer" or names != meta.authors:
            add(role, ", ".join(names))
    add("Published", meta.date.isoformat() if meta.date else None)
    add("Publisher", meta.publisher)
    add("Language", meta.language)
    add("Tags", ", ".join(meta.tags))
    add("Pages", str(page_count))
    add("Description", meta.description)
    path = Path(book_path)
    try:
        size = human_size(path.stat().st_size)
    except OSError:
        size = ""
    add("File", f"{path.name}" + (f" ({size})" if size else ""))
    add("Folder", str(path.parent))
    return rows


def info_html(book: Book) -> str:
    meta = book.metadata
    esc = html.escape
    parts = [
        "<style>td{padding:3px 12px 3px 0} a{color:#8ec5ff;text-decoration:none}"
        " p{margin:0 0 6px 0} ul,ol{margin:0 0 6px 0} blockquote{margin:0 0 6px 18px}</style>"
    ]
    def cell(label: str, value: str) -> str:
        if label == "Description":  # already reduced to safe formatting tags
            return meta.description_html or plain_to_html(value)
        return plain_to_html(value)

    rows = "".join(
        f'<tr><td valign="top" style="color:#9a9a9a" align="right">{esc(label)}</td>'
        f"<td>{cell(label, value)}</td></tr>"
        for label, value in info_rows(meta, book.path, book.count)
    )
    parts.append(f"<table>{rows}</table>")
    if meta.bookmarks:
        parts.append('<h3 style="color:#9a9a9a">Contents</h3><table>')
        for info in meta.bookmarks:
            parts.append(
                f'<tr><td align="right" style="color:#9a9a9a">{info.index + 1}</td>'
                f'<td><a href="cbv-page:{info.index}">{esc(info.bookmark or "")}</a></td></tr>'
            )
        parts.append("</table>")
    return "".join(parts)


_MODIFIER_KEYS = {
    Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock, Qt.Key.Key_ScrollLock,
}  # fmt: skip


class InfoOverlay(Overlay):
    """Any key (except the info/gallery keys, handled by the viewer) or a left click
    outside a link returns to the normal view."""

    captures_all_keys = True

    def __init__(self, parent: QWidget, book: Book) -> None:
        super().__init__(parent)
        self.browser = QTextBrowser(self)
        self.browser.setOpenLinks(False)
        self.browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.browser.setStyleSheet(
            "QTextBrowser { background: transparent; color: #e8e8e8; font-size: 15px; }"
        )
        self.browser.setHtml(info_html(book))
        self.browser.anchorClicked.connect(self._on_link)
        self.browser.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keys go to the overlay
        self.browser.viewport().installEventFilter(self)
        self._layout_panel()

    def _on_link(self, url: QUrl) -> None:
        if url.scheme() == "cbv-page":
            self.page_chosen.emit(int(url.path()))

    def _layout_panel(self) -> None:
        width = min(_PANEL_WIDTH, self.width() - 48)
        height = max(0, self.height() - 96)
        self.browser.setGeometry((self.width() - width) // 2, 48, width, height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_panel()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """A left click on the text closes the overlay, unless it hits a link."""
        if (
            obj is self.browser.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and not self.browser.anchorAt(event.position().toPoint())
        ):
            self.closed.emit()
            return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.closed.emit()
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() not in _MODIFIER_KEYS:
            self.closed.emit()
