import json
import os
import tempfile
import unittest

from loader import be


class FetchCloudcasts(unittest.TestCase):
    def test_follows_paging_next_until_exhausted(self):
        pages = {
            "https://api.mixcloud.com/someone/cloudcasts/?limit=100":
                {"data": [{"n": 1}], "paging": {"next": "http://page2"}},
            "http://page2":
                {"data": [{"n": 2}], "paging": {"next": "http://page3"}},
            "http://page3": {"data": [{"n": 3}]},
        }
        got = be.fetch_cloudcasts("someone", fetch_json=pages.__getitem__)
        self.assertEqual(got, [{"n": 1}, {"n": 2}, {"n": 3}])

    def test_stops_if_next_repeats(self):
        loop = {"data": [{"n": 1}], "paging": {"next": "http://same"}}
        got = be.fetch_cloudcasts("someone", fetch_json=lambda url: loop)
        self.assertEqual(len(got), 2)

    def test_missing_data_key_is_empty(self):
        self.assertEqual(be.fetch_cloudcasts("x", fetch_json=lambda u: {}), [])


class DataFile(unittest.TestCase):
    def test_missing_file_gives_empty_snapshot(self):
        self.assertEqual(be.load_data("/no/such/file.json"),
                         {"number_overrides": {}, "episodes": {}})

    def test_round_trip_is_deterministic(self):
        data = {"number_overrides": {"/k/": 2},
                "episodes": {"2": {"title": "Café", "number": 2}}}
        text = be.dump_data(data)
        self.assertTrue(text.endswith("\n"))
        self.assertIn("Café", text)  # not \u-escaped
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(be.load_data(path), data)
        self.assertEqual(be.dump_data(json.loads(text)), text)


if __name__ == "__main__":
    unittest.main()
