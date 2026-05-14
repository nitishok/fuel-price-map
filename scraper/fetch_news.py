#!/usr/bin/env python3
"""Fetch latest India fuel news from Google News RSS.

Saves news.json and generates news/index.html.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import urlopen
from urllib.error import URLError
from xml.etree import ElementTree as ET

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_JSON = os.path.join(PROJECT_ROOT, "news.json")
NEWS_DIR  = os.path.join(PROJECT_ROOT, "news")

RSS_URLS = [
    "https://news.google.com/rss/search?q=petrol+diesel+price+India&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=fuel+shortage+ration+India&hl=en-IN&gl=IN&ceid=IN:en",
]

IST = timezone(timedelta(hours=5, minutes=30))


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


def fetch_articles() -> list[dict]:
    seen: set[str] = set()
    articles: list[dict] = []

    for url in RSS_URLS:
        try:
            with urlopen(url, timeout=15) as resp:
                xml_data = resp.read()
        except (URLError, OSError) as e:
            print(f"  Warning: could not fetch {url}: {e}")
            continue

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            print(f"  Warning: XML parse error for {url}: {e}")
            continue

        channel = root.find("channel")
        if channel is None:
            continue

        for item in channel.findall("item"):
            raw_title = (item.findtext("title") or "").strip()
            link      = (item.findtext("link")  or "").strip()
            pub_str   = (item.findtext("pubDate") or "").strip()
            src_el    = item.find("source")
            source    = src_el.text.strip() if src_el is not None else ""

            # Google appends " - Source Name" to the title
            if source and raw_title.endswith(f" - {source}"):
                title = raw_title[: -(len(source) + 3)].strip()
            else:
                parts = raw_title.rsplit(" - ", 1)
                if len(parts) == 2 and len(parts[1]) < 60:
                    title = parts[0].strip()
                    if not source:
                        source = parts[1].strip()
                else:
                    title = raw_title

            key = title.lower()
            if key in seen:
                continue
            seen.add(key)

            try:
                pub_dt  = parsedate_to_datetime(pub_str)
                if (datetime.now(IST) - pub_dt.astimezone(IST)).days > 180:
                    continue
                pub_iso = pub_dt.isoformat()
                rel     = relative_time(pub_dt)
            except Exception:
                pub_iso = ""
                rel     = ""

            articles.append({
                "title":     title,
                "url":       link,
                "source":    source,
                "published": pub_iso,
                "relative":  rel,
            })

    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:25]


def save_json(articles: list[dict]) -> None:
    data = {
        "lastUpdated": datetime.now(IST).isoformat(),
        "articles":    articles,
    }
    with open(NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  news.json ({len(articles)} articles)")


def load_social_posts() -> list[dict]:
    """Load Reddit posts from social.json if available."""
    social_path = os.path.join(PROJECT_ROOT, "social.json")
    try:
        with open(social_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("posts", [])
    except Exception:
        return []


def generate_page(articles: list[dict]) -> None:
    os.makedirs(NEWS_DIR, exist_ok=True)
    updated_str = datetime.now(IST).strftime("%-d %b %Y, %-I:%M %p IST")
    posts = load_social_posts()

    news_rows = ""
    for a in articles:
        src  = f'<span class="ns-src">{a["source"]}</span>' if a["source"] else ""
        time = f'<span class="ns-time">{a["relative"]}</span>' if a["relative"] else ""
        news_rows += f"""
      <div class="col-item">
        <a class="col-title" href="{a['url']}" target="_blank" rel="noopener noreferrer">{a['title']}</a>
        <div class="col-meta">{src}{time}</div>
      </div>"""

    reddit_rows = ""
    for p in posts:
        src  = f'<span class="ns-src">{p["source"]}</span>' if p.get("source") else ""
        time = f'<span class="ns-time">{p["relative"]}</span>' if p.get("relative") else ""
        ups  = f'<span class="rd-ups">▲{p["upvotes"]}</span>' if p.get("upvotes") else ""
        reddit_rows += f"""
      <div class="col-item">
        <a class="col-title" href="{p['url']}" target="_blank" rel="noopener noreferrer">{p['title']}</a>
        <div class="col-meta">{src}{time}{ups}</div>
      </div>"""

    if not reddit_rows:
        reddit_rows = '<div class="col-empty">No Reddit posts available.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>India Fuel News &amp; Discussion – Petrol &amp; Diesel Updates | FuelPriceToday.in</title>
  <meta name="description" content="Latest news and community discussion on petrol and diesel prices in India. Fuel price hikes, shortages, government policy updates — updated hourly."/>
  <link rel="canonical" href="https://www.fuelpricetoday.in/news"/>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg"/>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f3f4f6;color:#1f2937}}
    .hdr{{background:linear-gradient(135deg,#0f766e,#0ea5e9);padding:13px 20px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
    .hdr-left{{display:flex;flex-direction:column;gap:2px}}
    .hdr-title{{font-size:18px;font-weight:700;color:#fff;text-decoration:none}}
    .brand-t{{color:#5eead4}}
    .brand-i{{color:rgba(255,255,255,.45);font-weight:500}}
    .hdr-sub{{font-size:12px;color:rgba(255,255,255,.82);margin:0;font-weight:400}}
    .hdr-nav{{color:rgba(255,255,255,.85);font-size:13px;text-decoration:none;white-space:nowrap;padding:6px 12px;border:1px solid rgba(255,255,255,.35);border-radius:6px}}
    .hdr-nav:hover{{background:rgba(255,255,255,.15)}}
    .wrap{{max-width:1100px;margin:0 auto;padding:24px 16px 48px}}
    h1{{font-size:22px;font-weight:700;color:#0f766e;margin-bottom:4px}}
    .page-sub{{font-size:13px;color:#6b7280;margin-bottom:20px}}
    .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
    .col-card{{background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.07)}}
    .col-head{{padding:14px 16px 10px;border-bottom:1px solid #f3f4f6;font-size:13px;font-weight:700;color:#111827;display:flex;align-items:center;gap:8px}}
    .col-badge{{font-size:10px;font-weight:600;padding:2px 6px;border-radius:4px;text-transform:uppercase}}
    .badge-news{{background:#dbeafe;color:#1e40af}}
    .badge-reddit{{background:#fee2e2;color:#991b1b}}
    .col-item{{padding:13px 16px;border-bottom:1px solid #f3f4f6}}
    .col-item:last-child{{border-bottom:none}}
    .col-title{{font-size:14px;color:#1a56db;text-decoration:none;line-height:1.45;font-weight:500;display:block;margin-bottom:4px}}
    .col-title:hover{{text-decoration:underline}}
    .col-meta{{display:flex;align-items:center;gap:6px}}
    .ns-src{{font-size:12px;color:#374151;font-weight:500}}
    .ns-time{{font-size:12px;color:#9ca3af}}
    .ns-time::before{{content:"·";margin-right:6px;color:#d1d5db}}
    .rd-ups{{font-size:12px;color:#059669}}
    .rd-ups::before{{content:"·";margin-right:6px;color:#d1d5db}}
    .col-empty{{padding:16px;font-size:13px;color:#9ca3af}}
    footer{{text-align:center;padding:20px;font-size:12px;color:#9ca3af}}
    @media(max-width:700px){{.two-col{{grid-template-columns:1fr}}.hdr{{flex-direction:column;align-items:flex-start;gap:8px}}}}
  </style>
</head>
<body>
<header class="hdr">
  <div class="hdr-left">
    <a href="/" class="hdr-title">⛽ FuelPrice<span class="brand-t">Today</span><span class="brand-i">.in</span></a>
    <p class="hdr-sub">Latest news &amp; discussion on petrol &amp; diesel prices in India.</p>
  </div>
  <a href="/" class="hdr-nav">← Live Map</a>
</header>
<div class="wrap">
  <h1>News &amp; Discussion</h1>
  <p class="page-sub">Updated {updated_str}</p>
  <div class="two-col">
    <div class="col-card">
      <div class="col-head"><span class="col-badge badge-news">News</span> India Fuel News &nbsp;·&nbsp; {len(articles)} stories</div>{news_rows}
    </div>
    <div class="col-card">
      <div class="col-head"><span class="col-badge badge-reddit">Reddit</span> Community Discussion &nbsp;·&nbsp; {len(posts)} posts</div>{reddit_rows}
    </div>
  </div>
</div>
<footer>&copy; 2026 fuelpricetoday.in &nbsp;·&nbsp; News sourced from Google News &nbsp;·&nbsp; Posts from Reddit</footer>
</body>
</html>"""

    with open(os.path.join(NEWS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  news/index.html")


def main():
    print("Fetching fuel news...")
    articles = fetch_articles()
    if not articles:
        print("  No articles fetched — skipping.")
        return
    save_json(articles)
    generate_page(articles)


if __name__ == "__main__":
    main()
