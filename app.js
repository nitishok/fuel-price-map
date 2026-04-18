/* global L, FUEL_DATA */

// ---------- data loading ----------
//
// Prefer the scraper-maintained data.json (fresh prices + lastUpdated).
// Fall back to the static data.js that ships with the repo.
let FUEL_CITIES = Array.isArray(window.FUEL_DATA) ? window.FUEL_DATA.slice() : [];
let LAST_UPDATED = null;
let DATA_SOURCE = "seed:data.js";

async function loadFreshData() {
  try {
    const resp = await fetch("./data.json", { cache: "no-store" });
    if (!resp.ok) return;
    const json = await resp.json();
    if (!json || !Array.isArray(json.cities)) return;
    FUEL_CITIES = json.cities;
    LAST_UPDATED = json.lastUpdated || null;
    DATA_SOURCE = json.source || "data.json";
    rebuildMarkers();
    updateStatusLine();
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

// ---------- markers ----------

const markerGroup = L.layerGroup().addTo(map);
const markersByName = new Map();

function popupHtml(c) {
  return `
    <div class="popup-inner">
      <div class="name">${c.name}</div>
      <div class="region">${c.state}</div>
      <div class="row"><span class="k">Petrol</span><span class="v">₹ ${fmtPrice(
        c.petrol
      )}</span></div>
      <div class="row"><span class="k">Diesel</span><span class="v">₹ ${fmtPrice(
        c.diesel
      )}</span></div>
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

updateStatusLine();
loadFreshData();
