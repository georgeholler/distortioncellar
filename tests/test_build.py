import copy
import os
import re
import tempfile
import unittest
import urllib.error

from loader import be, load_fixture


class BuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.fixture = load_fixture()
        self.logs = []

    def run_build(self, **kw):
        kw.setdefault("fetch_json", lambda url: self.fixture)
        be.build(self.root, log=self.logs.append, **kw)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as fh:
            return fh.read()

    def test_creates_pages_notes_stubs_and_data(self):
        self.run_build()
        for n in range(1, 14):
            self.assertTrue(os.path.exists(self.path("episodes", "ep-%d.html" % n)))
            self.assertTrue(os.path.exists(self.path("episodes", "notes", "ep-%d.md" % n)))
        self.assertTrue(os.path.exists(self.path("episodes", "data.json")))
        self.assertIn("episodes/ep-13.html", self.read("previous-episodes.html"))
        self.assertIn("episode 13", self.read("episodes", "notes", "ep-13.md"))
        self.assertNotIn("episode-notes", self.read("episodes", "ep-13.html"))

    def test_edited_notes_are_rendered_and_never_overwritten(self):
        self.run_build()
        notes = self.path("episodes", "notes", "ep-13.md")
        with open(notes, "w", encoding="utf-8") as fh:
            fh.write("# Tracklist\n\n- Song A\n")
        self.run_build()
        self.assertEqual(self.read("episodes", "notes", "ep-13.md"),
                         "# Tracklist\n\n- Song A\n")
        self.assertIn("<li>Song A</li>", self.read("episodes", "ep-13.html"))

    def test_second_run_changes_nothing(self):
        self.run_build()
        del self.logs[:]
        self.run_build()
        self.assertTrue(self.logs)
        for line in self.logs:
            self.assertTrue(line.startswith("unchanged"), line)

    def test_dry_run_writes_nothing(self):
        self.run_build(dry_run=True)
        self.assertEqual(os.listdir(self.root), [])
        self.assertTrue(any(line.startswith("created") for line in self.logs))

    # Review Focus 3: Mixcloud unreachable
    def test_api_down_builds_from_snapshot_with_warning(self):
        self.run_build()
        del self.logs[:]

        def down(url):
            raise urllib.error.URLError("boom")
        self.run_build(fetch_json=down)
        self.assertTrue(self.logs[0].startswith("WARNING"))
        self.assertTrue(os.path.exists(self.path("episodes", "ep-13.html")))

    def test_malformed_response_falls_back_to_snapshot(self):
        self.run_build()
        del self.logs[:]

        def bad(url):
            raise ValueError("bad json")
        self.run_build(fetch_json=bad)
        self.assertTrue(self.logs[0].startswith("WARNING"))

    def test_malformed_response_without_snapshot_is_a_clear_error(self):
        def bad(url):
            raise ValueError("bad json")
        with self.assertRaises(SystemExit) as ctx:
            self.run_build(fetch_json=bad)
        self.assertIn("Mixcloud", str(ctx.exception))

    def test_bom_notes_heading(self):
        self.run_build()
        with open(self.path("episodes", "notes", "ep-13.md"), "wb") as fh:
            fh.write(b"\xef\xbb\xbf# Tracklist\n")
        self.run_build()
        self.assertIn("<h4>Tracklist</h4>", self.read("episodes", "ep-13.html"))

    def test_stub_suggests_one_dash_per_track(self):
        self.assertIn("one '- ' line per track", be.stub_notes(5))

    def test_api_down_without_snapshot_is_a_clear_error(self):
        def down(url):
            raise urllib.error.URLError("boom")
        with self.assertRaises(SystemExit) as ctx:
            self.run_build(fetch_json=down)
        self.assertIn("Mixcloud", str(ctx.exception))
        self.assertEqual(os.listdir(self.root), [])

    # Review Focus 4: CRLF and whitespace-only notes
    def test_crlf_notes(self):
        self.run_build()
        with open(self.path("episodes", "notes", "ep-13.md"), "wb") as fh:
            fh.write(b"# Tracklist\r\n\r\n- Song A\r\n")
        self.run_build()
        self.assertIn("<li>Song A</li>", self.read("episodes", "ep-13.html"))

    def test_whitespace_only_notes_show_no_notes_box(self):
        self.run_build()
        with open(self.path("episodes", "notes", "ep-13.md"), "w") as fh:
            fh.write("  \n\n")
        self.run_build()
        self.assertNotIn("episode-notes", self.read("episodes", "ep-13.html"))

    # Review Focus 5: episode vanishes from the feed
    def test_episode_missing_from_feed_is_kept(self):
        self.run_build()
        trimmed = copy.deepcopy(self.fixture)
        trimmed["data"] = trimmed["data"][1:]  # drop newest (Ep 13)
        self.run_build(fetch_json=lambda url: trimmed)
        self.assertTrue(os.path.exists(self.path("episodes", "ep-13.html")))
        self.assertIn("episodes/ep-13.html", self.read("previous-episodes.html"))

    def test_unparseable_title_raises(self):
        bad = copy.deepcopy(self.fixture)
        bad["data"][0]["name"] = "Distortion Cellar - Mystery"
        with self.assertRaises(ValueError):
            self.run_build(fetch_json=lambda url: bad)

    def test_number_override_fixes_unparseable_title(self):
        bad = copy.deepcopy(self.fixture)
        bad["data"][0]["name"] = "Distortion Cellar - Mystery"
        key = bad["data"][0]["key"]
        os.makedirs(self.path("episodes"))
        with open(self.path("episodes", "data.json"), "w") as fh:
            fh.write('{"number_overrides": {"%s": 13}, "episodes": {}}' % key)
        self.run_build(fetch_json=lambda url: bad)
        self.assertTrue(os.path.exists(self.path("episodes", "ep-13.html")))

    def test_every_generated_link_resolves(self):
        self.run_build()
        pages = [("previous-episodes.html", self.root)]
        pages += [(os.path.join("episodes", "ep-%d.html" % n),
                   os.path.join(self.root, "episodes")) for n in range(1, 14)]
        for rel, base in pages:
            for href in re.findall(r'href="([^"]+)"', self.read(rel)):
                if href.startswith(("http", "mailto:")) or "style.css" in href \
                        or href in ("index.html", "../index.html"):
                    continue
                target = os.path.normpath(os.path.join(base, href))
                self.assertTrue(os.path.exists(target), "%s -> %s" % (rel, href))


if __name__ == "__main__":
    unittest.main()
