#!/usr/bin/env python3
"""Update the "Latest Show" link in index.html from the Mixcloud account feed.

Reads the newest cloudcast from https://api.mixcloud.com/<user>/cloudcasts/
and rewrites the href of the <a> tag whose text is "Latest Show".

Usage:
  scripts/update-latest-show.py             # update index.html in place
  scripts/update-latest-show.py --dry-run   # show what would change
  scripts/update-latest-show.py --user someoneelse --file other.html
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_USER = "distortioncellar"
DEFAULT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html"
)
API = "https://api.mixcloud.com/{user}/cloudcasts/?limit=10"

# Matches the href of an <a ...>Latest Show</a> tag. [^>] keeps the match inside
# the opening tag, so it works whether or not the attributes span several lines.
LINK_RE = re.compile(
    r'(<a\b[^>]*?href=")([^"]*)("[^>]*>\s*Latest Show\s*</a>)',
    re.IGNORECASE,
)


def fetch_latest(user):
    """Return (url, name) of the most recent cloudcast for `user`."""
    req = urllib.request.Request(
        API.format(user=user),
        headers={"User-Agent": "distortioncellar-site-updater/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)

    shows = payload.get("data") or []
    if not shows:
        raise SystemExit("No cloudcasts found for user '%s'." % user)

    # The API returns newest-first, but sort defensively in case that changes.
    shows.sort(key=lambda s: s.get("created_time", ""), reverse=True)
    latest = shows[0]

    url = latest.get("url")
    if not url:
        raise SystemExit("Latest cloudcast has no url field.")
    return url, latest.get("name", "(untitled)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", default=DEFAULT_USER, help="Mixcloud username")
    parser.add_argument("--file", default=DEFAULT_FILE, help="HTML file to update")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the change without writing the file")
    args = parser.parse_args()

    try:
        url, name = fetch_latest(args.user)
    except urllib.error.URLError as exc:
        raise SystemExit("Could not reach the Mixcloud API: %s" % exc)

    with open(args.file, encoding="utf-8") as fh:
        html = fh.read()

    match = LINK_RE.search(html)
    if not match:
        raise SystemExit(
            'No <a ...>Latest Show</a> link found in %s.' % args.file
        )

    current = match.group(2)
    print("Latest show: %s" % name)
    print("  url:     %s" % url)
    print("  current: %s" % current)

    if current == url:
        print("Already up to date; nothing to do.")
        return 0

    updated = html[:match.start()] + match.group(1) + url + match.group(3) + html[match.end():]

    if args.dry_run:
        print("Dry run: would update %s" % args.file)
        return 0

    with open(args.file, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("Updated %s" % args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
