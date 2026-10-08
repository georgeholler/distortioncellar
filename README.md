# Distortion Cellar

Website for the **Distortion Cellar** internet radio show. A plain static site
— no build step, no dependencies. Open `index.html` in a browser to preview.

## Pages

| File                      | Purpose                                   |
| ------------------------- | ----------------------------------------- |
| `index.html`              | Home: hero image, description, Mixcloud links, contact, sub-page links |
| `previous-episodes.html`  | All Episodes list (generated)             |
| `episodes/ep-N.html`      | One page per episode (generated)          |
| `george-glossary.html`    | The George Glossary                       |
| `themed-shows.html`       | Themed Shows                              |
| `recurring-segments.html` | Recurring Segments                        |
| `biography.html`          | Mini Biography                            |
| `credits.html`            | Credits                                   |
| `policies.html`           | Policies                                  |
| `css/style.css`           | All styling (mobile-first, responsive)    |
| `images/`                 | Your images (add `hero.jpg`)              |

## All Episodes

Episode pages are generated from the Mixcloud feed. After posting a new episode:

```
python3 scripts/build-episodes.py        # add --dry-run to preview
```

The same command also points the home page's "Latest Episode" button at the
newest episode. Then commit and push. To add notes to an episode, edit
`episodes/notes/ep-N.md` (markdown: `# headings`, `- lists`, `[links](url)`,
`**bold**`, `*italic*`) and run the script again. The script creates the notes
file the first time it sees an episode and never overwrites it. Use one `- `
line per track in a tracklist; plain lines on consecutive rows run together
into a single paragraph.

- Episode URLs are `episodes/ep-N.html`, where N is parsed from the Mixcloud
  title ("Ep 13", "Ep13", "Episode 13", "Show 13"). If a title has no number,
  the script stops; add `"<mixcloud key>": N` to `number_overrides` in
  `episodes/data.json` and run it again.
- To correct a title, date, tags or image for one episode, add an `override`
  object to that episode in `episodes/data.json`, e.g. `"override": {"date": "2026-10-04"}`.
- Tests: `python3 -m unittest discover -s tests -v`

## Things to fill in

Search the HTML for `TODO`, `[ ... ]`, `YOUR-EMAIL`, and `YOUR-PROFILE`:

- **Home image** — add `images/hero.jpg`.
- **Show description** — the About section in `index.html`.
- **Mixcloud links** — replace `YOUR-PROFILE` in the two Mixcloud links.
- **Contact email** — replace `YOUR-EMAIL@example.com` in every page footer.
- **Sub-page content** — fill in the placeholder entries on each sub-page.

## Restyling

Open `css/style.css` and edit the variables in the `:root` block at the top
(colors, fonts, layout width). Changing those restyles the whole site.

## Publishing with GitHub Pages

Because this is a static site it can be hosted free on GitHub Pages:

1. Push this repo to GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to *Deploy from a branch*.
4. Choose the `main` branch and the `/ (root)` folder, then **Save**.
5. After a minute the site is live at
   `https://<your-username>.github.io/<repo-name>/`.

No configuration files are needed — GitHub serves `index.html` automatically.
