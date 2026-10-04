from __future__ import annotations

import datetime as dt
from pathlib import Path

from cbv.archive import open_archive
from cbv.metadata.comicinfo import parse_comicinfo
from cbv.metadata.merge import load_metadata

from .conftest import png_bytes

COMICINFO = b"""<?xml version="1.0"?>
<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Title>Chapter One</Title><Series>Big Series</Series><Number>1.5</Number><Count>12</Count>
  <Volume>2</Volume><Year>2019</Year><Month>3</Month><Day>7</Day>
  <Writer>A Writer, Second Writer</Writer><Penciller>P</Penciller><Publisher>Pub</Publisher>
  <Summary>Sum</Summary><LanguageISO>fr</LanguageISO><Manga>YesAndRightToLeft</Manga>
  <Tags>x, y</Tags>
  <Pages>
    <Page Image="0" Type="FrontCover" ImageWidth="800" ImageHeight="1200"/>
    <Page Image="3" DoublePage="true" Bookmark="Act II"/>
    <Page Type="Story"/>
  </Pages>
</ComicInfo>"""


def test_comicinfo_fields():
    m = parse_comicinfo(COMICINFO)
    assert (m.title, m.series, m.series_index, m.series_count, m.volume) == (
        "Chapter One", "Big Series", 1.5, 12, 2,
    )  # fmt: skip
    assert m.date == dt.date(2019, 3, 7)
    assert m.authors == ["A Writer", "Second Writer", "P"]
    assert m.credits["Writer"] == ["A Writer", "Second Writer"]
    assert m.manga_rtl is True
    assert m.tags == ["x", "y"]
    assert [(p.index, p.type, p.double_page, p.bookmark) for p in m.pages] == [
        (0, "FrontCover", None, None),
        (3, None, True, "Act II"),
    ]
    assert m.pages[0].width == 800
    assert [p.index for p in m.bookmarks] == [3]


def test_comicinfo_manga_flag_variants():
    assert parse_comicinfo(b"<ComicInfo><Manga>No</Manga></ComicInfo>").manga_rtl is False
    assert parse_comicinfo(b"<ComicInfo><Manga>Yes</Manga></ComicInfo>").manga_rtl is None
    assert parse_comicinfo(b"<ComicInfo/>").manga_rtl is None


def test_comicinfo_rejects_other_xml():
    assert parse_comicinfo(b"<other/>") is None
    assert parse_comicinfo(b"<ComicInfo") is None


def test_load_metadata_end_to_end(make_zip):
    path = make_zip("Goodman", {"ComicInfo.xml": COMICINFO, "1.png": png_bytes()})
    with open_archive(path) as a:
        m = load_metadata(path, a)
    assert m.title == "Chapter One"
    assert m.manga_rtl is True
    assert m.series == "Big Series" and m.series_index == 1.5


def test_load_metadata_falls_back_to_filename(make_zip):
    path = make_zip("Some Book - Someone", {"1.png": png_bytes()})
    with open_archive(path) as a:
        m = load_metadata(path, a)
    assert m.title == "Some Book - Someone" and m.manga_rtl is None


def test_broken_comicinfo_is_ignored(make_zip):
    path = make_zip("b", {"ComicInfo.xml": b"<ComicInfo", "1.png": png_bytes()})
    with open_archive(path) as a:
        assert load_metadata(path, a).title == "b"


def test_real_library_comicinfo(library: Path):
    book = library / "Moebius/The Airtight Garage (89)/The Airtight Garage - Moebius.cbz"
    with open_archive(str(book)) as a:
        m = load_metadata(str(book), a)
    assert m.title == "The Airtight Garage"
    assert m.series == "Epic Graphic Novel: Moebius" and m.series_index == 3.0
    assert m.series_count == 11
    assert m.authors == ["Mœbius"]
    assert m.date == dt.date(1976, 3, 1)
    assert m.publisher == "Marvel/Epic Comics"
    assert m.manga_rtl is False
