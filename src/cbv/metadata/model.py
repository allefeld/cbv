from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class PageInfo:
    """Per-page hints from ComicInfo.xml; ``index`` is the position in reading order."""

    index: int
    type: str | None = None
    double_page: bool | None = None
    bookmark: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class Metadata:
    # Bibliographic
    title: str | None = None
    series: str | None = None
    series_index: float | None = None
    series_count: int | None = None
    volume: int | None = None
    authors: list[str] = field(default_factory=list)
    credits: dict[str, list[str]] = field(default_factory=dict)
    publisher: str | None = None
    date: dt.date | None = None
    language: str | None = None
    description: str | None = None  # plain text
    description_html: str | None = None  # sanitized formatting-only HTML
    tags: list[str] = field(default_factory=list)
    # Reading hints
    manga_rtl: bool | None = None
    pages: list[PageInfo] = field(default_factory=list)
    # Identity / source
    uuid: str | None = None
    cover_path: str | None = None

    @property
    def bookmarks(self) -> list[PageInfo]:
        return [p for p in self.pages if p.bookmark]

