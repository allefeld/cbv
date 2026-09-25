from cbv.metadata.richtext import plain_to_html, sanitize_html


def test_basic_formatting_is_kept():
    assert sanitize_html("<i>Help!</i> <b>magazine</b>") == "<i>Help!</i> <b>magazine</b>"
    assert sanitize_html("<strong>a</strong><em>b</em><u>c</u><s>d</s>x<sub>1</sub><sup>2</sup>") == (
        "<strong>a</strong><em>b</em><u>c</u><s>d</s>x<sub>1</sub><sup>2</sup>"
    )


def test_paragraphs_lists_quotes_and_breaks():
    src = "<p>one</p>\n<p>two<br/>three</p><ul><li>a</li><li>b</li></ul><blockquote>q</blockquote>"
    assert sanitize_html(src) == (
        "<p>one</p><p>two<br>three</p><ul><li>a</li><li>b</li></ul><blockquote>q</blockquote>"
    )


def test_attributes_are_dropped():
    assert sanitize_html('<b onclick="evil()" style="color:red">x</b>') == "<b>x</b>"
    assert sanitize_html('<p class="c" id="i">x</p>') == "<p>x</p>"


def test_unsupported_tags_keep_their_text():
    assert sanitize_html('<a href="http://x/">link</a> <span>s</span>') == "link s"
    assert sanitize_html('a<img src="x.png">b') == "ab"


def test_script_and_style_content_is_dropped():
    assert sanitize_html("<p>a<script>alert(1)</script>b</p>") == "<p>ab</p>"
    assert sanitize_html("<style>p{color:red}</style><p>x</p>") == "<p>x</p>"


def test_div_becomes_paragraph_and_headings_become_bold_paragraphs():
    assert sanitize_html("<div>a</div><div>b</div>") == "<p>a</p><p>b</p>"
    assert sanitize_html("<h2>Title</h2><p>text</p>") == "<p><b>Title</b></p><p>text</p>"


def test_broken_nesting_is_repaired():
    assert sanitize_html("<b>unclosed <i>text") == "<b>unclosed <i>text</i></b>"
    assert sanitize_html("stray</i> end</b>") == "stray end"
    assert sanitize_html("<b><i>x</b></i>") == "<b><i>x</i></b>"


def test_text_is_escaped_and_whitespace_collapsed():
    assert sanitize_html("<p>a  &lt;b&gt;\n  &amp; c</p>") == "<p>a &lt;b&gt; &amp; c</p>"


def test_empty_paragraphs_and_edge_breaks_are_removed():
    assert sanitize_html("<p></p><p> </p><p>x</p><br><br>") == "<p>x</p>"
    assert sanitize_html("   ") == ""


def test_plain_text_keeps_line_breaks():
    assert sanitize_html("line one\nline 2 & 3 < 4") == "line one<br>line 2 &amp; 3 &lt; 4"
    assert plain_to_html("a\n<b>") == "a<br>&lt;b&gt;"
