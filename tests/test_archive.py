from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from cbv.archive import ArchiveError, detect_format, open_archive
from cbv.pages import page_names

from .conftest import png_bytes


def test_zip_reads_entries_and_skips_directories(make_zip):
    path = make_zip("a", {"dir/": b"", "dir/1.png": png_bytes(), "dir/2.png": png_bytes()})
    with open_archive(path) as a:
        assert a.names() == ["dir/1.png", "dir/2.png"]
        assert a.read("dir/1.png").startswith(b"\x89PNG")


def test_format_detected_by_magic_not_extension(make_zip):
    path = make_zip("really_a_zip", {"1.png": png_bytes()}, ext=".cbr")
    assert detect_format(path) == "zip"
    with open_archive(path) as a:
        assert a.names() == ["1.png"]


def test_unknown_format_raises(tmp_path: Path):
    p = tmp_path / "x.cbz"
    p.write_bytes(b"not an archive at all" * 50)
    with pytest.raises(ArchiveError):
        open_archive(str(p))


def test_missing_entry_raises(make_zip):
    with open_archive(make_zip("a", {"1.png": png_bytes()})) as a, pytest.raises(ArchiveError):
        a.read("nope.png")


def test_zip_backslash_names_are_normalised(make_zip):
    path = make_zip("w", {"dir\\1.png": png_bytes()})
    with open_archive(path) as a:
        assert a.names() == ["dir/1.png"]
        assert a.read("dir/1.png")


def test_zip_legacy_utf8_name_without_flag(tmp_path: Path):
    """Names in UTF-8 but without the UTF-8 flag are decoded as cp437 by zipfile."""
    path = tmp_path / "u.cbz"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Café/1.png", png_bytes())  # zipfile sets the UTF-8 flag itself
    data = bytearray(path.read_bytes())
    # clear flag bit 0x800 (high byte of the flags field) in local and central headers
    for sig, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        data[data.find(sig) + offset + 1] &= ~0x08 & 0xFF
    path.write_bytes(bytes(data))
    with open_archive(str(path)) as a:
        assert a.names() == ["Café/1.png"]


def test_stored_order_is_not_page_order(make_zip):
    entries = {f"Book{n}.png": png_bytes() for n in (9, 7, 1, 10, 2)}
    with open_archive(make_zip("s", entries)) as a:
        assert page_names(a.names()) == [f"Book{n}.png" for n in (1, 2, 7, 9, 10)]


def test_tar(tmp_path: Path):
    path = tmp_path / "t.cbt"
    with tarfile.open(path, "w") as t:
        info = tarfile.TarInfo("a/1.png")
        data = png_bytes()
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    assert detect_format(str(path)) == "tar"
    with open_archive(str(path)) as a:
        assert a.names() == ["a/1.png"]
        assert a.read("a/1.png") == data


def test_seven_zip(tmp_path: Path):
    import py7zr

    path = tmp_path / "s.cb7"
    with py7zr.SevenZipFile(path, "w") as z:
        z.writestr(png_bytes(), "d/1.png")
        z.writestr(png_bytes(color="black"), "d/2.png")
    assert detect_format(str(path)) == "7z"
    with open_archive(str(path)) as a:
        assert sorted(a.names()) == ["d/1.png", "d/2.png"]
        assert a.read("d/2.png") == png_bytes(color="black")


def test_folder(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "1.png").write_bytes(png_bytes())
    assert detect_format(str(tmp_path)) == "folder"
    with open_archive(str(tmp_path)) as a:
        assert a.names() == ["sub/1.png"]
        assert a.read("sub/1.png").startswith(b"\x89PNG")


def test_real_rar_compressed_and_directory_entry(library: Path):
    """Sarvan has a wrapper directory entry; 'Honorata' uses real RAR compression."""
    sarvan = next(library.glob("Jordi Bernet/*/*.cbr"))
    with open_archive(str(sarvan)) as a:
        assert len(page_names(a.names())) == 52
        assert not any(n.endswith("/") for n in a.names())
    honorata = next(library.glob("Alexandro Jodorowsky/#2_*/*.cbr"))
    with open_archive(str(honorata)) as a:
        names = page_names(a.names())
        assert len(names) == 66
        data = a.read(names[-1])
        assert data[:2] == b"\xff\xd8" and len(data) == 2599865
