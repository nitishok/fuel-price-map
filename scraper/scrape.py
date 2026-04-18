#!/usr/bin/env python3
"""
Fuel price scraper for the India Fuel Price Map project.

Multi-source scraper that tries sources in priority order:
  1. bankbazaar.com        — hero price (font-size:32px anchor), 2 reqs per city
                             requires Google Referer header to bypass Cloudflare
  2. petroldieselprice.com — JSON-LD structured data, 1 req per city (both fuels)
                             broader coverage including NE India & hill stations

Reads the canonical dataset from data.json (or bootstraps from data.js),
fetches fresh prices, and writes back to data.json.

Design notes:
- Zero third-party dependencies (stdlib only).
- Respectful: 0.5s delay between requests, real User-Agent, 15s timeout.
- Graceful: if all sources fail for a city, previous price is kept.
- Slug overrides for cities whose URL slugs differ from canonical name.

Usage:
    python3 scraper/scrape.py [--dry-run] [--city "Mumbai"] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DATA_JSON = os.path.join(PROJECT_ROOT, "data.json")
DATA_JS = os.path.join(PROJECT_ROOT, "data.js")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
REQUEST_DELAY_SEC = 0.5
REQUEST_TIMEOUT_SEC = 15

# Canonical name -> candidate URL slugs (tried in order).
# If missing, the auto_slug() function derives one from the name.
SLUG_OVERRIDES: dict[str, list[str]] = {
    "Bengaluru": ["bangalore"],
    "Mysuru": ["mysore", "mysuru"],
    "Mangaluru": ["mangalore", "mangaluru"],
    "Hubballi": ["hubli", "hubballi"],
    "Belagavi": ["belgaum", "belagavi"],
    "Kalaburagi": ["gulbarga", "kalaburagi"],
    "Tiruchirappalli": ["trichy", "tiruchirappalli"],
    "Thiruvananthapuram": ["thiruvananthapuram", "trivandrum"],
    "Thoothukudi": ["tuticorin", "thoothukudi"],
    "Puducherry": ["pondicherry", "puducherry"],
    "Vadodara": ["vadodara", "baroda"],
    "Prayagraj": ["prayagraj", "allahabad"],
    "Kolkata": ["kolkata"],
    "Varanasi": ["varanasi", "benares"],
    "Gurugram": ["gurgaon", "gurugram"],
    "Dwarka (Delhi)": ["dwarka"],
}

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

# Extra headers needed by bankbazaar.com to pass Cloudflare bot detection.
_BB_HEADERS = {
    "Referer": "https://www.google.co.in/",
    "Accept-Language": "en-IN,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
}


def fetch_url(url: str, extra_headers: Optional[dict] = None) -> Optional[str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None

# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def auto_slug(name: str) -> str:
    """Derive a URL slug from a city name: lowercase, strip parens, dash-sep."""
    s = name.lower()
    s = re.sub(r"\s*\([^)]*\)", "", s)
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def candidate_slugs(name: str) -> list[str]:
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]
    return [auto_slug(name)]


def title_slug(name: str) -> str:
    """Derive a Title-Case slug for petroldieselprice.com: 'New Delhi' -> 'New-Delhi'."""
    s = re.sub(r"\s*\([^)]*\)", "", name).strip()
    return s.replace(" ", "-")


# ---------------------------------------------------------------------------
# Source 1: bankbazaar.com
# ---------------------------------------------------------------------------

# The hero price is the ONLY element with font-size:32px on the page.
_BB_HERO_RE = re.compile(
    r'font-size:32px[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*₹\s*(\d{2,3}(?:\.\d{1,2})?)'
)


def _bb_parse(html: str) -> Optional[float]:
    m = _BB_HERO_RE.search(html)
    if m:
        val = float(m.group(1))
        if 30.0 <= val <= 200.0:
            return val
    return None


def fetch_bankbazaar(name: str, verbose: bool = False) -> dict[str, Optional[float]]:
    """Return {"petrol": price|None, "diesel": price|None} from bankbazaar.
    Passes _BB_HEADERS to satisfy Cloudflare bot check."""
    result: dict[str, Optional[float]] = {"petrol": None, "diesel": None}
    for fuel in ("petrol", "diesel"):
        for slug in candidate_slugs(name):
            url = f"https://www.bankbazaar.com/fuel/{fuel}-price-{slug}.html"
            if verbose:
                print(f"    [bb] GET {url}", file=sys.stderr)
            html = fetch_url(url, extra_headers=_BB_HEADERS)
            if html is None:
                continue
            price = _bb_parse(html)
            if price is not None:
                result[fuel] = price
                break
        time.sleep(REQUEST_DELAY_SEC)
    return result


# ---------------------------------------------------------------------------
# Source 2: petroldieselprice.com
# ---------------------------------------------------------------------------

# JSON-LD on every page contains:
#   "petrol price in {City} is ₹{P} per litre and the diesel price is ₹{D} per litre"
_PDP_RE = re.compile(
    r"petrol price in .+? is ₹(\d{2,3}(?:\.\d{1,2})) per litre "
    r"and the diesel price is ₹(\d{2,3}(?:\.\d{1,2})) per litre"
)


def fetch_petroldieselprice(name: str, verbose: bool = False) -> dict[str, Optional[float]]:
    """Return {"petrol": price|None, "diesel": price|None} from petroldieselprice.com.
    One request gets both fuels."""
    result: dict[str, Optional[float]] = {"petrol": None, "diesel": None}

    # Try the title-cased slug first, then auto-slug variants
    slugs_to_try = [title_slug(name)]
    # Also try all candidate slugs in Title Case
    for cs in candidate_slugs(name):
        titled = cs.replace("-", " ").title().replace(" ", "-")
        if titled not in slugs_to_try:
            slugs_to_try.append(titled)

    for slug in slugs_to_try:
        url = f"https://www.petroldieselprice.com/petrol-diesel-price-in-{slug}"
        if verbose:
            print(f"    [pdp] GET {url}", file=sys.stderr)
        html = fetch_url(url)
        if html is None:
            continue
        m = _PDP_RE.search(html)
        if m:
            p, d = float(m.group(1)), float(m.group(2))
            if 30.0 <= p <= 200.0:
                result["petrol"] = p
            if 30.0 <= d <= 200.0:
                result["diesel"] = d
            if result["petrol"] and result["diesel"]:
                break

    return result


# ---------------------------------------------------------------------------
# Multi-source orchestrator
# ---------------------------------------------------------------------------

SOURCES = [
    ("bankbazaar", fetch_bankbazaar),
    ("petroldieselprice", fetch_petroldieselprice),
]


def fetch_all_sources(
    name: str, verbose: bool = False
) -> tuple[Optional[float], Optional[float], str]:
    """Try each source in order until both petrol & diesel are found.
    Returns (petrol, diesel, source_name)."""
    petrol: Optional[float] = None
    diesel: Optional[float] = None
    sources_used: list[str] = []

    for src_name, fetcher in SOURCES:
        if petrol is not None and diesel is not None:
            break  # already have both, done
        prices = fetcher(name, verbose=verbose)
        if petrol is None and prices["petrol"] is not None:
            petrol = prices["petrol"]
            sources_used.append(src_name)
        if diesel is None and prices["diesel"] is not None:
            diesel = prices["diesel"]
            if src_name not in sources_used:
                sources_used.append(src_name)
        time.sleep(REQUEST_DELAY_SEC)

    return petrol, diesel, "+".join(sources_used) if sources_used else ""


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

def bootstrap_from_data_js() -> dict:
    """Parse data.js once to bootstrap data.json on the first run."""
    with open(DATA_JS, "r", encoding="utf-8") as f:
        src = f.read()
    pattern = re.compile(
        r'\{\s*name:\s*"([^"]+)",\s*'
        r'state:\s*"([^"]+)",\s*'
        r'lat:\s*(-?\d+\.?\d*),\s*'
        r'lng:\s*(-?\d+\.?\d*),\s*'
        r'petrol:\s*(-?\d+\.?\d*),\s*'
        r'diesel:\s*(-?\d+\.?\d*)\s*\}'
    )
    cities = []
    for m in pattern.finditer(src):
        cities.append({
            "name": m.group(1),
            "state": m.group(2),
            "lat": float(m.group(3)),
            "lng": float(m.group(4)),
            "petrol": float(m.group(5)),
            "diesel": float(m.group(6)),
        })
    if not cities:
        raise RuntimeError("Could not parse any cities from data.js")
    return {"lastUpdated": None, "source": "bootstrap:data.js", "cities": cities}


def load_dataset() -> dict:
    if os.path.exists(DATA_JSON):
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return bootstrap_from_data_js()


def save_dataset(data: dict) -> None:
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Multi-source fuel price scraper")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write data.json; just print results.")
    parser.add_argument("--city", action="append", default=None,
                        help="Only scrape the named city (can repeat).")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    data = load_dataset()
    cities = data["cities"]
    targets = cities
    if args.city:
        wanted = {c.lower() for c in args.city}
        targets = [c for c in cities if c["name"].lower() in wanted]
        if not targets:
            print(f"No matching cities for: {args.city}", file=sys.stderr)
            return 2

    stats = {"petrol_ok": 0, "diesel_ok": 0, "miss": 0, "sources": {}}
    start = time.time()

    for idx, city in enumerate(targets, 1):
        name = city["name"]
        if args.verbose:
            print(f"[{idx}/{len(targets)}] {name}", file=sys.stderr)

        new_petrol, new_diesel, src = fetch_all_sources(name, verbose=args.verbose)

        updated = []
        if new_petrol is not None:
            if abs(new_petrol - city["petrol"]) > 0.001:
                updated.append(f"petrol {city['petrol']}->{new_petrol}")
            city["petrol"] = round(new_petrol, 2)
            stats["petrol_ok"] += 1
        if new_diesel is not None:
            if abs(new_diesel - city["diesel"]) > 0.001:
                updated.append(f"diesel {city['diesel']}->{new_diesel}")
            city["diesel"] = round(new_diesel, 2)
            stats["diesel_ok"] += 1
        if new_petrol is None and new_diesel is None:
            stats["miss"] += 1
            print(f"  MISS {name} (all sources failed)", file=sys.stderr)
        else:
            stats["sources"][src] = stats["sources"].get(src, 0) + 1
            if updated and args.verbose:
                print(f"  OK   {name} [{src}]: {', '.join(updated)}", file=sys.stderr)

    elapsed = time.time() - start
    n = len(targets)
    print(
        f"\nDone in {elapsed:.1f}s ({n} cities):\n"
        f"  petrol ok = {stats['petrol_ok']}/{n}\n"
        f"  diesel ok = {stats['diesel_ok']}/{n}\n"
        f"  total miss = {stats['miss']}/{n}\n"
        f"  sources breakdown: {json.dumps(stats['sources'], indent=4)}",
        file=sys.stderr,
    )

    data["lastUpdated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["source"] = "bankbazaar.com, petroldieselprice.com"

    if args.dry_run:
        print("--dry-run: not writing data.json", file=sys.stderr)
        return 0

    save_dataset(data)
    print(f"\nWrote {DATA_JSON}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
