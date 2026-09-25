"""Pure page-layout logic (no Qt): pairing pages and fitting them into a window.

All geometry is in device pixels. ``sizes`` are the natural (width, height) of the
pages in reading order, ``None`` where a page has not been probed yet.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

Size = tuple[int, int]


@dataclass(frozen=True)
class Placement:
    page: int
    x: int
    y: int
    w: int
    h: int


def is_wide(size: Size | None) -> bool:
    """Landscape pages are treated as double-page spreads and always shown alone."""
    return size is not None and size[0] > size[1]


def typical_aspect(sizes: Sequence[Size | None]) -> float | None:
    """Median width/height of the known portrait pages, or None if there are none."""
    aspects = [w / h for s in sizes if s is not None and not is_wide(s) and (w := s[0]) and (h := s[1])]
    return statistics.median(aspects) if aspects else None


def two_page_mode(window: Size, aspect: float | None) -> bool:
    """Two typical pages fit side by side when scaled to the full window height."""
    if aspect is None:
        return False
    wind_w, wind_h = window
    return wind_h > 0 and wind_w / wind_h >= 2 * aspect


def build_groups(
    count: int, wide: Sequence[bool], two_page: bool, cover_alone: bool = True
) -> list[tuple[int, ...]]:
    """Partition pages into display groups: singles, or pairs in two-page mode.

    Wide pages are always alone; pairing restarts after them. With ``cover_alone``
    the first page is shown by itself, as in print.
    """
    if not two_page:
        return [(i,) for i in range(count)]
    groups: list[tuple[int, ...]] = []
    i = 0
    if cover_alone and count:
        groups.append((0,))
        i = 1
    while i < count:
        if not wide[i] and i + 1 < count and not wide[i + 1]:
            groups.append((i, i + 1))
            i += 2
        else:
            groups.append((i,))
            i += 1
    return groups


def group_index(groups: Sequence[tuple[int, ...]], page: int) -> int:
    for gi, group in enumerate(groups):
        if page in group:
            return gi
    return max(0, min(len(groups) - 1, page))


def place(group: Sequence[int], sizes: Sequence[Size | None], window: Size, rtl: bool) -> list[Placement]:
    """Scale the group to the largest common height that fits, centred in the window.

    Upscaling beyond natural size is intended. In right-to-left mode the first page of
    a pair is on the right. Returns placements in on-screen left-to-right order.
    """
    win_w, win_h = window
    dims = []
    for page in group:
        size = sizes[page]
        if size is None or size[0] <= 0 or size[1] <= 0:
            return []
        dims.append(size)
    total_aspect = sum(w / h for w, h in dims)
    height = min(win_h, win_w / total_aspect)
    if height <= 0:
        return []
    pages = list(zip(group, dims, strict=True))
    if rtl:
        pages.reverse()
    widths = [max(1, round(height * w / h)) for _, (w, h) in pages]
    h_px = max(1, round(height))
    x = (win_w - sum(widths)) // 2
    y = (win_h - h_px) // 2
    result = []
    for (page, _), w_px in zip(pages, widths, strict=True):
        result.append(Placement(page, x, y, w_px, h_px))
        x += w_px
    return result
