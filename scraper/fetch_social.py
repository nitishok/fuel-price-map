#!/usr/bin/env python3
"""Fetch latest India fuel-related posts from Reddit (public API, no auth needed).

Saves social.json for the website's "From Social Media" section.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL_JSON = os.path.join(PROJECT_ROOT, "social.json")

IST = timezone(timedelta(hours=5, minutes=30))

REDDIT_QUERIES = [
    "https://www.reddit.com/search.json?q=petrol+diesel+price+india&sort=new&t=week&limit=10",
    "https://www.reddit.com/search.json?q=fuel+shortage+india&sort=new&t=week&limit=8",
]

HEADERS = {"User-Agent": "fuelpricetoday.in/1.0 (news aggregator; contact@fuelpricetoday.in)"}

FUEL_KEYWORDS = {
    "petrol", "diesel", "fuel", "cng", "lpg", "oil price",
    "fuel price", "petrol price", "diesel price", "fuel shortage",
    "fuel hike", "fuel cut", "rationing", "petroleum",
}


def relative_time(dt: datetime) -> str:
    now = datetime.now(IST)
    dt_ist = dt.astimezone(IST)
    secs = int((now - dt_ist).total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        m = secs // 60
        return f"{m} min ago"
    if secs < 86400:
        h = secs // 3600
        return f"{h} hr{'s' if h > 1 else ''} ago"
    d = secs // 86400
    return f"{d} day{'s' if d > 1 else ''} ago"


def fetch_posts() -> list[dict]:
    seen: set[str] = set()
    posts: list[dict] = []

    for url in REDDIT_QUERIES:
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except (URLError, OSError, json.JSONDecodeError) as e:
            print(f"  Warning: {url}: {e}")
            continue

        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = (d.get("title") or "").strip()
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            # Skip posts with no fuel-related keywords in title
            if not any(kw in key for kw in FUEL_KEYWORDS):
                continue
            seen.add(key)

            permalink = d.get("permalink", "")
            post_url = f"https://www.reddit.com{permalink}" if permalink else d.get("url", "")
            subreddit   = d.get("subreddit", "")
            upvotes     = d.get("ups", 0)
            num_comments = d.get("num_comments", 0)
            created_utc = d.get("created_utc", 0)

            try:
                pub_dt  = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                pub_iso = pub_dt.isoformat()
                rel     = relative_time(pub_dt)
            except Exception:
                pub_iso = ""
                rel     = ""

            posts.append({
                "title":    title,
                "url":      post_url,
                "platform": "reddit",
                "source":   f"r/{subreddit}",
                "upvotes":  upvotes,
                "comments": num_comments,
                "published": pub_iso,
                "relative":  rel,
            })

    posts.sort(key=lambda p: p["published"], reverse=True)
    return posts[:20]


def save_json(posts: list[dict]) -> None:
    data = {
        "lastUpdated": datetime.now(IST).isoformat(),
        "posts": posts,
    }
    with open(SOCIAL_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  social.json ({len(posts)} posts)")


def main():
    print("Fetching social posts...")
    posts = fetch_posts()
    if not posts:
        print("  No posts fetched — skipping.")
        return
    save_json(posts)


if __name__ == "__main__":
    main()
