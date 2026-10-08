# Previous Episodes — Design

## Goal

A "Previous Episodes" page listing every episode on the Distortion Cellar
Mixcloud account. Each episode has its own page at a stable, shareable URL,
where George can add notes (e.g. tracklist, commentary).

## Constraints

- Static site on GitHub Pages: no backend, no build service, no dependencies.
- Python 3 standard library only, matching `scripts/update-latest-show.py`.
- Notes are edited as files and committed directly to `main`.
- Call each item an "episode" (not "show") in all new pages and UI text.
  The existing "Latest Show" button, `update-latest-show.py` and
  `themed-shows.html` are unchanged.

## Files

| Path | Purpose |
| --- | --- |
| `scripts/build-episodes.py` | Fetches episodes from Mixcloud and generates all pages |
| `episodes/data.json` | Committed snapshot of episode metadata plus manual overrides |
| `episodes/notes/ep-N.md` | George's notes for episode N. Created once as a stub (a single HTML comment, so a new episode shows no Notes box) and never overwritten |
| `episodes/ep-N.html` | Generated episode page |
| `previous-episodes.html` | Generated list page, newest first |
| `index.html` | Gains a "Previous Episodes" card in the Explore grid |
| `README.md` | Page table and workflow updated |

## URLs

The key is the episode number, parsed from the Mixcloud title with a
case-insensitive pattern accepting `Ep 13`, `Ep13`, `Episode 2`, `Show 1`.
The page URL is `/episodes/ep-13.html`. Mixcloud slugs are not used (they are
inconsistent). If a title does not parse, the script exits with an error naming the title and the Mixcloud key; the number is set by adding the key to "number_overrides" in episodes/data.json and is kept on later runs. Duplicate episode numbers are an error.

## Data flow

1. Fetch `https://api.mixcloud.com/distortioncellar/cloudcasts/?limit=100`,
   following `paging.next` until exhausted.
2. Merge into `episodes/data.json`, keyed by episode number. Stored per
   episode: number, title, Mixcloud URL, Mixcloud key (used for the embed),
   episode date (the date in the title when present and not later than the upload date, otherwise the Mixcloud upload date), tags, artwork URL. Manual overrides in `data.json` win over
   fetched values.
3. If the API is unreachable, build from the existing `data.json` and warn.
4. For each episode, create `episodes/notes/ep-N.md` (stub heading only) if
   missing. Existing notes files are never modified.
5. Render `episodes/ep-N.html` and `previous-episodes.html` from `data.json`
   and the notes, reusing `css/style.css` and the site header/footer markup.

## Episode page

Title, date, tags, artwork, Mixcloud embed player, a link to the episode on
Mixcloud, notes rendered from markdown, and previous/next episode links.
Works without JavaScript.

## Notes markdown

A small built-in converter supports headings, paragraphs, bulleted and numbered
lists, links, bold and italic. HTML in notes is escaped.
Markdown # / ## / ### render as h4 / h5 / h6, since the page itself uses h2 and h3.

## List page

One card per episode, newest first: artwork, title, date, linking to its
episode page. Reuses the existing card styling, with minimal CSS additions.

## CLI

`scripts/build-episodes.py [--dry-run] [--user NAME]`. `--dry-run` reports what
would be created or changed without writing.

## Testing

- Save an API response as a fixture; run the build against it offline.
- Title parsing is checked against all 13 current titles, including `Ep7`,
  `Episode 2` and `Show 1`.
- Unparseable titles and duplicate numbers fail with clear errors.
- Re-running the build is idempotent, and an edited notes file is untouched.
- Generated pages are checked for valid links (prev/next, list, Mixcloud).

## Out of scope

Search, tag filtering, comments, structured tracklists (go in the notes),
replacing `update-latest-show.py`, renaming "Latest Show".
