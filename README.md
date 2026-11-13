# DR Tourism Intelligence

Live dashboard for Dominican Republic tourism, with a Puerto Plata section, a press feed, and a regional comparison.

## How the data flows

| File | Source | How it updates |
|---|---|---|
| `data/news.json` | Google News RSS + DR1 WordPress API | GitHub Action, every 6 hours |
| `data/worldbank.json` | World Bank API (UN Tourism data) | GitHub Action, every 6 hours |
| `data/monthly.json` | MITUR monthly press briefings | **By hand** (no API exists) |

The page reads those JSON files and re-checks them every 10 minutes while open.

## Updating the MITUR numbers

After each monthly press conference, edit `data/monthly.json`:
add a row to `months`, add a checkpoint to `ytd`, change `last_edited`. Keep the `url` so there's always a source.

## Run locally

Opening `index.html` by double-click won't load the data (browsers block `fetch` on `file://`). Use:

```
python3 -m http.server 8000
```

then open http://localhost:8000

## Refresh the data on demand

GitHub → **Actions** → **Update tourism data** → **Run workflow**.

If the data ever stops updating, check the Actions tab. GitHub can pause scheduled workflows on repos with no recent activity; re-enabling takes one click.
