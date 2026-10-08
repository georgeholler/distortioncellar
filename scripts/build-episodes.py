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
PREFIX_RE = re.compile(r"^\s*Distortion Cel+\w*\s*-\s*", re.IGNORECASE)
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
