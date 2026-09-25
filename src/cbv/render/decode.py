"""Decode page images and scale them with Pillow (high-quality Lanczos)."""

from __future__ import annotations

import io

from PIL import Image, ImageOps

_EXIF_ORIENTATION = 0x0112
_SWAPPING_ORIENTATIONS = {5, 6, 7, 8}
_BACKGROUND = (255, 255, 255)

Image.MAX_IMAGE_PIXELS = None  # scans can be large; these are the user's own files


def _orientation(im: Image.Image) -> int:
    try:
        return int(im.getexif().get(_EXIF_ORIENTATION, 1))
    except Exception:
        return 1


def probe_size(data: bytes) -> tuple[int, int]:
    """Displayed (width, height) without decoding pixel data."""
    with Image.open(io.BytesIO(data)) as im:
        w, h = im.size
        if _orientation(im) in _SWAPPING_ORIENTATIONS:
            w, h = h, w
        return w, h


def _to_rgb(im: Image.Image) -> Image.Image:
    """RGB image; transparency is composited onto white paper."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, _BACKGROUND)
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    if im.mode in ("I;16", "I;16L", "I;16B", "I"):
        im = im.point(lambda v: v / 256).convert("L")
    return im.convert("RGB")


def render(data: bytes, width: int, height: int) -> Image.Image:
    """Decode ``data`` and resize to exactly ``width`` x ``height`` (up or down)."""
    im = Image.open(io.BytesIO(data))
    oriented = _orientation(im) != 1
    if not oriented and im.format == "JPEG":
        # Let libjpeg decode at 1/2, 1/4 or 1/8 size when the target is much smaller.
        im.draft("RGB", (width, height))
    im.load()
    if oriented:
        im = ImageOps.exif_transpose(im)
    if im.size != (width, height):
        if im.mode not in ("RGB", "RGBA", "LA", "L", "P"):
            im = _to_rgb(im)
        im = im.resize((width, height), Image.Resampling.LANCZOS)
    return _to_rgb(im)


def decode_full(data: bytes) -> Image.Image:
    """Full-resolution RGB decode (used by the magnifier)."""
    im = Image.open(io.BytesIO(data))
    im.load()
    return _to_rgb(ImageOps.exif_transpose(im))
