"""Combine metadata sources into one :class:`Metadata` for a book."""

from __future__ import annotations

import logging
from dataclasses import fields
from pathlib import Path

from ..archive import Archive
from .comicinfo import parse_comicinfo
from .model import Metadata
from .opf import find_opf, read_opf

log = logging.getLogger(__name__)

_READING_HINTS = ("manga_rtl", "pages")


def _find_comicinfo(archive: Archive) -> str | None:
    candidates = [n for n in archive.names() if n.rsplit("/", 1)[-1].lower() == "comicinfo.xml"]
    return min(candidates, key=lambda n: n.count("/")) if candidates else None


def merge(sidecar: Metadata | None, embedded: Metadata | None) -> Metadata:
    """The sidecar (OPF) wins for bibliographic fields; ComicInfo fills gaps and is
    the only source of reading hints (direction, page types, bookmarks)."""
    result = Metadata()
    for f in fields(Metadata):
        if f.name in _READING_HINTS:
            continue
        for source in (sidecar, embedded):
            if source is not None and (value := getattr(source, f.name)):
                setattr(result, f.name, value)
                break
    if embedded is not None:
        result.manga_rtl = embedded.manga_rtl
        result.pages = embedded.pages
    return result


def load_metadata(book_path: str, archive: Archive) -> Metadata:
    """OPF sidecar (if present) + embedded ComicInfo.xml (if present) + filename."""
    sidecar = None
    if (opf_path := find_opf(book_path)) is not None:
        sidecar = read_opf(opf_path)
        if sidecar is not None and sidecar.cover_path:
            sidecar.cover_path = str(opf_path.parent / sidecar.cover_path)

    embedded = None
    if (name := _find_comicinfo(archive)) is not None:
        try:
            embedded = parse_comicinfo(archive.read(name))
        except Exception as e:  # a broken ComicInfo must never prevent reading
            log.warning("ignoring ComicInfo.xml: %s", e)

    result = merge(sidecar, embedded)
    if not result.title:
        result.title = Path(book_path).stem
    return result
