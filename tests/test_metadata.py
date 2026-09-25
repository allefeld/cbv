from __future__ import annotations

import datetime as dt
from pathlib import Path

from cbv.archive import open_archive
from cbv.metadata.comicinfo import parse_comicinfo
from cbv.metadata.merge import load_metadata, merge
from cbv.metadata.opf import find_opf, html_to_text, parse_opf

from .conftest import png_bytes

OPF_OLD = b"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier opf:scheme="calibre" id="calibre_id">70</dc:identifier>
    <dc:identifier opf:scheme="uuid" id="uuid_id">78e63ca2-efc3-43be-a134-6577d96e64ae</dc:identifier>
    <dc:title>Goodman goes Playboy</dc:title>
    <dc:creator opf:file-as="Kurtzman, Harvey &amp; Elder, Will" opf:role="aut">Harvey Kurtzman</dc:creator>
    <dc:creator opf:file-as="Kurtzman, Harvey &amp; Elder, Will" opf:role="aut">Will Elder</dc:creator>
    <dc:contributor opf:file-as="calibre" opf:role="bkp">calibre (3.19.0)</dc:contributor>
    <dc:date>1962-01-31T23:00:00+00:00</dc:date>
    <dc:description>&lt;i&gt;Help!&lt;/i&gt; magazine&lt;br/&gt;second &amp;amp; line</dc:description>
    <dc:language>en</dc:language>
    <meta content="Valerian" name="calibre:series"/>
    <meta content="4.5" name="calibre:series_index"/>
  </metadata>
  <guide><reference href="cover.jpg" title="Cover" type="cover"/></guide>
</package>"""

OPF_NEW_UNDEFINED_DATE = b"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Undated</dc:title>
    <dc:date>0101-01-01T00:00:00+00:00</dc:date>
    <meta name="calibre:series" content="S"/>
  </metadata>
</package>"""


def test_opf_fields(berlin_tz):
    m = parse_opf(OPF_OLD)
    assert m.title == "Goodman goes Playboy"
    assert m.authors == ["Harvey Kurtzman", "Will Elder"]
    assert m.series == "Valerian" and m.series_index == 4.5
    assert m.uuid == "78e63ca2-efc3-43be-a134-6577d96e64ae"
    assert m.cover_path == "cover.jpg"
    assert m.language == "en"
    assert m.description == "Help! magazine\nsecond & line"
    assert m.description_html == "<i>Help!</i> magazine<br>second &amp; line"


def test_opf_date_is_local_calendar_date(berlin_tz):
    # 23:00 UTC is midnight of the next day in Berlin (what Calibre shows)
    assert parse_opf(OPF_OLD).date == dt.date(1962, 2, 1)


def test_opf_undefined_date_sentinel_and_attribute_order():
    m = parse_opf(OPF_NEW_UNDEFINED_DATE)
    assert m.date is None
    assert m.series == "S"


def test_opf_garbage_returns_none():
    assert parse_opf(b"<not xml") is None
    assert parse_opf(b"<package/>") is None


def test_find_opf_prefers_metadata_opf(tmp_path: Path):
    book = tmp_path / "Book - Author.cbz"
    book.write_bytes(b"x")
    assert find_opf(str(book)) is None
    (tmp_path / "Book - Author.opf").write_text("x")
    assert find_opf(str(book)).name == "Book - Author.opf"
    (tmp_path / "metadata.opf").write_text("x")
    assert find_opf(str(book)).name == "metadata.opf"


def test_html_to_text():
    assert html_to_text("<p>a</p><p>b <b>c</b></p>") == "a\nb c"


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


def test_merge_opf_wins_comicinfo_fills_and_supplies_hints():
    opf = parse_opf(OPF_NEW_UNDEFINED_DATE)
    ci = parse_comicinfo(COMICINFO)
    m = merge(opf, ci)
    assert m.title == "Undated" and m.series == "S"  # OPF wins
    assert m.publisher == "Pub" and m.description == "Sum"  # gaps filled from ComicInfo
    assert m.manga_rtl is True and len(m.pages) == 2  # hints only from ComicInfo


def test_load_metadata_end_to_end(tmp_path: Path, make_zip):
    (tmp_path / "metadata.opf").write_bytes(OPF_OLD)
    path = make_zip("Goodman", {"ComicInfo.xml": COMICINFO, "1.png": png_bytes()})
    with open_archive(path) as a:
        m = load_metadata(path, a)
    assert m.title == "Goodman goes Playboy"
    assert m.manga_rtl is True
    assert m.cover_path == str(tmp_path / "cover.jpg")


def test_load_metadata_falls_back_to_filename(make_zip):
    path = make_zip("Some Book - Someone", {"1.png": png_bytes()})
    with open_archive(path) as a:
        m = load_metadata(path, a)
    assert m.title == "Some Book - Someone" and m.manga_rtl is None


def test_broken_comicinfo_is_ignored(make_zip):
    path = make_zip("b", {"ComicInfo.xml": b"<ComicInfo", "1.png": png_bytes()})
    with open_archive(path) as a:
        assert load_metadata(path, a).title == "b"


def test_real_library_sidecar(library: Path):
    book = next(library.glob("Alexandro Jodorowsky/#1_*/*.cbr"))
    with open_archive(str(book)) as a:
        m = load_metadata(str(book), a)
    assert m.title == "#1: Othon"
    assert m.series == "The Metabarons" and m.series_index == 1.0
    assert m.authors == ["Alexandro Jodorowsky", "Juan Giménez"]
