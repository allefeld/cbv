from __future__ import annotations

import io
import os
import time
import zipfile
from pathlib import Path

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

LIBRARY = Path("/home/ca/Collection/Books & Stories/Comics")


def png_bytes(size: tuple[int, int] = (8, 12), color: str = "white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def make_zip(tmp_path: Path):
    def make(name: str, entries: dict[str, bytes], ext: str = ".cbz") -> str:
        path = tmp_path / (name + ext)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
            for entry, data in entries.items():
                z.writestr(entry, data)
        return str(path)

    return make


@pytest.fixture
def berlin_tz(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture(scope="session")
def library() -> Path:
    if not LIBRARY.is_dir():
        pytest.skip("real comics library not available")
    return LIBRARY


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
