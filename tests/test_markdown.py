import unittest

from loader import be

md = be.render_markdown


class Markdown(unittest.TestCase):
    def test_paragraph_and_inline_styles(self):
        self.assertEqual(
            md("Hello **big** and *small* world"),
            "<p>Hello <strong>big</strong> and <em>small</em> world</p>")

    def test_underscore_italic_but_not_inside_words(self):
        self.assertEqual(md("_hi_ snake_case_name"),
                         "<p><em>hi</em> snake_case_name</p>")

    def test_consecutive_lines_join_into_one_paragraph(self):
        self.assertEqual(md("one\ntwo\n\nthree"), "<p>one two</p>\n<p>three</p>")

    def test_headings_start_at_h4(self):
        self.assertEqual(md("# Tracklist"), "<h4>Tracklist</h4>")
        self.assertEqual(md("## Sub"), "<h5>Sub</h5>")
        self.assertEqual(md("##### Deep"), "<h6>Deep</h6>")

    def test_lists(self):
        self.assertEqual(md("- one\n- two"),
                         "<ul><li>one</li><li>two</li></ul>")
        self.assertEqual(md("1. a\n2. b"), "<ol><li>a</li><li>b</li></ol>")
        self.assertEqual(md("Intro\n- a"), "<p>Intro</p>\n<ul><li>a</li></ul>")
        self.assertEqual(md("- a\n\nafter"), "<ul><li>a</li></ul>\n<p>after</p>")

    def test_links(self):
        self.assertEqual(
            md("[Mixcloud](https://www.mixcloud.com/x/)"),
            '<p><a href="https://www.mixcloud.com/x/">Mixcloud</a></p>')
        self.assertEqual(md("[q](https://x.com/?a=1&b=2)"),
                         '<p><a href="https://x.com/?a=1&amp;b=2">q</a></p>')

    def test_link_with_parentheses(self):
        out = md("[Love](https://en.wikipedia.org/wiki/Love_(band))")
        self.assertIn('href="https://en.wikipedia.org/wiki/Love_(band)"', out)
        self.assertNotIn("</a>)", out)

    def test_protocol_relative_url_is_not_a_link(self):
        self.assertNotIn("<a", md("[x](//evil.com)"))

    def test_link_url_is_not_italicized(self):
        out = md("[a](https://x.com/_a_b_)")
        self.assertIn('href="https://x.com/_a_b_"', out)
        self.assertNotIn("<em>", out)

    # Review Focus 1: injection
    def test_raw_html_is_escaped(self):
        out = md("<script>alert(1)</script> and <b>x</b>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<b>", out)

    def test_javascript_links_are_not_anchors(self):
        out = md("[x](javascript:alert(1))")
        self.assertNotIn("<a", out)

    def test_quote_in_link_cannot_break_out_of_attribute(self):
        out = md('[x](https://e.com/" onmouseover="alert(1))')
        self.assertNotIn('" onmouseover', out)

    # Review Focus 4: line endings and empty content
    def test_crlf_line_endings(self):
        self.assertEqual(md("# T\r\n\r\n- a\r\n- b\r\n"),
                         "<h4>T</h4>\n<ul><li>a</li><li>b</li></ul>")

    def test_html_comments_are_dropped(self):
        self.assertEqual(md("<!-- stub -->\n"), "")
        self.assertEqual(md("<!-- a\nmulti-line -->\nHi"), "<p>Hi</p>")

    def test_empty_and_whitespace(self):
        self.assertEqual(md(""), "")
        self.assertEqual(md("  \n\n \t\n"), "")


if __name__ == "__main__":
    unittest.main()
