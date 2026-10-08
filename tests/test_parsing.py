import unittest

from loader import be, load_fixture


class ParseEpisodeNumber(unittest.TestCase):
    def test_title_forms(self):
        cases = {
            "Distortion Cellar - Ep 13 - 60s Soul, Part 3- 2026/10/04": 13,
            "Distortion Cellar - Ep7 - Mixed Bag #4 - 2026-08-16": 7,
            "Distortion Cellar - Episode 2 - Mixed Bag": 2,
            "Distortion Cellar - Show 1": 1,
            "distortion cellar - EP 10 - Psychedelic 60s - 2026/09/06": 10,
        }
        for title, expected in cases.items():
            self.assertEqual(be.parse_episode_number(title), expected, title)

    def test_unparseable_title_names_the_override_setting(self):
        with self.assertRaises(ValueError) as ctx:
            be.parse_episode_number("Distortion Cellar - Mixed Bag",
                                    "/distortioncellar/x/")
        self.assertIn("number_overrides", str(ctx.exception))
        self.assertIn("/distortioncellar/x/", str(ctx.exception))

    def test_override_wins_over_title(self):
        self.assertEqual(
            be.parse_episode_number("No number here", "/k/", {"/k/": 14}), 14)


class DisplayTitle(unittest.TestCase):
    def test_strips_show_name_and_trailing_date(self):
        self.assertEqual(
            be.display_title("Distortion Cellar - Ep 13 - 60s Soul, Part 3- 2026/10/04"),
            "Ep 13 - 60s Soul, Part 3")
        self.assertEqual(
            be.display_title("Distortion Cellar - Ep7 - Mixed Bag #4 - 2026-08-16"),
            "Ep7 - Mixed Bag #4")

    def test_tolerates_misspelled_show_name(self):
        self.assertEqual(
            be.display_title("Distortion Celler - Ep 12 - Jazz - 2026/09/27"),
            "Ep 12 - Jazz")

    def test_leaves_other_titles_alone(self):
        self.assertEqual(be.display_title("Something Else"), "Something Else")

    def test_never_returns_empty(self):
        self.assertEqual(be.display_title("Distortion Cellar - "), "Distortion Cellar -")


class ToRecord(unittest.TestCase):
    def test_fields_from_fixture(self):
        cc = load_fixture()["data"][0]
        rec = be.to_record(cc)
        self.assertEqual(rec["number"], 13)
        self.assertEqual(rec["title"], "Ep 13 - 60s Soul, Part 3")
        self.assertEqual(rec["url"], cc["url"])
        self.assertEqual(rec["key"], cc["key"])
        self.assertEqual(rec["date"], "2026-10-05")
        self.assertIn("Soul", rec["tags"])
        self.assertTrue(rec["image"].startswith("https://"))


class MergeEpisodes(unittest.TestCase):
    EMPTY = {"number_overrides": {}, "episodes": {}}

    def test_fixture_yields_numbers_one_to_thirteen(self):
        merged = be.merge_episodes(self.EMPTY, load_fixture()["data"])
        self.assertEqual(sorted(int(n) for n in merged["episodes"]),
                         list(range(1, 14)))

    def test_duplicate_episode_numbers_are_an_error(self):
        cc = load_fixture()["data"][0]
        other = dict(cc, key="/distortioncellar/other/",
                     url="https://www.mixcloud.com/distortioncellar/other/")
        with self.assertRaises(ValueError) as ctx:
            be.merge_episodes(self.EMPTY, [cc, other])
        self.assertIn("twice", str(ctx.exception))

    def test_keeps_overrides_and_episodes_missing_from_feed(self):
        cc = load_fixture()["data"][0]
        old = {"number": 99, "title": "Old", "url": "u", "key": "k",
               "date": "2020-01-01", "tags": [], "image": "", "override": {}}
        data = {"number_overrides": {"/x/": 5},
                "episodes": {"99": old,
                             "13": {"override": {"date": "2026-10-04"}}}}
        merged = be.merge_episodes(data, [cc])
        self.assertIn("99", merged["episodes"])
        self.assertEqual(merged["episodes"]["13"]["override"],
                         {"date": "2026-10-04"})
        self.assertEqual(merged["number_overrides"], {"/x/": 5})

    def test_effective_applies_override(self):
        ep = {"title": "A", "date": "2026-10-05",
              "override": {"date": "2026-10-04"}}
        self.assertEqual(be.effective(ep)["date"], "2026-10-04")
        self.assertEqual(be.effective(ep)["title"], "A")


if __name__ == "__main__":
    unittest.main()
