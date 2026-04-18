# Fuel Price Scraper

Small Python 3 script that refreshes `data.json` at the project root with
current retail petrol and diesel prices for every city in the India Fuel
Price Map. The frontend loads `data.json` on page load and shows a
"last updated" timestamp.

## Sources (priority order)

| # | Source | Coverage | Req/city |
|---|--------|----------|----------|
| 1 | `bankbazaar.com` | ~180+ major & minor cities | 2 (petrol + diesel separately) |
| 2 | `petroldieselprice.com` | ~200+ cities incl. NE India & hill stations | 1 (both fuels in one page) |

The scraper tries bankbazaar first. If either fuel's price is missing after
bankbazaar, it falls back to petroldieselprice. If both fail for a city the
previous value is kept and the city is logged as a miss.

**bankbazaar** requires a `Referer: https://www.google.co.in/` header to pass
Cloudflare bot detection — this is included in the scraper automatically.

**petroldieselprice** uses a JSON-LD description sentence (`"petrol price in
{City} is ₹X per litre and the diesel price is ₹Y per litre"`) which is
stable and easy to parse.

## How it works

1. Reads `data.json` (or bootstraps it from `data.js` on first run).
2. For each city, tries each source in order until both petrol & diesel are found.
3. Writes `data.json` back with updated prices and a UTC `lastUpdated` timestamp.
4. The frontend picks up the new file on next page load.

## Usage

From the project root:

```bash
# Refresh everything (~8–12 minutes for ~240 cities).
python3 scraper/scrape.py --verbose

# Test a few cities without writing data.json.
python3 scraper/scrape.py --dry-run --city "Mumbai" --city "Imphal" --city "Gangtok" -v

# Refresh a single city in place.
python3 scraper/scrape.py --city "Jaipur"
```

Exit code is `0` on success, `2` if `--city` matched nothing.

## Schedule

A Claude scheduled task named **`fuel-price-scraper-daily`** runs this
script every day at 08:15 local time. Manage it from the Scheduled
section of the sidebar, or with the scheduled-tasks MCP tools.

To use system cron instead, add this to `crontab -e`:

```cron
15 8 * * * cd /Users/nthok0714/Projects/fuel-price-map && /usr/bin/python3 scraper/scrape.py >> /tmp/fuel-scrape.log 2>&1
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every city misses on bankbazaar | Their markup changed — find the new hero price element and update `_BB_HERO_RE` |
| Every city misses on petroldieselprice | Check `_PDP_RE`; their description sentence format may have changed |
| A specific city always misses both sources | Add the correct slug to `SLUG_OVERRIDES` in `scrape.py` |
| 403 from bankbazaar | Increase `REQUEST_DELAY_SEC` or check `_BB_HEADERS` |
| 500 from petroldieselprice | Transient — retry; their server occasionally blips |

## Adding new cities

1. Add the city to `data.js` (name, state, lat, lng, seed petrol/diesel values).
2. Delete `data.json` and re-run the scraper to pick up the new entry:
   ```bash
   rm data.json && python3 scraper/scrape.py --verbose
   ```
