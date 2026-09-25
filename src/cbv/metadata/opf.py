"""Reader for Calibre's ``metadata.opf`` sidecar (OPF 2.x)."""

from __future__ import annotations

import datetime as dt
import logging
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .model import Metadata
from .richtext import sanitize_html

log = logging.getLogger(__name__)

_DC = "{http://purl.org/dc/elements/1.1/}"
_OPF = "{http://www.idpf.org/2007/opf}"
# Calibre stores "no date" as 0101-01-01.
_UNDEFINED_YEAR_LIMIT = 101


def find_opf(book_path: str) -> Path | None:
    """Locate the sidecar next to the book: ``metadata.opf`` or ``<stem>.opf``."""
    book = Path(book_path)
    for candidate in (book.parent / "metadata.opf", book.with_suffix(".opf")):
        if candidate.is_file():
            return candidate
    return None


class _TextExtractor(HTMLParser):
    _BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        if tag in self._BREAKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line).strip()


def _parse_date(text: str | None) -> dt.date | None:
    if not text:
        return None
    try:
        value = dt.datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if value.year <= _UNDEFINED_YEAR_LIMIT:
        return None
    if value.tzinfo is not None:
        try:
            value = value.astimezone()  # Calibre stores UTC; show local calendar date
        except (OverflowError, OSError, ValueError):
            pass
    return value.date()


def _float(text: str | None) -> float | None:
    try:
        return float(text) if text else None
    except ValueError:
        return None


def parse_opf(data: bytes) -> Metadata | None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        log.warning("cannot parse OPF: %s", e)
        return None
    meta = root.find(f"{_OPF}metadata")
    if meta is None:
        return None

    def text_of(tag: str) -> str | None:
        el = meta.find(f"{_DC}{tag}")
        return el.text.strip() if el is not None and el.text and el.text.strip() else None

    calibre = {
        m.get("name"): m.get("content") for m in meta.findall(f"{_OPF}meta") if m.get("name")
    }
    # Calibre also emits unqualified <meta> in some OPF 2 files.
    for m in meta.findall("meta"):
        if m.get("name"):
            calibre.setdefault(m.get("name"), m.get("content"))

    uuid = None
    for ident in meta.findall(f"{_DC}identifier"):
        if ident.get(f"{_OPF}scheme", "").lower() == "uuid" and ident.text:
            uuid = ident.text.strip()

    cover = None
    for ref in root.findall(f"{_OPF}guide/{_OPF}reference"):
        if ref.get("type") == "cover":
            cover = ref.get("href")

    description = text_of("description")
    series_index = _float(calibre.get("calibre:series_index"))
    return Metadata(
        title=text_of("title"),
        series=calibre.get("calibre:series") or None,
        series_index=series_index,
        authors=[
            e.text.strip() for e in meta.findall(f"{_DC}creator") if e.text and e.text.strip()
        ],
        publisher=text_of("publisher"),
        date=_parse_date(text_of("date")),
        language=text_of("language"),
        description=html_to_text(description) if description else None,
        description_html=sanitize_html(description) or None if description else None,
        tags=[e.text.strip() for e in meta.findall(f"{_DC}subject") if e.text and e.text.strip()],
        uuid=uuid,
        cover_path=cover,
    )


def read_opf(path: Path) -> Metadata | None:
    try:
        return parse_opf(path.read_bytes())
    except OSError as e:
        log.warning("cannot read %s: %s", path, e)
        return None
