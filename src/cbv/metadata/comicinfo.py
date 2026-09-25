"""Reader for ComicInfo.xml (ComicRack / Anansi Project schema, v1.0–2.1)."""

from __future__ import annotations

import datetime as dt
import logging
from xml.etree import ElementTree as ET

from .model import Metadata, PageInfo

log = logging.getLogger(__name__)

_CREDIT_FIELDS = {
    "Writer": "Writer",
    "Penciller": "Penciller",
    "Inker": "Inker",
    "Colorist": "Colorist",
    "Letterer": "Letterer",
    "CoverArtist": "Cover artist",
    "Editor": "Editor",
    "Translator": "Translator",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _int(text: str | None) -> int | None:
    try:
        return int(text.strip()) if text else None
    except ValueError:
        return None


def _float(text: str | None) -> float | None:
    try:
        return float(text.strip()) if text else None
    except ValueError:
        return None


def _bool(text: str | None) -> bool | None:
    if text is None:
        return None
    value = text.strip().lower()
    return True if value == "true" else False if value == "false" else None


def _split(text: str | None) -> list[str]:
    return [p.strip() for p in text.split(",") if p.strip()] if text else []


def parse_comicinfo(data: bytes) -> Metadata | None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        log.warning("cannot parse ComicInfo.xml: %s", e)
        return None
    if _local(root.tag) != "ComicInfo":
        return None

    fields: dict[str, str] = {}
    page_elements: list[ET.Element] = []
    for child in root:
        name = _local(child.tag)
        if name == "Pages":
            page_elements = [p for p in child if _local(p.tag) == "Page"]
        elif child.text and child.text.strip():
            fields[name] = child.text.strip()

    credits = {
        label: names for key, label in _CREDIT_FIELDS.items() if (names := _split(fields.get(key)))
    }
    authors = credits.get("Writer", []) + [
        n for n in credits.get("Penciller", []) if n not in credits.get("Writer", [])
    ]

    date = None
    if (year := _int(fields.get("Year"))) and year > 0:
        try:
            date = dt.date(year, _int(fields.get("Month")) or 1, _int(fields.get("Day")) or 1)
        except ValueError:
            date = dt.date(year, 1, 1)

    manga = fields.get("Manga")
    manga_rtl = True if manga == "YesAndRightToLeft" else False if manga == "No" else None

    pages = []
    for el in page_elements:
        index = _int(el.get("Image"))
        if index is None:
            continue
        pages.append(
            PageInfo(
                index=index,
                type=el.get("Type"),
                double_page=_bool(el.get("DoublePage")),
                bookmark=(el.get("Bookmark") or "").strip() or None,
                width=_int(el.get("ImageWidth")),
                height=_int(el.get("ImageHeight")),
            )
        )

    tags = _split(fields.get("Tags")) or _split(fields.get("Genre"))
    return Metadata(
        title=fields.get("Title"),
        series=fields.get("Series"),
        series_index=_float(fields.get("Number")),
        series_count=_int(fields.get("Count")),
        volume=_int(fields.get("Volume")),
        authors=authors,
        credits=credits,
        publisher=fields.get("Publisher"),
        date=date,
        language=fields.get("LanguageISO"),
        description=fields.get("Summary"),
        tags=tags,
        manga_rtl=manga_rtl,
        pages=pages,
    )
