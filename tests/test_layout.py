from cbv.render.layout import (
    Placement,
    build_groups,
    group_index,
    is_wide,
    place,
    two_page_mode,
    typical_aspect,
)

PORTRAIT = (1000, 1500)  # aspect 0.667
WIDE = (2000, 1500)


def test_typical_aspect_ignores_wide_and_unknown():
    assert typical_aspect([PORTRAIT, WIDE, None, (1200, 1500)]) == (1000 / 1500 + 0.8) / 2
    assert typical_aspect([WIDE, None]) is None


def test_two_page_mode_depends_on_window_shape():
    assert two_page_mode((1920, 1080), 0.7)  # 16:9 fits two portrait pages
    assert not two_page_mode((1000, 1000), 0.7)  # square window does not
    assert not two_page_mode((1920, 1080), None)
    assert two_page_mode((1400, 1000), 0.7)  # exactly the boundary


def test_single_page_groups():
    assert build_groups(3, [False] * 3, two_page=False) == [(0,), (1,), (2,)]


def test_pairs_cover_alone():
    assert build_groups(6, [False] * 6, True, cover_alone=True) == [(0,), (1, 2), (3, 4), (5,)]


def test_pairs_cover_paired_when_disabled():
    assert build_groups(5, [False] * 5, True, cover_alone=False) == [(0, 1), (2, 3), (4,)]


def test_wide_page_is_alone_and_pairing_restarts():
    wide = [False, False, False, True, False, False, False]
    assert build_groups(7, wide, True, cover_alone=True) == [(0,), (1, 2), (3,), (4, 5), (6,)]


def test_wide_after_single_breaks_pair():
    wide = [False, True, False, False]
    assert build_groups(4, wide, True, cover_alone=True) == [(0,), (1,), (2, 3)]


def test_group_index():
    groups = [(0,), (1, 2), (3,)]
    assert [group_index(groups, p) for p in range(4)] == [0, 1, 1, 2]


def test_is_wide():
    assert is_wide(WIDE) and not is_wide(PORTRAIT) and not is_wide(None)


def test_single_page_fits_by_height_and_upscales_and_centres():
    (p,) = place([0], [PORTRAIT], (3000, 2000), rtl=False)
    assert (p.h, p.w) == (2000, round(2000 * 1000 / 1500))  # upscaled past natural size
    assert p.y == 0 and p.x == (3000 - p.w) // 2


def test_single_page_limited_by_width():
    (p,) = place([0], [PORTRAIT], (600, 2000), rtl=False)
    assert p.w == 600 and p.h == 900 and p.y == (2000 - 900) // 2


def test_pair_common_height_and_order():
    sizes = [PORTRAIT, (1200, 1500)]
    ps = place([0, 1], sizes, (4000, 1000), rtl=False)
    assert [p.page for p in ps] == [0, 1]
    assert ps[0].h == ps[1].h == 1000
    assert ps[0].x + ps[0].w == ps[1].x  # adjacent, no gap
    assert ps[0].x == (4000 - (ps[0].w + ps[1].w)) // 2


def test_pair_rtl_puts_first_page_on_right():
    ps = place([0, 1], [PORTRAIT, PORTRAIT], (4000, 1000), rtl=True)
    assert [p.page for p in ps] == [1, 0]


def test_pair_scaled_down_when_too_wide():
    ps = place([0, 1], [PORTRAIT, PORTRAIT], (800, 1000), rtl=False)
    assert sum(p.w for p in ps) <= 800 and ps[0].h < 1000


def test_unknown_size_yields_no_placement():
    assert place([0, 1], [PORTRAIT, None], (800, 600), rtl=False) == []
    assert isinstance(place([0], [PORTRAIT], (800, 600), False)[0], Placement)
