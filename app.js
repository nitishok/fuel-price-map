/* global L, FUEL_DATA */

// ---------- data loading ----------
//
// Prefer the scraper-maintained data.json (fresh prices + lastUpdated).
// Fall back to the static data.js that ships with the repo.
let FUEL_CITIES = Array.isArray(window.FUEL_DATA) ? window.FUEL_DATA.slice() : [];
let LAST_UPDATED = null;
let DATA_SOURCE = "seed:data.js";
// city name (lowercase) → { petrol, diesel } from previous day
let YESTERDAY_MAP = new Map();

async function loadFreshData() {
  try {
    const [dataResp, yestResp] = await Promise.all([
      fetch("./data.json",           { cache: "no-store" }),
      fetch("./data-yesterday.json", { cache: "no-store" }),
    ]);

    if (dataResp.ok) {
      const json = await dataResp.json();
      if (json && Array.isArray(json.cities)) {
        FUEL_CITIES  = json.cities;
        LAST_UPDATED = json.lastUpdated || null;
        DATA_SOURCE  = json.source || "data.json";
      }
    }

    if (yestResp.ok) {
      const yest = await yestResp.json();
      if (yest && Array.isArray(yest.cities)) {
        YESTERDAY_MAP.clear();
        for (const c of yest.cities) {
          YESTERDAY_MAP.set(c.name.toLowerCase(), { petrol: c.petrol, diesel: c.diesel });
        }
      }
    }

    rebuildMarkers();
    updateStatusLine();
    updateQuickStats();
    updateBelowMap();
  } catch (err) {
    // data.json unavailable (e.g. opened via file://) — silently fall back.
    console.warn("data.json unavailable, using bundled data.js", err);
  }
}

// Bounding box approximating mainland India + island UTs.
const INDIA_BOUNDS = L.latLngBounds(
  L.latLng(6.0, 67.0),   // SW
  L.latLng(37.5, 98.5)   // NE
);

const map = L.map("map", {
  center: [22.9734, 78.6569],
  zoom: 5,
  minZoom: 4,
  maxZoom: 18,
  maxBounds: INDIA_BOUNDS.pad(0.2),
  maxBoundsViscosity: 0.8,
  worldCopyJump: false,
});

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
}).addTo(map);

// Remove "Leaflet" branding — keep only the required OSM attribution.
map.attributionControl.setPrefix("");

// ---------- helpers ----------

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function findNearest(lat, lng) {
  let best = null;
  let bestDist = Infinity;
  for (const c of FUEL_CITIES) {
    const d = haversineKm(lat, lng, c.lat, c.lng);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return { city: best, distanceKm: bestDist };
}

function fmtPrice(n) {
  return n.toFixed(2);
}

// Returns an HTML badge showing price change vs yesterday.
// Price UP   → red   ▲  (costs more — bad for driver)
// Price DOWN → green ▼  (costs less — good for driver)
function deltaHtml(current, yesterday) {
  if (yesterday == null) return "";
  const diff = current - yesterday;
  if (Math.abs(diff) < 0.005) return "";
  const sign = diff > 0 ? "▲" : "▼";
  const cls  = diff > 0 ? "delta-up" : "delta-dn";
  return `<span class="${cls}">${sign}${Math.abs(diff).toFixed(2)}</span>`;
}

// For table cells: wraps price + a fixed-width delta slot so columns stay
// aligned regardless of whether a delta badge is shown or not.
function priceCellHtml(price, yesterdayPrice) {
  if (!YESTERDAY_MAP.size) return `₹${price.toFixed(2)}`;
  const badge = deltaHtml(price, yesterdayPrice ?? null) || `<span class="delta-ph"></span>`;
  return `<span class="price-cell"><span class="pv">₹${price.toFixed(2)}</span>${badge}</span>`;
}

// ---------- markers ----------

const markerGroup = L.layerGroup().addTo(map);
const markersByName = new Map();

function popupHtml(c) {
  const yest = YESTERDAY_MAP.get(c.name.toLowerCase());
  const pd = yest ? deltaHtml(c.petrol, yest.petrol) : "";
  const dd = yest ? deltaHtml(c.diesel, yest.diesel) : "";
  return `
    <div class="popup-inner">
      <div class="name">${c.name}</div>
      <div class="region">${c.state}</div>
      <div class="row"><span class="k">Petrol</span><span class="v">₹ ${fmtPrice(c.petrol)} ${pd}</span></div>
      <div class="row"><span class="k">Diesel</span><span class="v">₹ ${fmtPrice(c.diesel)} ${dd}</span></div>
    </div>
  `;
}

const fuelIcon = L.divIcon({
  className: "fuel-marker",
  html:
    '<div style="background:#0f766e;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);font-size:12px;font-weight:700;">₹</div>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

function rebuildMarkers() {
  markerGroup.clearLayers();
  markersByName.clear();
  FUEL_CITIES.forEach((c) => {
    const m = L.marker([c.lat, c.lng], { icon: fuelIcon, title: c.name })
      .bindPopup(popupHtml(c))
      .addTo(markerGroup);
    m.on("click", () => showPriceCard(c, 0));
    markersByName.set(c.name.toLowerCase(), { city: c, marker: m });
  });
}

rebuildMarkers();

// ---------- info panel ----------

const pcEl = document.getElementById("price-card");
const pcName = document.getElementById("pc-name");
const pcRegion = document.getElementById("pc-region");
const pcPetrol = document.getElementById("pc-petrol");
const pcDiesel = document.getElementById("pc-diesel");
const pcDistance = document.getElementById("pc-distance");
const hint = document.querySelector(".hint");

function showPriceCard(city, distanceKm) {
  pcName.textContent = city.name;
  pcRegion.textContent = city.state;
  pcPetrol.textContent = fmtPrice(city.petrol);
  pcDiesel.textContent = fmtPrice(city.diesel);
  if (distanceKm > 0.5) {
    pcDistance.textContent = `Nearest reference point · ${distanceKm.toFixed(
      1
    )} km away from clicked location`;
  } else {
    pcDistance.textContent = "";
  }
  pcEl.classList.remove("hidden");
  hint.classList.add("hidden");
}

// ---------- click-on-map handler ----------

let clickMarker = null;

map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  if (!INDIA_BOUNDS.contains(e.latlng)) {
    return;
  }
  const { city, distanceKm } = findNearest(lat, lng);
  if (!city) return;

  if (clickMarker) {
    map.removeLayer(clickMarker);
  }
  clickMarker = L.circleMarker([lat, lng], {
    radius: 6,
    color: "#ef4444",
    fillColor: "#ef4444",
    fillOpacity: 0.9,
    weight: 2,
  }).addTo(map);

  showPriceCard(city, distanceKm);

  // Also open the nearest city's popup.
  const entry = markersByName.get(city.name.toLowerCase());
  if (entry) {
    entry.marker.openPopup();
  }
});

// ---------- search ----------

const searchInput = document.getElementById("search");
const resultsEl = document.getElementById("search-results");

function renderResults(items) {
  if (items.length === 0) {
    resultsEl.classList.add("hidden");
    resultsEl.innerHTML = "";
    return;
  }
  resultsEl.innerHTML = items
    .slice(0, 12)
    .map(
      (c) =>
        `<li data-name="${c.name}"><span>${c.name}</span><span class="region">${c.state}</span></li>`
    )
    .join("");
  resultsEl.classList.remove("hidden");
}

searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim().toLowerCase();
  if (!q) {
    renderResults([]);
    return;
  }
  const matches = FUEL_CITIES.filter(
    (c) =>
      c.name.toLowerCase().includes(q) || c.state.toLowerCase().includes(q)
  );
  renderResults(matches);
});

resultsEl.addEventListener("click", (e) => {
  const li = e.target.closest("li");
  if (!li) return;
  const name = li.getAttribute("data-name");
  const entry = markersByName.get(name.toLowerCase());
  if (!entry) return;
  map.setView([entry.city.lat, entry.city.lng], 11, { animate: true });
  entry.marker.openPopup();
  showPriceCard(entry.city, 0);
  searchInput.value = "";
  renderResults([]);
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-wrap")) {
    renderResults([]);
  }
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const first = resultsEl.querySelector("li");
    if (first) first.click();
  } else if (e.key === "Escape") {
    renderResults([]);
    searchInput.blur();
  }
});

// ---------- status line (last updated) ----------

const statusEl = document.getElementById("data-status");

function updateStatusLine() {
  if (!statusEl) return;
  if (!LAST_UPDATED) {
    statusEl.textContent =
      `Showing seed sample prices (${FUEL_CITIES.length} cities). Run the scraper to fetch live values.`;
    statusEl.classList.add("is-stale");
    return;
  }
  const ts = new Date(LAST_UPDATED);
  const pretty = ts.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  statusEl.textContent =
    `Prices for ${FUEL_CITIES.length} cities • last updated ${pretty}`;
  statusEl.classList.remove("is-stale");
}

// ---------- quick stats ----------

function updateQuickStats() {
  if (!FUEL_CITIES.length) return;

  const avgPetrol = FUEL_CITIES.reduce((s, c) => s + c.petrol, 0) / FUEL_CITIES.length;
  const avgDiesel = FUEL_CITIES.reduce((s, c) => s + c.diesel, 0) / FUEL_CITIES.length;

  const byPetrol  = [...FUEL_CITIES].sort((a, b) => a.petrol - b.petrol);
  const byDiesel  = [...FUEL_CITIES].sort((a, b) => a.diesel - b.diesel);

  const el = (id) => document.getElementById(id);

  // Average prices — show delta vs yesterday's average if data available
  if (YESTERDAY_MAP.size) {
    const yvals = [...YESTERDAY_MAP.values()];
    const yAvgPetrol = yvals.reduce((s, c) => s + c.petrol, 0) / yvals.length;
    const yAvgDiesel = yvals.reduce((s, c) => s + c.diesel, 0) / yvals.length;
    el("qs-avg-petrol").innerHTML = `₹${avgPetrol.toFixed(2)}/L ${deltaHtml(avgPetrol, yAvgPetrol)}`;
    el("qs-avg-diesel").innerHTML = `₹${avgDiesel.toFixed(2)}/L ${deltaHtml(avgDiesel, yAvgDiesel)}`;
  } else {
    el("qs-avg-petrol").textContent = `₹${avgPetrol.toFixed(2)}/L`;
    el("qs-avg-diesel").textContent = `₹${avgDiesel.toFixed(2)}/L`;
  }

  const fmt = (price, city) => `₹${price.toFixed(2)}/L (${city})`;
  el("qs-cheapest-petrol").textContent  = fmt(byPetrol[0].petrol,  byPetrol[0].name);
  el("qs-costliest-petrol").textContent = fmt(byPetrol[byPetrol.length - 1].petrol, byPetrol[byPetrol.length - 1].name);
  el("qs-cheapest-diesel").textContent  = fmt(byDiesel[0].diesel,  byDiesel[0].name);
  el("qs-costliest-diesel").textContent = fmt(byDiesel[byDiesel.length - 1].diesel, byDiesel[byDiesel.length - 1].name);
}

// ---------- metro cities grid ----------

const CITY_SLUGS = {
  "Mumbai": "mumbai", "New Delhi": "delhi", "Bengaluru": "bangalore",
  "Hyderabad": "hyderabad", "Ahmedabad": "ahmedabad", "Chennai": "chennai",
  "Kolkata": "kolkata", "Surat": "surat", "Pune": "pune", "Jaipur": "jaipur",
  "Lucknow": "lucknow", "Kanpur": "kanpur", "Nagpur": "nagpur",
  "Indore": "indore", "Bhopal": "bhopal", "Visakhapatnam": "visakhapatnam",
  "Patna": "patna", "Vadodara": "vadodara", "Kochi": "kochi",
  "Coimbatore": "coimbatore", "Guwahati": "guwahati", "Ranchi": "ranchi",
  "Chandigarh": "chandigarh", "Thiruvananthapuram": "thiruvananthapuram",
  "Varanasi": "varanasi",
};

const METRO_CITIES = [
  "Mumbai", "New Delhi", "Bengaluru", "Hyderabad", "Ahmedabad",
  "Chennai", "Kolkata", "Surat", "Pune", "Jaipur",
  "Lucknow", "Kanpur", "Nagpur", "Indore", "Bhopal",
  "Visakhapatnam", "Patna", "Vadodara", "Kochi", "Coimbatore",
  "Guwahati", "Ranchi", "Chandigarh", "Thiruvananthapuram", "Varanasi"
];

function updateMetroCities() {
  const tbody = document.getElementById("metro-table-body");
  if (!tbody || !FUEL_CITIES.length) return;

  tbody.innerHTML = METRO_CITIES.map((name, i) => {
    const city = FUEL_CITIES.find(c => c.name.toLowerCase() === name.toLowerCase());
    if (!city) {
      return `<tr class="${i % 2 === 0 ? "tr-even" : "tr-odd"}">
        <td class="td-state">${name}</td>
        <td class="td-city" colspan="2">data unavailable</td>
      </tr>`;
    }
    const yest = YESTERDAY_MAP.get(city.name.toLowerCase());
    const slug = CITY_SLUGS[city.name];
    const cityLabel = slug
      ? `<a href="/${slug}" class="city-page-link" title="See 10-day history for ${city.name}">${city.name}</a>`
      : city.name;
    return `<tr class="${i % 2 === 0 ? "tr-even" : "tr-odd"} metro-row" data-name="${city.name}" style="cursor:pointer">
      <td class="td-state">${cityLabel}</td>
      <td class="td-petrol">${priceCellHtml(city.petrol, yest?.petrol)}</td>
      <td class="td-diesel">${priceCellHtml(city.diesel, yest?.diesel)}</td>
    </tr>`;
  }).join("");

  // Click row → pan map to city
  tbody.querySelectorAll(".metro-row").forEach(row => {
    row.addEventListener("click", () => {
      const name = row.getAttribute("data-name");
      const entry = markersByName.get(name.toLowerCase());
      if (!entry) return;
      map.setView([entry.city.lat, entry.city.lng], 11, { animate: true });
      entry.marker.openPopup();
      showPriceCard(entry.city, 0);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

// ---------- below-map content: state table ----------

function updateBelowMap() {
  if (!FUEL_CITIES.length) return;

  // ── Metro cities ──
  updateMetroCities();

  // ── State table ──
  const stateMap = {};
  for (const c of FUEL_CITIES) {
    if (!stateMap[c.state]) stateMap[c.state] = { petrol: [], diesel: [], cities: [], count: 0 };
    stateMap[c.state].petrol.push(c.petrol);
    stateMap[c.state].diesel.push(c.diesel);
    stateMap[c.state].cities.push(c);
    stateMap[c.state].count++;
  }
  const avg = arr => arr.reduce((s, v) => s + v, 0) / arr.length;

  // Build yesterday's average per state (for delta badges)
  const yestStateAvg = {};
  if (YESTERDAY_MAP.size) {
    const yestState = {};
    for (const c of FUEL_CITIES) {
      const y = YESTERDAY_MAP.get(c.name.toLowerCase());
      if (!y) continue;
      if (!yestState[c.state]) yestState[c.state] = { petrol: [], diesel: [] };
      yestState[c.state].petrol.push(y.petrol);
      yestState[c.state].diesel.push(y.diesel);
    }
    for (const [state, d] of Object.entries(yestState)) {
      yestStateAvg[state] = { petrol: avg(d.petrol), diesel: avg(d.diesel) };
    }
  }

  const states = Object.entries(stateMap)
    .map(([name, d]) => {
      const lowestPetrol = d.cities.reduce((a, b) => a.petrol < b.petrol ? a : b);
      const lowestDiesel = d.cities.reduce((a, b) => a.diesel < b.diesel ? a : b);
      return {
        name,
        avgPetrol: avg(d.petrol),
        avgDiesel: avg(d.diesel),
        count: d.count,
        lowestPetrolCity: `₹${lowestPetrol.petrol.toFixed(2)} (${lowestPetrol.name})`,
        lowestDieselCity: `₹${lowestDiesel.diesel.toFixed(2)} (${lowestDiesel.name})`,
      };
    })
    .sort((a, b) => a.avgPetrol - b.avgPetrol);

  const tbody = document.getElementById("state-table-body");
  if (tbody) {
    tbody.innerHTML = states.map((s, i) => {
      const y = yestStateAvg[s.name];
      return `
      <tr class="${i % 2 === 0 ? "tr-even" : "tr-odd"}">
        <td class="td-state">${s.name}</td>
        <td class="td-petrol">${priceCellHtml(s.avgPetrol, y?.petrol)}</td>
        <td class="td-diesel">${priceCellHtml(s.avgDiesel, y?.diesel)}</td>
        <td class="td-city">${s.lowestPetrolCity}</td>
        <td class="td-city td-city--diesel">${s.lowestDieselCity}</td>
        <td class="td-count">${s.count}</td>
      </tr>`;
    }).join("");
  }
}

updateStatusLine();
updateQuickStats();
updateBelowMap();
loadFreshData();
