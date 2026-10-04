"""Assemble a book's :class:`Metadata`: embedded ComicInfo.xml, else the filename."""

from __future__ import annotations

import logging
from pathlib import Path

from ..archive import Archive
from .comicinfo import parse_comicinfo
from .model import Metadata

log = logging.getLogger(__name__)


def _find_comicinfo(archive: Archive) -> str | None:
    candidates = [n for n in archive.names() if n.rsplit("/", 1)[-1].lower() == "comicinfo.xml"]
    return min(candidates, key=lambda n: n.count("/")) if candidates else None


def load_metadata(book_path: str, archive: Archive) -> Metadata:
    """Embedded ComicInfo.xml (if present) + filename."""
    embedded = None
    if (name := _find_comicinfo(archive)) is not None:
        try:
            embedded = parse_comicinfo(archive.read(name))
        except Exception as e:  # a broken ComicInfo must never prevent reading
            log.warning("ignoring ComicInfo.xml: %s", e)
    result = embedded if embedded is not None else Metadata()
    if not result.title:
        result.title = Path(book_path).stem
    return result
