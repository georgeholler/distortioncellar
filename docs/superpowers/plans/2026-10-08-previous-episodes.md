# Previous Episodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a "Previous Episodes" list page and one shareable page per Mixcloud episode, each showing notes George writes in a markdown file.

**Architecture:** One stdlib-only Python script, `scripts/build-episodes.py`, fetches the Mixcloud feed, merges it into a committed `episodes/data.json` snapshot, and renders static HTML (`episodes/ep-N.html`, `previous-episodes.html`). Notes live in `episodes/notes/ep-N.md`, which the script creates as a stub once and never rewrites. Tests are stdlib `unittest`, run against a saved API fixture, so nothing touches the network.

**Tech Stack:** Python 3.9 (the installed version; no `match`, no `X | Y` types), stdlib only, static HTML/CSS, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-07-previous-episodes-design.md`

## Global Constraints

- Python 3 standard library only, and it must run on Python 3.9.
- Static output, no JavaScript needed to read any generated page.
- New UI text and filenames say "episode", never "show". The existing "Latest Show" button, `scripts/update-latest-show.py` and `themed-shows.html` are NOT changed.
- URLs are `episodes/ep-N.html` where N is the episode number parsed from the Mixcloud title; Mixcloud slugs are never used for our URLs.
- `episodes/notes/ep-N.md` is never overwritten once it exists.
- Commit directly to `main`. No branches, no PRs.
- Every commit message ends with these two trailer lines (after a blank line):
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH`
- Run tests with: `python3 -m unittest discover -s tests -v` from the repo root.

## Review Focus

Spec-implied inputs no obvious happy-path test covers. Each has a test in the task named:

1. Notes containing raw HTML or a `javascript:` link must be escaped or dropped, not injected into the page (Task 3).
2. A title containing `&`, `<` or quotes (Ep 12 really has "Monk & Coltrane") must be escaped in the page and the list (Task 4).
3. Mixcloud unreachable: build from `data.json` with a warning; with no `data.json`, fail with a clear message instead of a traceback (Task 5).
4. Notes files with Windows (CRLF) line endings, or that contain only whitespace/the stub comment, must render sensibly (a whitespace-only file shows no empty "Notes" box) (Tasks 3 and 5).
5. An episode that disappears from the Mixcloud feed keeps its page and its notes (Task 5).

## File Structure

| Path | Responsibility |
| --- | --- |
| `scripts/build-episodes.py` | All logic: parsing, fetch, merge, markdown, rendering, build, CLI |
| `tests/loader.py` | Imports the hyphen-named script as module `be`; fixture helper |
| `tests/fixtures/cloudcasts.json` | Saved Mixcloud API response (13 episodes) |
| `tests/test_parsing.py` | Number/title parsing, record building, merging |
| `tests/test_fetch.py` | Paging and data.json load/save |
| `tests/test_markdown.py` | Notes markdown converter |
| `tests/test_render.py` | Episode page and list page HTML |
| `tests/test_build.py` | End-to-end build into a temp directory |
| `css/style.css` | Small additions for episode pages |
| `index.html`, `README.md` | Home card and docs |

---

### Task 1: Title parsing, records and merging

**Files:**
- Create: `tests/loader.py`, `tests/fixtures/cloudcasts.json`, `tests/test_parsing.py`
- Create: `scripts/build-episodes.py`

**Interfaces:**
- Produces (all in `scripts/build-episodes.py`):
  - `parse_episode_number(title, key="", number_overrides=None) -> int` (raises `ValueError`)
  - `display_title(title) -> str`
  - `to_record(cloudcast, number_overrides=None) -> dict` with keys `number, title, url, key, date, tags, image`
  - `merge_episodes(data, cloudcasts) -> dict` where `data` and the result are `{"number_overrides": {key: int}, "episodes": {"13": record_with_"override"_dict}}`
  - `effective(episode) -> dict` (record with its `override` dict applied)
- Produces in `tests/loader.py`: `be` (the loaded module), `load_fixture() -> dict`.

- [ ] **Step 1: Save the API fixture and write the loader**

```bash
mkdir -p tests/fixtures
curl -s -A "distortioncellar-site-updater/1.0" \
  "https://api.mixcloud.com/distortioncellar/cloudcasts/?limit=100" \
  | python3 -m json.tool > tests/fixtures/cloudcasts.json
python3 -c "import json; d=json.load(open('tests/fixtures/cloudcasts.json')); print(len(d['data']), d.get('paging'))"
```
Expected: `13` (or more if new episodes were posted) and a `paging` dict with no `next` key. If a `next` key is present, delete it from the fixture.

Create `tests/loader.py`:

```python
"""Loads scripts/build-episodes.py (hyphenated, so not importable) as `be`."""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "cloudcasts.json")


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_episodes", os.path.join(ROOT, "scripts", "build-episodes.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


be = _load()


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_parsing.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: error at import, `FileNotFoundError: ... scripts/build-episodes.py`.

- [ ] **Step 4: Write the implementation**

Create `scripts/build-episodes.py`:

```python
#!/usr/bin/env python3
"""Build the Previous Episodes pages from the Mixcloud account feed.

Fetches every cloudcast for the account, keeps a snapshot in
episodes/data.json, and writes:
  previous-episodes.html      the list of all episodes, newest first
  episodes/ep-N.html          one page per episode (N = episode number)
  episodes/notes/ep-N.md      notes for episode N, created once as a stub and
                              never overwritten -- edit these, then re-run.

Usage:
  scripts/build-episodes.py             # fetch, then write everything
  scripts/build-episodes.py --dry-run   # report what would change
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_USER = "distortioncellar"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.mixcloud.com/{user}/cloudcasts/?limit=100"

# "Ep 13", "Ep13", "Episode 2", "Show 1" (case-insensitive).
NUMBER_RE = re.compile(r"\b(?:episode|ep|show)\s*#?\s*(\d+)\b", re.IGNORECASE)
PREFIX_RE = re.compile(r"^\s*Distortion Cellar\s*-\s*", re.IGNORECASE)
TRAILING_DATE_RE = re.compile(r"\s*-\s*\d{4}[/-]\d{2}[/-]\d{2}\s*$")


def parse_episode_number(title, key="", number_overrides=None):
    """Return the episode number for a Mixcloud title (or its manual override)."""
    if number_overrides and key in number_overrides:
        return int(number_overrides[key])
    match = NUMBER_RE.search(title)
    if not match:
        raise ValueError(
            'Cannot find an episode number in the title %r. Add "%s": <number> '
            'to "number_overrides" in episodes/data.json and re-run.'
            % (title, key))
    return int(match.group(1))


def display_title(title):
    """Drop the 'Distortion Cellar - ' prefix and trailing date from a title."""
    cleaned = PREFIX_RE.sub("", title)
    cleaned = TRAILING_DATE_RE.sub("", cleaned).strip()
    return cleaned or title.strip()


def to_record(cloudcast, number_overrides=None):
    """Reduce a Mixcloud cloudcast to the fields we store."""
    pictures = cloudcast.get("pictures") or {}
    return {
        "number": parse_episode_number(
            cloudcast["name"], cloudcast["key"], number_overrides),
        "title": display_title(cloudcast["name"]),
        "url": cloudcast["url"],
        "key": cloudcast["key"],
        "date": cloudcast["created_time"][:10],
        "tags": [t["name"] for t in cloudcast.get("tags") or []],
        "image": (pictures.get("extra_large") or pictures.get("320wx320h")
                  or pictures.get("large") or ""),
    }


def merge_episodes(data, cloudcasts):
    """Merge fetched cloudcasts into the stored snapshot.

    Stored episodes missing from the feed are kept, and each episode's manual
    "override" dict survives refreshes.
    """
    overrides = data.get("number_overrides", {})
    episodes = dict(data.get("episodes", {}))
    seen = {}
    for cloudcast in cloudcasts:
        record = to_record(cloudcast, overrides)
        number = str(record["number"])
        if number in seen:
            raise ValueError("Episode %s appears twice on Mixcloud: %r and %r"
                             % (number, seen[number], record["title"]))
        seen[number] = record["title"]
        record["override"] = episodes.get(number, {}).get("override", {})
        episodes[number] = record
    return {"number_overrides": overrides, "episodes": episodes}


def effective(episode):
    """The episode record with its manual overrides applied."""
    merged = dict(episode)
    merged.update(episode.get("override") or {})
    return merged
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests in `test_parsing` PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/build-episodes.py tests/
git commit -m "Add episode parsing and merging for Previous Episodes" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

---

### Task 2: Fetching (with paging) and data.json storage

**Files:**
- Modify: `scripts/build-episodes.py` (append to end)
- Create: `tests/test_fetch.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `default_fetch_json(url) -> dict`
  - `fetch_cloudcasts(user, fetch_json=default_fetch_json) -> list` (all cloudcasts, following `paging.next`)
  - `load_data(path) -> dict` (empty snapshot `{"number_overrides": {}, "episodes": {}}` if the file is missing)
  - `dump_data(data) -> str` (deterministic JSON text ending in a newline)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetch.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s tests -p "test_fetch.py" -v`
Expected: FAIL/ERROR, `module 'build_episodes' has no attribute 'fetch_cloudcasts'`.

- [ ] **Step 3: Implement**

Append to `scripts/build-episodes.py`:

```python


def default_fetch_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "distortioncellar-site-updater/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_cloudcasts(user, fetch_json=default_fetch_json):
    """Return every cloudcast for `user`, following the API's paging links."""
    url = API.format(user=user)
    cloudcasts = []
    visited = set()
    while url and url not in visited:
        visited.add(url)
        payload = fetch_json(url)
        cloudcasts.extend(payload.get("data") or [])
        url = (payload.get("paging") or {}).get("next")
    return cloudcasts


def load_data(path):
    """Load the episodes/data.json snapshot (empty snapshot if missing)."""
    if not os.path.exists(path):
        return {"number_overrides": {}, "episodes": {}}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("number_overrides", {})
    data.setdefault("episodes", {})
    return data


def dump_data(data):
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-episodes.py tests/test_fetch.py
git commit -m "Add Mixcloud fetching and data.json storage" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

---

### Task 3: Notes markdown converter

**Files:**
- Modify: `scripts/build-episodes.py` (append)
- Create: `tests/test_markdown.py`

**Interfaces:**
- Produces: `render_markdown(text) -> str` (HTML fragment; `""` if there is no content), `render_inline(text) -> str`. Markdown `#` becomes `<h4>`, `##` `<h5>`, `###` and deeper `<h6>` (the page's own headings use h2/h3).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_markdown.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s tests -p "test_markdown.py" -v`
Expected: ERROR/FAIL, `no attribute 'render_markdown'`.

- [ ] **Step 3: Implement**

Append to `scripts/build-episodes.py`:

```python


# --- Notes markdown -----------------------------------------------------------
# Deliberately tiny: headings, paragraphs, lists, links, bold, italic. All text
# is HTML-escaped first, so nothing typed in a notes file becomes markup.

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
STAR_ITALIC_RE = re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])")
UNDERSCORE_ITALIC_RE = re.compile(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)")
SAFE_URL_RE = re.compile(r"^(https?://|mailto:|/|#|[^:]*$)", re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.+)$")


def _emphasis(escaped):
    escaped = BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = STAR_ITALIC_RE.sub(r"<em>\1</em>", escaped)
    return UNDERSCORE_ITALIC_RE.sub(r"<em>\1</em>", escaped)


def render_inline(text):
    """Escape `text` and apply links, bold and italic."""
    escaped = html.escape(text, quote=True)
    out = []
    pos = 0
    for match in LINK_RE.finditer(escaped):
        out.append(_emphasis(escaped[pos:match.start()]))
        label, url = match.group(1), match.group(2)
        if SAFE_URL_RE.match(url):
            out.append('<a href="%s">%s</a>' % (url, _emphasis(label)))
        else:
            out.append(_emphasis(match.group(0)))
        pos = match.end()
    out.append(_emphasis(escaped[pos:]))
    return "".join(out)


def render_markdown(text):
    """Convert notes markdown to an HTML fragment ('' if there is no content)."""
    lines = COMMENT_RE.sub("", text).splitlines()
    blocks = []
    para = []
    items = []
    list_tag = [None]

    def flush():
        if para:
            blocks.append("<p>%s</p>" % render_inline(" ".join(para)))
            del para[:]
        if items:
            blocks.append("<%s>%s</%s>" % (
                list_tag[0],
                "".join("<li>%s</li>" % render_inline(i) for i in items),
                list_tag[0]))
            del items[:]
            list_tag[0] = None

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = HEADING_RE.match(line)
        bullet = BULLET_RE.match(line)
        numbered = NUMBERED_RE.match(line)
        if heading:
            flush()
            level = min(len(heading.group(1)), 3) + 3  # '#' -> h4 ... h6
            blocks.append("<h%d>%s</h%d>"
                          % (level, render_inline(heading.group(2)), level))
        elif bullet or numbered:
            tag = "ul" if bullet else "ol"
            if para or (items and list_tag[0] != tag):
                flush()
            list_tag[0] = tag
            items.append((bullet or numbered).group(1))
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return "\n".join(blocks)
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS. If `test_underscore_italic_but_not_inside_words` fails, adjust only the regexes above, not the test.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-episodes.py tests/test_markdown.py
git commit -m "Add notes markdown converter" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

---

### Task 4: Page rendering and CSS

**Files:**
- Modify: `scripts/build-episodes.py` (append), `css/style.css`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `effective(episode)`, `render_markdown` are NOT called here; notes arrive as an HTML string.
- Produces:
  - `episode_filename(number) -> str` (`"ep-13.html"`)
  - `render_episode_page(episode, notes_html, prev_episode=None, next_episode=None) -> str` (full HTML document, lives in `episodes/`, so site paths start with `../`)
  - `render_list_page(episodes) -> str` (full HTML document, lives at the site root; `episodes` is a list of stored records in any order)
  - Episode arguments are stored records (with an optional `override`); the functions apply `effective()` themselves.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render.py`:

```python
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
        self.assertIn("Previous Episodes", page)

    def test_titles_are_escaped(self):
        page = be.render_list_page([make_ep(12, title="Monk & <b>Trane</b>")])
        self.assertIn("Monk &amp; &lt;b&gt;Trane&lt;/b&gt;", page)

    def test_empty_list_still_renders(self):
        self.assertIn("Previous Episodes", be.render_list_page([]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s tests -p "test_render.py" -v`
Expected: ERROR, `no attribute 'render_episode_page'`.

- [ ] **Step 3: Implement the renderers**

Append to `scripts/build-episodes.py`:

```python


# --- Page rendering -----------------------------------------------------------

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>%(title)s — Distortion Cellar</title>
  <meta name="description" content="%(description)s">
  <link rel="stylesheet" href="%(root)scss/style.css">
</head>
<body>

  <header class="site-header">
    <h1 class="brand">Distortion Cellar</h1>
    <p class="tagline">%(tagline)s</p>
  </header>

  <main class="wrap">
    <!-- Generated by scripts/build-episodes.py. Edit episodes/notes/ep-N.md, not this file. -->
%(body)s
  </main>

  <footer class="site-footer">
    <p>Contact: <a href="mailto:distortioncellar@gmail.com">distortioncellar@gmail.com</a></p>
    <p>&copy; <span id="year">2026</span> Distortion Cellar</p>
  </footer>

  <script>document.getElementById('year').textContent = new Date().getFullYear();</script>
</body>
</html>
"""


def page_html(title, description, tagline, body, root=""):
    """Wrap `body` (trusted HTML) in the site chrome. Other args are plain text."""
    return PAGE_TEMPLATE % {
        "title": html.escape(title),
        "description": html.escape(description, quote=True),
        "tagline": html.escape(tagline),
        "root": root,
        "body": body,
    }


def episode_filename(number):
    return "ep-%d.html" % number


def embed_url(key):
    return ("https://www.mixcloud.com/widget/iframe/?hide_cover=1&feed="
            + urllib.parse.quote(key, safe=""))


def render_episode_page(episode, notes_html, prev_episode=None, next_episode=None):
    ep = effective(episode)
    esc = html.escape
    title = esc(ep["title"])
    meta = " &middot; ".join([esc(ep["date"])] + [esc(t) for t in ep["tags"]])
    parts = [
        "    <section>",
        "      <h2>%s</h2>" % title,
        '      <p class="episode-meta">%s</p>' % meta,
    ]
    if ep.get("image"):
        parts.append('      <figure class="episode-art"><img src="%s" alt="%s"></figure>'
                     % (esc(ep["image"], quote=True), title))
    parts.append(
        '      <iframe class="episode-player" height="120" src="%s" title="%s"'
        ' loading="lazy"></iframe>'
        % (esc(embed_url(ep["key"]), quote=True), title))
    parts.append(
        '      <p><a class="button" href="%s" target="_blank" rel="noopener">'
        "Listen on Mixcloud</a></p>" % esc(ep["url"], quote=True))
    if notes_html.strip():
        parts.append('      <div class="episode-notes">\n'
                     "        <h3>Notes</h3>\n%s\n      </div>" % notes_html)

    prev_link = next_link = "<span></span>"
    if prev_episode:
        prev_link = '<a href="%s">&larr; %s</a>' % (
            episode_filename(prev_episode["number"]),
            esc("Ep %d" % prev_episode["number"]))
    if next_episode:
        next_link = '<a href="%s">%s &rarr;</a>' % (
            episode_filename(next_episode["number"]),
            esc("Ep %d" % next_episode["number"]))
    parts.append(
        '      <nav class="episode-nav">%s'
        '<a href="../previous-episodes.html">All episodes</a>%s</nav>'
        % (prev_link, next_link))
    parts.append("    </section>")
    return page_html(ep["title"], "Distortion Cellar episode: " + ep["title"],
                     "Previous Episodes", "\n".join(parts), root="../")


def render_list_page(episodes):
    esc = html.escape
    cards = []
    for ep in sorted((effective(e) for e in episodes),
                     key=lambda e: e["number"], reverse=True):
        image = ""
        if ep.get("image"):
            image = '<img src="%s" alt="" loading="lazy">' % esc(ep["image"], quote=True)
        cards.append(
            '        <a class="card episode-card" href="episodes/%s">\n'
            "          %s\n"
            "          <div><h3>%s</h3><p>%s</p></div>\n"
            "        </a>"
            % (episode_filename(ep["number"]), image, esc(ep["title"]), esc(ep["date"])))
    body = "\n".join([
        "    <section>",
        "      <h2>Previous Episodes</h2>",
        "      <p>Every episode of the show, newest first. Open one for its notes"
        " and a link you can share.</p>",
        '      <div class="episode-list">',
        "\n".join(cards),
        "      </div>",
        '      <a class="back-link" href="index.html">&larr; Back to home</a>',
        "    </section>",
    ])
    return page_html("Previous Episodes", "Every Distortion Cellar episode.",
                     "Previous Episodes", body)
```

- [ ] **Step 4: Add the CSS**

Use Edit on `css/style.css` to insert this block immediately above the line `/* --- Larger screens ------------------------------------------------------- */`:

```css
/* --- Episodes ------------------------------------------------------------- */
.episode-meta { color: var(--color-muted); margin: 0.25rem 0 1rem; }

.episode-art img {
  width: 100%;
  max-width: 320px;
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
}

.episode-player { display: block; width: 100%; border: 0; margin: 1rem 0; }

.episode-notes h3 {
  color: var(--color-accent-2);
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}
.episode-notes h4,
.episode-notes h5,
.episode-notes h6 { color: var(--color-link-yellow); margin: 1.25rem 0 0.4rem; }
.episode-notes a { color: var(--color-link-yellow); text-decoration: underline; }

.episode-nav {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 2rem;
  font-size: 0.95rem;
}

.episode-list { display: grid; grid-template-columns: 1fr; gap: var(--gap); margin-top: 1.25rem; }
.episode-card { display: flex; align-items: center; gap: 1rem; }
.episode-card img {
  width: 72px;
  height: 72px;
  flex: none;
  object-fit: cover;
  border-radius: 8px;
}
.episode-card h3 { font-size: 1.05rem; }

```

- [ ] **Step 5: Run all tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/build-episodes.py tests/test_render.py css/style.css
git commit -m "Add episode and list page rendering" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

---

### Task 5: Build orchestration, CLI and first real run

**Files:**
- Modify: `scripts/build-episodes.py` (append)
- Create: `tests/test_build.py`
- Generated and committed: `episodes/data.json`, `episodes/ep-*.html`, `episodes/notes/ep-*.md`, `previous-episodes.html`

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces:
  - `stub_notes(number) -> str`
  - `write_file(root, rel, content, dry_run, log, only_if_missing=False) -> None` logs `created|updated|unchanged <rel>`
  - `build(root, user=DEFAULT_USER, fetch_json=default_fetch_json, dry_run=False, log=print) -> None`; may raise `ValueError` (bad titles/duplicates) or `SystemExit` (API down and no snapshot)
  - `main(argv=None) -> int`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s tests -p "test_build.py" -v`
Expected: all ERROR, `no attribute 'build'`.

- [ ] **Step 3: Implement**

Append to `scripts/build-episodes.py`:

```python


# --- Build --------------------------------------------------------------------

def stub_notes(number):
    return ("<!-- Notes for episode %d. Delete this line and write your notes "
            "in markdown. -->\n" % number)


def write_file(root, rel, content, dry_run, log, only_if_missing=False):
    """Write `content` to root/rel, logging created / updated / unchanged."""
    path = os.path.join(root, *rel.split("/"))
    existing = None
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as fh:
            existing = fh.read()
    if existing is not None and (only_if_missing or existing == content):
        log("unchanged %s" % rel)
        return
    log("%s %s" % ("created" if existing is None else "updated", rel))
    if dry_run:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)


def read_notes(root, number):
    path = os.path.join(root, "episodes", "notes", "ep-%d.md" % number)
    if not os.path.exists(path):
        return stub_notes(number)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def build(root, user=DEFAULT_USER, fetch_json=default_fetch_json,
          dry_run=False, log=print):
    data_rel = "episodes/data.json"
    data = load_data(os.path.join(root, "episodes", "data.json"))
    try:
        cloudcasts = fetch_cloudcasts(user, fetch_json)
    except OSError as exc:  # URLError, HTTPError and timeouts all land here
        if not data["episodes"]:
            raise SystemExit(
                "Could not reach Mixcloud (%s) and there is no saved "
                "episodes/data.json to build from." % exc)
        log("WARNING: could not reach Mixcloud (%s); building from the saved "
            "episodes/data.json" % exc)
    else:
        data = merge_episodes(data, cloudcasts)

    episodes = sorted(data["episodes"].values(), key=lambda e: e["number"])
    write_file(root, data_rel, dump_data(data), dry_run, log)
    for index, episode in enumerate(episodes):
        number = episode["number"]
        write_file(root, "episodes/notes/ep-%d.md" % number, stub_notes(number),
                   dry_run, log, only_if_missing=True)
        prev_episode = episodes[index - 1] if index > 0 else None
        next_episode = episodes[index + 1] if index + 1 < len(episodes) else None
        page = render_episode_page(
            episode, render_markdown(read_notes(root, number)),
            prev_episode, next_episode)
        write_file(root, "episodes/" + episode_filename(number), page, dry_run, log)
    write_file(root, "previous-episodes.html", render_list_page(episodes),
               dry_run, log)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", default=DEFAULT_USER, help="Mixcloud username")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing files")
    args = parser.parse_args(argv)
    try:
        build(ROOT, user=args.user, dry_run=args.dry_run)
    except ValueError as exc:
        raise SystemExit("Error: %s" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all PASS.

- [ ] **Step 5: Dry-run against the real Mixcloud feed**

Run: `python3 scripts/build-episodes.py --dry-run`
Expected: lines like `created episodes/ep-13.html`, no traceback, and `git status` shows nothing new.

- [ ] **Step 6: Real run and visual check**

Run: `python3 scripts/build-episodes.py`
Then: `python3 -m http.server 8000` (background), open `http://localhost:8000/previous-episodes.html` and `http://localhost:8000/episodes/ep-12.html`. Confirm: list is newest first with artwork, the Ep 12 title shows "Monk & Coltrane" correctly, the Mixcloud player loads, prev/next links work, layout is fine at phone width. Stop the server. Then run the script a second time and confirm every line starts with `unchanged`.

- [ ] **Step 7: Commit script, tests and generated files**

```bash
git add scripts/build-episodes.py tests/test_build.py episodes previous-episodes.html
git commit -m "Add episode build and generate Previous Episodes pages" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

---

### Task 6: Home page card, README and spec alignment

**Files:**
- Modify: `index.html` (Explore grid, around line 52), `README.md`, `docs/superpowers/specs/2026-10-07-previous-episodes-design.md`

- [ ] **Step 1: Add the home card**

In `index.html`, directly after `<div class="card-grid">` and before the George Glossary card, insert:

```html
        <a class="card" href="previous-episodes.html">
          <h3>Previous Episodes</h3>
          <p>Every episode, with notes and a link you can share.</p>
        </a>
```

- [ ] **Step 2: Update the README**

In `README.md`, add this row to the Pages table (after the `index.html` row):

```
| `previous-episodes.html`  | Previous Episodes list (generated)        |
| `episodes/ep-N.html`      | One page per episode (generated)          |
```

Then add this section before "## Things to fill in":

````markdown
## Previous Episodes

Episode pages are generated from the Mixcloud feed. After posting a new episode:

```
python3 scripts/build-episodes.py        # add --dry-run to preview
```

Then commit and push. To add notes to an episode, edit
`episodes/notes/ep-N.md` (markdown: `# headings`, `- lists`, `[links](url)`,
`**bold**`, `*italic*`) and run the script again. The script creates the notes
file the first time it sees an episode and never overwrites it.

- Episode URLs are `episodes/ep-N.html`, where N is parsed from the Mixcloud
  title ("Ep 13", "Ep13", "Episode 13", "Show 13"). If a title has no number,
  the script stops; add `"<mixcloud key>": N` to `number_overrides` in
  `episodes/data.json` and run it again.
- To correct a title, date, tags or image for one episode, add an `override`
  object to that episode in `episodes/data.json`, e.g. `"override": {"date": "2026-10-04"}`.
- Tests: `python3 -m unittest discover -s tests -v`
````

- [ ] **Step 3: Align the spec with what was built**

In `docs/superpowers/specs/2026-10-07-previous-episodes-design.md`:
- In the Files table, change the `episodes/notes/ep-N.md` description to: `George's notes for episode N. Created once as a stub (a single HTML comment, so a new episode shows no Notes box) and never overwritten`.
- In the URLs section, replace the sentence beginning "If a title does not parse" with: `If a title does not parse, the script exits with an error naming the title and the Mixcloud key; the number is set by adding the key to "number_overrides" in episodes/data.json and is kept on later runs.`
- In "Notes markdown", append: `Markdown # / ## / ### render as h4 / h5 / h6, since the page itself uses h2 and h3.`

- [ ] **Step 4: Verify and commit**

Run: `python3 -m unittest discover -s tests -v` (all PASS), then open `index.html` via the local server and confirm the new card links to the list page.

```bash
git add index.html README.md docs/superpowers/specs/2026-10-07-previous-episodes-design.md
git commit -m "Link Previous Episodes from home page and document workflow" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0174tuQx6FabLZsMewyDbwUH"
```

- [ ] **Step 5: Push**

Only after George confirms the pages look right locally: `git push origin main`.
