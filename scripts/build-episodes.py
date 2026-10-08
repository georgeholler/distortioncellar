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
