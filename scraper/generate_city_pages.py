#!/usr/bin/env python3
"""Generate individual city HTML pages from history.json.

Run after scrape.py has updated history.json:
    python3 scraper/generate_city_pages.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
HISTORY_JSON = os.path.join(PROJECT_ROOT, "history.json")

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


def generate_page(city_name: str, slug: str, entries: list[dict], all_cities: dict[str, str]) -> str:
    today = entries[0] if entries else None
    prev = entries[1] if len(entries) > 1 else None

    tp = today["petrol"] if today else 0.0
    td = today["diesel"] if today else 0.0
    pp = prev["petrol"] if prev else None
    pd = prev["diesel"] if prev else None

    today_date_str = format_updated(
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
        rows_html += (
            f'<tr class="{row_cls}">'
            f'<td class="dc">{format_date(entry["date"])}{today_badge}</td>'
            f'<td class="np">₹{entry["petrol"]:.2f}{p_d}</td>'
            f'<td class="nd">₹{entry["diesel"]:.2f}{d_d}</td>'
            f"</tr>\n"
        )

    if not rows_html:
        rows_html = '<tr><td colspan="3" class="empty">No history yet — check back tomorrow.</td></tr>'

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
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8fafc;color:#111827;line-height:1.5}}
    .hdr{{background:#0f766e;color:#fff;padding:13px 20px;display:flex;align-items:center;justify-content:space-between}}
    .hdr-title{{font-size:16px;font-weight:700;display:flex;align-items:center;gap:6px}}
    .hdr a{{color:#fff;text-decoration:none;font-size:13px;opacity:.85;font-weight:500}}
    .hdr a:hover{{opacity:1;text-decoration:underline}}
    .wrap{{max-width:640px;margin:0 auto;padding:24px 16px 60px}}
    h1{{font-size:21px;font-weight:800;color:#0f766e;margin-bottom:4px}}
    .sub{{font-size:12px;color:#9ca3af;margin-bottom:22px}}
    .hero{{display:flex;gap:12px;margin-bottom:28px}}
    .card{{flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px 14px;text-align:center}}
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
  </style>
</head>
<body>
<header class="hdr">
  <span class="hdr-title">⛽ FuelPriceToday.in</span>
  <a href="/">← Live Map</a>
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
    </div>
  </div>

  <p class="sec-title">Last 10 Days — {city_name} Fuel Price History</p>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th style="text-align:right">Petrol (₹/L)</th>
        <th style="text-align:right">Diesel (₹/L)</th>
      </tr>
    </thead>
    <tbody>
{rows_html}    </tbody>
  </table>

  <a class="back" href="/">🗺 View Live Price Map</a>
  <p class="note">Prices are updated automatically every hour.</p>

  <div class="cities-section">
    <p class="cities-title">Fuel Prices in Other Cities</p>
    <div class="cities-grid">
{other_links}
    </div>
  </div>
</div>
</body>
</html>
"""


def main() -> int:
    if not os.path.exists(HISTORY_JSON):
        print("history.json not found — run scraper first.", file=sys.stderr)
        return 1

    with open(HISTORY_JSON, encoding="utf-8") as f:
        history: dict[str, list] = json.load(f)

    count = 0
    for city_name, slug in METRO_CITY_SLUGS.items():
        entries = history.get(city_name, [])
        if not entries:
            print(f"  SKIP {city_name} — no data in history.json", file=sys.stderr)
            continue

        page_html = generate_page(city_name, slug, entries, METRO_CITY_SLUGS)

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
