from cbv.pages import is_page, natural_key, page_names


def test_natural_sort_handles_unpadded_numbers():
    names = ["p10.jpg", "p2.jpg", "p1.jpg", "p11.jpg"]
    assert page_names(names) == ["p1.jpg", "p2.jpg", "p10.jpg", "p11.jpg"]


def test_natural_sort_is_case_insensitive_and_mixed_padding():
    names = ["Page_01.jpg", "page_2.jpg", "PAGE_10.jpg"]
    assert page_names(names) == ["Page_01.jpg", "page_2.jpg", "PAGE_10.jpg"]


def test_cover_names_sort_before_pages():
    names = ["c_p01.jpg", "c_p24.jpg", "c_ic1.jpg", "c_c01-rc1.jpg"]
    assert page_names(names)[:2] == ["c_c01-rc1.jpg", "c_ic1.jpg"]


def test_sort_uses_full_path_components():
    names = ["b/2.jpg", "a/10.jpg", "a/9.jpg", "c.jpg"]
    assert page_names(names) == ["a/9.jpg", "a/10.jpg", "b/2.jpg", "c.jpg"]


def test_non_images_and_junk_are_dropped():
    names = [
        "ComicInfo.xml", "Thumbs.db", "__MACOSX/1.jpg", "._1.jpg", ".hidden/2.jpg",
        "notes.txt", "1.JPG", "sub/2.PNG", "noext",
    ]  # fmt: skip
    assert page_names(names) == ["1.JPG", "sub/2.PNG"]


def test_is_page():
    assert is_page("x/y.webp")
    assert not is_page("x/y.txt")
    assert not is_page("Thumbs.db")


def test_natural_key_is_comparable_for_mixed_names():
    # digit-leading vs letter-leading names must not raise TypeError
    sorted(["1a", "a1", "10", "b"], key=natural_key)
