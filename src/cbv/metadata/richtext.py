"""Reduce an HTML description (as Calibre stores it) to a few safe formatting tags."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_INLINE = {"b", "strong", "i", "em", "u", "s", "sub", "sup"}
_BLOCK = {"p", "ul", "ol", "li", "blockquote"}
_AS_PARAGRAPH = {"div", "tr"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_CONTENT = {"script", "style", "head", "title"}
_LOOKS_LIKE_HTML = re.compile(r"<[a-zA-Z/!]")
_BLOCK_EDGES = re.compile(r"\s*(</?(?:p|ul|ol|li|blockquote)>)\s*")
_EMPTY_PARAGRAPH = re.compile(r"<p>\s*</p>")
_EDGE_BREAKS = re.compile(r"^(?:\s|<br>)+|(?:\s|<br>)+$")


class _Sanitizer(HTMLParser):
    """Keeps b/i/u/s/sub/sup, paragraphs, lists, quotes and line breaks - without any
    attributes - and drops everything else but the text (links, spans, images, ...)."""

    def __init__(self, plain: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.plain = plain  # no markup at all: newlines are line breaks
        self.out: list[str] = []
        self.stack: list[tuple[str, str]] = []  # (source tag, closing html)
        self.skipping: str | None = None

    def _open(self, source: str, opening: str, closing: str) -> None:
        self.out.append(opening)
        self.stack.append((source, closing))

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        if self.skipping:
            return
        if tag in _SKIP_CONTENT:
            self.skipping = tag
        elif tag == "br":
            self.out.append("<br>")
        elif tag in _INLINE or tag in _BLOCK:
            self._open(tag, f"<{tag}>", f"</{tag}>")
        elif tag in _AS_PARAGRAPH:
            self._open(tag, "<p>", "</p>")
        elif tag in _HEADINGS:
            self._open(tag, "<p><b>", "</b></p>")

    def handle_endtag(self, tag: str) -> None:
        if self.skipping:
            if tag == self.skipping:
                self.skipping = None
            return
        if not any(source == tag for source, _ in self.stack):
            return  # stray end tag
        while self.stack:
            source, closing = self.stack.pop()
            self.out.append(closing)
            if source == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.skipping:
            return
        if self.plain:
            self.out.append("<br>".join(html.escape(part) for part in data.split("\n")))
        else:
            self.out.append(html.escape(re.sub(r"\s+", " ", data)))

    def result(self) -> str:
        while self.stack:
            self.out.append(self.stack.pop()[1])
        text = "".join(self.out)
        text = _BLOCK_EDGES.sub(r"\1", text)
        previous = None
        while previous != text:  # empty paragraphs can nest after removal
            previous = text
            text = _EMPTY_PARAGRAPH.sub("", text)
        return _EDGE_BREAKS.sub("", text)


def sanitize_html(source: str) -> str:
    """Safe HTML fragment (formatting only) for a description in HTML or plain text."""
    parser = _Sanitizer(plain=not _LOOKS_LIKE_HTML.search(source))
    parser.feed(source)
    parser.close()
    return parser.result()


def plain_to_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")
