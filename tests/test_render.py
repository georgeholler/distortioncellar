import unittest

from loader import be


def make_ep(number, **kw):
    ep = {"number": number, "title": "Ep %d - Test" % number,
          "url": "https://www.mixcloud.com/distortioncellar/ep-%d/" % number,
          "key": "/distortioncellar/ep-%d/" % number,
          "date": "2026-10-0%d" % (number % 9 + 1), "tags": ["Soul", "R&B"],
          "image": "https://thumbnailer.mixcloud.com/x.jpg", "override": {}}
    ep.update(kw)
    return ep


class EpisodePage(unittest.TestCase):
    def test_core_content(self):
        page = be.render_episode_page(make_ep(13), "<p>Great show</p>")
        self.assertIn("<h2>Ep 13 - Test</h2>", page)
        self.assertIn("2026-10-05", page)
        self.assertIn("Soul", page)
        self.assertIn("R&amp;B", page)
        self.assertIn("feed=%2Fdistortioncellar%2Fep-13%2F", page)
        self.assertIn('href="https://www.mixcloud.com/distortioncellar/ep-13/"', page)
        self.assertIn('href="../css/style.css"', page)
        self.assertIn('href="../previous-episodes.html"', page)
        self.assertIn("<p>Great show</p>", page)
        self.assertIn("<h3>Notes</h3>", page)

    # Review Focus 2: special characters
    def test_title_with_ampersand_and_markup_is_escaped(self):
        page = be.render_episode_page(
            make_ep(12, title="Jazz - Miles, Monk & Coltrane <script>x</script>"), "")
        self.assertIn("Monk &amp; Coltrane &lt;script&gt;", page)
        self.assertNotIn("Monk & Coltrane", page)
        self.assertNotIn("<script>x", page)

    def test_no_notes_means_no_notes_section(self):
        for notes in ("", "   \n"):
            page = be.render_episode_page(make_ep(13), notes)
            self.assertNotIn("episode-notes", page)

    def test_prev_next_links(self):
        page = be.render_episode_page(make_ep(5), "", make_ep(4), make_ep(6))
        self.assertIn('href="ep-4.html"', page)
        self.assertIn('href="ep-6.html"', page)
        first = be.render_episode_page(make_ep(1), "", None, make_ep(2))
        self.assertNotIn("&larr;", first)
        last = be.render_episode_page(make_ep(13), "", make_ep(12), None)
        self.assertNotIn("&rarr;", last)

    def test_override_wins(self):
        page = be.render_episode_page(
            make_ep(13, override={"date": "2026-10-04"}), "")
        self.assertIn("2026-10-04", page)
        self.assertNotIn("2026-10-05", page)

    def test_missing_image_omits_figure(self):
        page = be.render_episode_page(make_ep(13, image=""), "")
        self.assertNotIn("<img", page)


class ListPage(unittest.TestCase):
    def test_newest_first_with_links(self):
        page = be.render_list_page([make_ep(2), make_ep(13), make_ep(7)])
        self.assertLess(page.index("episodes/ep-13.html"),
                        page.index("episodes/ep-7.html"))
        self.assertLess(page.index("episodes/ep-7.html"),
                        page.index("episodes/ep-2.html"))
        self.assertIn('href="css/style.css"', page)
        self.assertIn('href="index.html"', page)
        self.assertIn("All Episodes", page)

    def test_intro_says_episode_not_show(self):
        page = be.render_list_page([make_ep(1)])
        self.assertIn("Every episode, newest first.", page)

    def test_titles_are_escaped(self):
        page = be.render_list_page([make_ep(12, title="Monk & <b>Trane</b>")])
        self.assertIn("Monk &amp; &lt;b&gt;Trane&lt;/b&gt;", page)

    def test_empty_list_still_renders(self):
        self.assertIn("All Episodes", be.render_list_page([]))


if __name__ == "__main__":
    unittest.main()
