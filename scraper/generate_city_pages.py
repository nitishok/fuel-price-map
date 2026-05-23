#!/usr/bin/env python3
"""Generate individual city HTML pages from history.json.

Run after scrape.py has updated history.json:
    python3 scraper/generate_city_pages.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import urlopen
from urllib.error import URLError
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
HISTORY_JSON = os.path.join(PROJECT_ROOT, "history.json")
DATA_JSON = os.path.join(PROJECT_ROOT, "data.json")

IST = timezone(timedelta(hours=5, minutes=30))

CITY_STATES: dict[str, str] = {
    "Mumbai":             "Maharashtra",
    "New Delhi":          "Delhi",
    "Bengaluru":          "Karnataka",
    "Hyderabad":          "Telangana",
    "Ahmedabad":          "Gujarat",
    "Chennai":            "Tamil Nadu",
    "Kolkata":            "West Bengal",
    "Surat":              "Gujarat",
    "Pune":               "Maharashtra",
    "Jaipur":             "Rajasthan",
    "Lucknow":            "Uttar Pradesh",
    "Kanpur":             "Uttar Pradesh",
    "Nagpur":             "Maharashtra",
    "Indore":             "Madhya Pradesh",
    "Bhopal":             "Madhya Pradesh",
    "Visakhapatnam":      "Andhra Pradesh",
    "Patna":              "Bihar",
    "Vadodara":           "Gujarat",
    "Kochi":              "Kerala",
    "Coimbatore":         "Tamil Nadu",
    "Guwahati":           "Assam",
    "Ranchi":             "Jharkhand",
    "Chandigarh":         "Chandigarh",
    "Thiruvananthapuram": "Kerala",
    "Varanasi":           "Uttar Pradesh",
}

METRO_CITY_SLUGS: dict[str, str] = {
    "Mumbai": "mumbai",
    "New Delhi": "delhi",
    "Bengaluru": "bangalore",
    "Hyderabad": "hyderabad",
    "Ahmedabad": "ahmedabad",
    "Chennai": "chennai",
    "Kolkata": "kolkata",
    "Surat": "surat",
    "Pune": "pune",
    "Jaipur": "jaipur",
    "Lucknow": "lucknow",
    "Kanpur": "kanpur",
    "Nagpur": "nagpur",
    "Indore": "indore",
    "Bhopal": "bhopal",
    "Visakhapatnam": "visakhapatnam",
    "Patna": "patna",
    "Vadodara": "vadodara",
    "Kochi": "kochi",
    "Coimbatore": "coimbatore",
    "Guwahati": "guwahati",
    "Ranchi": "ranchi",
    "Chandigarh": "chandigarh",
    "Thiruvananthapuram": "thiruvananthapuram",
    "Varanasi": "varanasi",
}


def fmt_pub_date(iso: str) -> str:
    """Format an ISO datetime string as '15 May' or '15 May 2025'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso).astimezone(IST)
    except Exception:
        return ""
    now = datetime.now(IST)
    return f"{dt.day} {dt.strftime('%b')}" if dt.year == now.year else f"{dt.day} {dt.strftime('%b')} {dt.year}"


def fetch_city_news(city_name: str, state_name: str, max_articles: int = 5) -> list[dict]:
    """Fetch Google News RSS articles relevant to city/state fuel news."""
    query = f"petrol diesel price {city_name} {state_name}"
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        with urlopen(url, timeout=15) as resp:
            xml_data = resp.read()
    except (URLError, OSError) as e:
        print(f"  Warning: could not fetch news for {city_name}: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    articles: list[dict] = []
    seen: set[str] = set()
    for item in channel.findall("item"):
        raw_title = (item.findtext("title") or "").strip()
        link      = (item.findtext("link")  or "").strip()
        pub_str   = (item.findtext("pubDate") or "").strip()
        src_el    = item.find("source")
        source    = src_el.text.strip() if src_el is not None else ""

        if source and raw_title.endswith(f" - {source}"):
            title = raw_title[: -(len(source) + 3)].strip()
        else:
            parts = raw_title.rsplit(" - ", 1)
            title = parts[0].strip() if len(parts) == 2 and len(parts[1]) < 60 else raw_title
            if not source and len(parts) == 2:
                source = parts[1].strip()

        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        try:
            pub_dt  = parsedate_to_datetime(pub_str)
            if (datetime.now(IST) - pub_dt.astimezone(IST)).days > 180:
                continue
            pub_iso = pub_dt.isoformat()
        except Exception:
            pub_iso = ""

        articles.append({"title": title, "url": link, "source": source, "published": pub_iso})
        if len(articles) >= max_articles:
            break

    return articles


def format_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return date_str


def format_updated(updated_str: str | None, date_str: str) -> str:
    """Return human-readable 'DD Mon YYYY, HH:MM AM/PM IST' from ISO timestamp."""
    if updated_str:
        try:
            dt = datetime.strptime(updated_str[:16], "%Y-%m-%dT%H:%M")
            return dt.strftime("%-d %b %Y, %-I:%M %p IST")
        except ValueError:
            pass
    return format_date(date_str)


def get_last_scrape_timestamp() -> str:
    """Read lastUpdated from data.json, convert UTC → IST, return formatted string."""
    try:
        with open(DATA_JSON, encoding="utf-8") as f:
            data = json.load(f)
        utc_str = data.get("lastUpdated", "")
        if utc_str:
            from datetime import timezone, timedelta
            IST = timezone(timedelta(hours=5, minutes=30))
            dt_utc = datetime.fromisoformat(utc_str)
            dt_ist = dt_utc.astimezone(IST)
            return dt_ist.strftime("%-d %b %Y, %-I:%M %p IST")
    except Exception:
        pass
    return ""


def delta_html(current: float, previous: float | None) -> str:
    if previous is None:
        return ""
    diff = current - previous
    if abs(diff) < 0.005:
        return ""
    sign = "▲" if diff > 0 else "▼"
    color = "#dc2626" if diff > 0 else "#059669"
    return (
        f'<span style="color:{color};font-size:11px;font-weight:700;'
        f'margin-left:5px">{sign}{abs(diff):.2f}</span>'
    )


def generate_page(city_name: str, slug: str, entries: list[dict], all_cities: dict[str, str], scrape_ts: str = "", news: list[dict] | None = None, coords: dict | None = None) -> str:
    today = entries[0] if entries else None
    prev = entries[1] if len(entries) > 1 else None

    tp = today["petrol"] if today else 0.0
    td = today["diesel"] if today else 0.0
    tc = today.get("cng") if today else None
    pp = prev["petrol"] if prev else None
    pd = prev["diesel"] if prev else None

    today_date_str = scrape_ts or format_updated(
        entries[0].get("updated") if entries else None,
        entries[0]["date"] if entries else "",
    )

    petrol_delta = delta_html(tp, pp)
    diesel_delta = delta_html(td, pd)

    # Build history table rows (newest first)
    rows_html = ""
    for i, entry in enumerate(entries):
        prev_e = entries[i + 1] if i + 1 < len(entries) else None
        p_d = delta_html(entry["petrol"], prev_e["petrol"] if prev_e else None)
        d_d = delta_html(entry["diesel"], prev_e["diesel"] if prev_e else None)
        row_cls = "re" if i % 2 == 0 else "ro"
        today_badge = (
            ' <span class="today-badge">today</span>' if i == 0 else ""
        )
        cng_v = entry.get("cng")
        cng_td = "—" if cng_v is None else f"₹{cng_v:.2f}"
        rows_html += (
            f'<tr class="{row_cls}">'
            f'<td class="dc">{format_date(entry["date"])}{today_badge}</td>'
            f'<td class="np">₹{entry["petrol"]:.2f}{p_d}</td>'
            f'<td class="nd">₹{entry["diesel"]:.2f}{d_d}</td>'
            f'<td class="nd">{cng_td}</td>'
            f"</tr>\n"
        )

    if not rows_html:
        rows_html = '<tr><td colspan="4" class="empty">No history yet — check back tomorrow.</td></tr>'

    # Build station finder buttons
    city_coords = (coords or {}).get(city_name, {})
    clat = city_coords.get("lat", "")
    clng = city_coords.get("lng", "")
    petrol_maps_url = f"https://www.google.com/maps/search/petrol+station/@{clat},{clng},14z"
    cng_maps_url    = f"https://www.google.com/maps/search/CNG+station/@{clat},{clng},14z"
    cng_stn_btn = "" if tc is None else (
        f'<a class="stn-btn cng" href="{cng_maps_url}" target="_blank" rel="noopener">'
        f'💨 Find CNG Stations near {city_name}</a>'
    )
    station_html = (
        f'<div class="stn-btns">'
        f'<a class="stn-btn" href="{petrol_maps_url}" target="_blank" rel="noopener">'
        f'⛽ Find Petrol &amp; Diesel Stations near {city_name}</a>'
        f'{cng_stn_btn}</div>'
    )

    # Build city news section
    state_name = CITY_STATES.get(city_name, "")
    city_data_json = json.dumps({
        "name": city_name, "state": state_name,
        "petrol": tp, "diesel": td, "cng": tc,
        "updated": entries[0].get("updated", "") if entries else "",
    }, ensure_ascii=False)
    news_html = ""
    if news:
        def _news_item(a: dict) -> str:
            src  = f'<span class="news-src">{a["source"]}</span>'  if a["source"]   else ""
            time = f'<span class="news-time">{fmt_pub_date(a["published"])}</span>' if a.get("published") else ""
            return (
                f'      <div class="news-item">'
                f'<a class="news-link" href="{a["url"]}" target="_blank" rel="noopener noreferrer">{a["title"]}<i class="ext-icon">↗</i></a>'
                f'<div class="news-meta">{src}{time}</div></div>'
            )
        news_items_html = "\n".join(_news_item(a) for a in news)
        heading = f"Latest Fuel News — {city_name}" + (f" &amp; {state_name}" if state_name else "")
        news_html = f"""
  <div class="news-section">
    <div class="news-head"><span class="news-dot"></span><span class="news-head-text">{heading}</span></div>
{news_items_html}
  </div>"""

    # Cross-links to all other city pages
    other_links = "\n".join(
        f'    <a href="/{s}/" class="clink">{n}</a>'
        for n, s in all_cities.items()
        if s != slug
    )

    schema = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": f"Petrol & Diesel Price in {city_name} Today",
            "url": f"https://www.fuelpricetoday.in/{slug}/",
            "description": (
                f"Today's petrol price in {city_name} is ₹{tp:.2f}/L "
                f"and diesel is ₹{td:.2f}/L as of {today_date_str}. "
                f"See last 10 days price history."
            ),
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Petrol &amp; Diesel Price in {city_name} Today | FuelPriceToday.in</title>
  <meta name="description" content="Today's petrol price in {city_name} is ₹{tp:.2f}/L and diesel is ₹{td:.2f}/L as of {today_date_str}. Track last 10 days of fuel price history." />
  <link rel="canonical" href="https://www.fuelpricetoday.in/{slug}/" />
  <meta property="og:title" content="Petrol &amp; Diesel Price in {city_name} Today" />
  <meta property="og:description" content="Petrol ₹{tp:.2f}/L · Diesel ₹{td:.2f}/L in {city_name} as of {today_date_str}" />
  <meta property="og:url" content="https://www.fuelpricetoday.in/{slug}/" />
  <meta property="og:type" content="website" />
  <script type="application/ld+json">{schema}</script>
  <script id="city-data" type="application/json">{city_data_json}</script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8fafc;color:#111827;line-height:1.5}}
    .hdr{{background:linear-gradient(135deg,#0f766e,#0ea5e9);color:#fff;padding:13px 20px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,0.15)}}
    .hdr-title{{font-size:18px;font-weight:700;color:#fff;text-decoration:none}}
    .hdr-title:hover{{opacity:.9}}
    .brand-t{{color:#5eead4}}
    .brand-i{{color:rgba(255,255,255,0.45);font-weight:500}}
    .hdr-left{{display:flex;flex-direction:column;gap:2px}}
    .hdr-sub{{font-size:12px;color:rgba(255,255,255,0.82);margin:0;font-weight:400}}
    .hdr-nav{{color:#fff;text-decoration:none;font-size:13px;opacity:.85;font-weight:500;white-space:nowrap}}
    .hdr-nav:hover{{opacity:1;text-decoration:underline}}
    .wrap{{max-width:640px;margin:0 auto;padding:24px 16px 60px}}
    h1{{font-size:21px;font-weight:800;color:#0f766e;margin-bottom:4px}}
    .sub{{font-size:12px;color:#9ca3af;margin-bottom:22px}}
    .hero{{display:flex;gap:12px;margin-bottom:28px;flex-wrap:wrap}}
    .card{{flex:1 1 150px;min-width:0;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px 14px;text-align:center}}
    .clbl{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin-bottom:6px}}
    .cval{{font-size:30px;font-weight:800;line-height:1}}
    .cunit{{font-size:12px;color:#9ca3af;margin-top:3px}}
    .cdelta{{font-size:12px;margin-top:6px;min-height:18px}}
    .sec-title{{font-size:15px;font-weight:700;margin-bottom:10px}}
    table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;font-size:13px}}
    thead th{{background:#f0fdf9;color:#0f766e;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;text-align:left;border-bottom:1px solid #d1fae5}}
    .np,.nd{{text-align:right;padding:10px 14px;white-space:nowrap}}
    .dc{{padding:10px 14px}}
    .re{{background:#fff}}
    .ro{{background:#f9fafb}}
    .today-badge{{font-size:10px;background:#d1fae5;color:#065f46;border-radius:4px;padding:1px 6px;margin-left:5px;font-weight:600}}
    .empty{{text-align:center;padding:20px;color:#9ca3af;font-size:13px}}
    .back{{display:inline-flex;align-items:center;gap:6px;margin-top:26px;font-size:13px;color:#0f766e;text-decoration:none;font-weight:600}}
    .back:hover{{text-decoration:underline}}
    .note{{font-size:11px;color:#9ca3af;margin-top:14px}}
    .cities-section{{margin-top:32px;padding-top:20px;border-top:1px solid #e5e7eb}}
    .cities-title{{font-size:13px;font-weight:700;color:#374151;margin-bottom:10px}}
    .cities-grid{{display:flex;flex-wrap:wrap;gap:8px}}
    .clink{{font-size:12px;color:#0f766e;text-decoration:none;background:#f0fdf9;border:1px solid #d1fae5;border-radius:6px;padding:4px 10px;white-space:nowrap}}
    .clink:hover{{background:#d1fae5;text-decoration:none}}
    .news-section{{margin-top:32px;padding-top:20px;border-top:1px solid #e5e7eb}}
    .news-head{{display:flex;align-items:center;gap:7px;margin-bottom:12px}}
    .news-dot{{width:8px;height:8px;border-radius:50%;background:#ef4444;animation:pulse 1.8s ease-in-out infinite;flex-shrink:0}}
    @keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.4;transform:scale(.75)}}}}
    .news-head-text{{font-size:14px;font-weight:700;color:#111827;text-transform:uppercase;letter-spacing:.5px}}
    .news-item{{padding:10px 0;border-bottom:1px solid #f3f4f6}}
    .news-item:last-child{{border-bottom:none}}
    .news-link{{font-size:13px;color:#1a56db;text-decoration:none;line-height:1.45;display:block;margin-bottom:3px}}
    .ext-icon{{font-size:11px;margin-left:4px;opacity:.7;font-style:normal}}
    .news-link:hover{{text-decoration:underline}}
    .news-meta{{font-size:11px;color:#9ca3af;display:flex;gap:6px;align-items:center}}
    .news-src{{color:#374151;font-weight:500}}
    .news-time::before{{content:"·";margin-right:4px;color:#d1d5db}}
    .share-btn{{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:24px;width:100%;padding:12px 16px;background:linear-gradient(135deg,#0f766e,#0ea5e9);color:#fff;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit}}
    .share-btn:hover{{opacity:.9}}.share-btn:active{{opacity:.75}}
    .stn-btns{{display:flex;flex-direction:column;gap:8px;margin-bottom:16px}}
    .stn-btn{{display:flex;align-items:center;justify-content:center;gap:6px;padding:10px 16px;background:#f1f5f9;color:#0f172a;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;font-family:inherit}}
    .stn-btn:hover{{background:#e2e8f0}}
    .stn-btn.cng{{background:#fef3c7;border-color:#fcd34d;color:#78350f}}
    .stn-btn.cng:hover{{background:#fde68a}}
  </style>
</head>
<body>
<header class="hdr">
  <div class="hdr-left">
    <a href="/" class="hdr-title">⛽ FuelPrice<span class="brand-t">Today</span><span class="brand-i">.in</span></a>
    <p class="hdr-sub">Live petrol &amp; diesel prices in {city_name}. Updated hourly from official pump rates.</p>
  </div>
  <a href="/" class="hdr-nav">← Live Map</a>
</header>
<div class="wrap">
  <h1>Petrol &amp; Diesel Price in {city_name} Today</h1>
  <p class="sub">Updated {today_date_str}</p>

  <div class="hero">
    <div class="card">
      <div class="clbl">⛽ Petrol</div>
      <div class="cval" style="color:#0f766e">₹{tp:.2f}</div>
      <div class="cunit">per litre</div>
      <div class="cdelta">{petrol_delta}</div>
    </div>
    <div class="card">
      <div class="clbl">🛢 Diesel</div>
      <div class="cval" style="color:#1e3a8a">₹{td:.2f}</div>
      <div class="cunit">per litre</div>
      <div class="cdelta">{diesel_delta}</div>
    </div>{"" if tc is None else f"""
    <div class="card">
      <div class="clbl">🟡 CNG</div>
      <div class="cval" style="color:#92400e">₹{tc:.2f}</div>
      <div class="cunit">per kg</div>
    </div>"""}
  </div>
  {station_html}
  <button id="city-share-btn" class="share-btn">📤 Share Prices</button>

  <p class="sec-title">Last 10 Days — {city_name} Fuel Price History</p>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th style="text-align:right">Petrol (₹/L)</th>
        <th style="text-align:right">Diesel (₹/L)</th>
        <th style="text-align:right">CNG (₹/Kg)</th>
      </tr>
    </thead>
    <tbody>
{rows_html}    </tbody>
  </table>

{news_html}
  <a class="back" href="/">🗺 View Live Price Map</a>
  <p class="note">Prices are updated automatically every hour.</p>

  <div class="cities-section">
    <p class="cities-title">Fuel Prices in Other Cities</p>
    <div class="cities-grid">
{other_links}
    </div>
  </div>
</div>
<script src="../share-card.js?v=1"></script>
<script>
document.getElementById('city-share-btn').addEventListener('click', function() {{
  var d = JSON.parse(document.getElementById('city-data').textContent);
  shareFuelPriceCard(d, d.updated);
}});
</script>
</body>
</html>
"""


def main() -> int:
    if not os.path.exists(HISTORY_JSON):
        print("history.json not found — run scraper first.", file=sys.stderr)
        return 1

    with open(HISTORY_JSON, encoding="utf-8") as f:
        history: dict[str, list] = json.load(f)

    scrape_ts = get_last_scrape_timestamp()
    if scrape_ts:
        print(f"  Using scrape timestamp: {scrape_ts}", file=sys.stderr)

    # Load city coordinates from data.json for station finder links
    coords: dict = {}
    if os.path.exists(DATA_JSON):
        with open(DATA_JSON, encoding="utf-8") as f:
            _d = json.load(f)
        coords = {c["name"]: {"lat": c["lat"], "lng": c["lng"]} for c in _d.get("cities", []) if "lat" in c}

    count = 0
    for city_name, slug in METRO_CITY_SLUGS.items():
        entries = history.get(city_name, [])
        if not entries:
            print(f"  SKIP {city_name} — no data in history.json", file=sys.stderr)
            continue

        state_name = CITY_STATES.get(city_name, "")
        city_news = fetch_city_news(city_name, state_name)
        page_html = generate_page(city_name, slug, entries, METRO_CITY_SLUGS, scrape_ts, city_news, coords)

        city_dir = os.path.join(PROJECT_ROOT, slug)
        os.makedirs(city_dir, exist_ok=True)

        out_path = os.path.join(city_dir, "index.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)

        print(f"  {slug}/index.html", file=sys.stderr)
        count += 1

    print(f"\nGenerated {count}/{len(METRO_CITY_SLUGS)} city pages.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
