"""Turn a raw list of archive entries into the ordered list of pages."""

from __future__ import annotations

import re
from functools import cache

from PIL import Image

_COMIC_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".gif", ".webp", ".bmp",
    ".tif", ".tiff", ".avif", ".jxl", ".heic", ".heif", ".jp2",
}  # fmt: skip
_JUNK_NAMES = {"thumbs.db", "desktop.ini"}
_DIGITS = re.compile(r"([0-9]+)")


@cache
def image_extensions() -> frozenset[str]:
    """Comic image extensions for which Pillow currently has a decoder."""
    Image.init()
    registered = {ext for ext, fmt in Image.registered_extensions().items() if fmt in Image.OPEN}
    return frozenset(_COMIC_IMAGE_EXTS & registered)


def _is_junk(name: str) -> bool:
    parts = name.split("/")
    return any(p.startswith(".") or p == "__MACOSX" for p in parts) or (
        parts[-1].lower() in _JUNK_NAMES
    )


def _natural(text: str) -> list[tuple[int, int | str]]:
    return [
        (0, int(tok)) if tok.isdigit() else (1, tok.casefold())
        for tok in _DIGITS.split(text)
        if tok
    ]


def natural_key(path: str) -> list[list[tuple[int, int | str]]]:
    """Case-insensitive, number-aware sort key applied per path component."""
    return [_natural(part) for part in path.split("/")]


def is_page(name: str) -> bool:
    if _is_junk(name):
        return False
    dot = name.rfind(".")
    return dot != -1 and name[dot:].lower() in image_extensions()


def page_names(entries: list[str]) -> list[str]:
    """Image entries in reading order. Stored order is never trusted."""
    return sorted((n for n in entries if is_page(n)), key=natural_key)
