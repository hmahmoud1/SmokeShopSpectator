# SmokeShopSpectator

A self-updating news page for tobacco, vape, hemp, and kratom news, with Ohio and Cleveland stories pulled to the top. Every 30 minutes a GitHub Actions job fetches the feeds, tags each story, and publishes the page to GitHub Pages.

## Files

| File | What it does |
|---|---|
| `feeds.json` | The news sources and the tag keywords. This is the only file you normally edit. |
| `build.py` | Fetches the feeds, removes duplicates, tags stories, and writes `index.html` and `stories.json`. |
| `template.html` | The page layout, styling, and the filter/search code. |
| `requirements.txt` | Python dependency (`feedparser`). |
| `../.github/workflows/smokeshopspectator.yml` | The 30-minute schedule and the Pages deployment. Must sit at the repo root. |

## One-time setup

1. Copy `SmokeShopSpectator/` into the root of the Warehouse repo, and copy `.github/workflows/smokeshopspectator.yml` into the repo's `.github/workflows/` folder.
2. Commit and push to `main`.
3. In the repo on GitHub, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to the **Actions** tab, open **SmokeShopSpectator**, and click **Run workflow** for the first build.
5. The page will be at `https://hmahmoud1.github.io/Warehouse/`.

GitHub Pages on a free account requires the repo to be public. The page only shows public news headlines.

## Run it on your own computer

```bash
cd SmokeShopSpectator
pip install -r requirements.txt
python build.py
# open _site/index.html in a browser
```

## Adding or fixing a source

Add an entry to `sources` in `feeds.json`:

```json
{ "name": "Site name", "group": "Industry", "url": "https://example.com/feed/", "relevant_only": false }
```

- `group` controls which heading it appears under in the Sources box.
- `relevant_only: true` keeps only stories that match a product tag. Use it for general news sites like Ohio Capital Journal.
- If a site has no RSS feed, use a Google News search instead: `https://news.google.com/rss/search?q=site:example.com+when:30d&hl=en-US&gl=US&ceid=US:en`
- If the page shows a source as "not responding" for several updates in a row, its feed address has probably changed. Find the new one on the site (often `/feed/` or `/rss`) or switch it to a Google News search.

## Tags

Tags in `feeds.json` mirror the SKU compliance tags planned for the inventory system (flavored, vape & nicotine, hemp/THC, kratom, FDA, and so on). Add keywords to a tag's list to widen what it catches. Tags with `"kind": "local"` feed the Ohio & Cleveland section.

## Good to know

- GitHub disables scheduled workflows in a public repo after 60 days with no commits. If updates stop, push any small change or click **Run workflow**, and the schedule resumes.
- Stories older than 30 days drop off (`max_age_days` in `feeds.json`).
- `stories.json` is published next to the page, so the same data can be loaded into SQL Server or matched against SKUs later.
