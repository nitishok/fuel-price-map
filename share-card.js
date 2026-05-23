// share-card.js — standalone fuel price card generator
// Used by both index.html (main map) and individual city pages.
// Globals exposed: drawFuelPriceCard(city, updatedISO), shareFuelPriceCard(city, updatedISO)

(function () {
  "use strict";

  function _fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
  }

  function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  function drawFuelPriceCard(city, updatedISO) {
    var W = 1080, H = 1920;
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");

    // ── Background ──────────────────────────────────────────────────────────
    var bg = ctx.createLinearGradient(0, 0, W, H);
    bg.addColorStop(0, "#0d1117");
    bg.addColorStop(1, "#0f172a");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    // ── Top accent bar ───────────────────────────────────────────────────────
    var bar = ctx.createLinearGradient(0, 0, W, 0);
    bar.addColorStop(0, "#0f766e");
    bar.addColorStop(1, "#0ea5e9");
    ctx.fillStyle = bar;
    ctx.fillRect(0, 0, W, 14);

    // ── Fuel icon ────────────────────────────────────────────────────────────
    ctx.font = "80px serif";
    ctx.textAlign = "center";
    ctx.fillText("\u26FD", W / 2, 195);

    // ── "FUEL PRICES" header ─────────────────────────────────────────────────
    ctx.fillStyle = "#0ea5e9";
    ctx.font = "600 46px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.letterSpacing = "4px";
    ctx.fillText("FUEL PRICES", W / 2, 310);
    ctx.letterSpacing = "0px";

    // ── City name ────────────────────────────────────────────────────────────
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 96px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.fillText(city.name, W / 2, 450);

    // ── State ────────────────────────────────────────────────────────────────
    ctx.fillStyle = "#94a3b8";
    ctx.font = "400 44px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.fillText(city.state || "", W / 2, 532);

    // ── Date ─────────────────────────────────────────────────────────────────
    var dateStr = _fmtDate(updatedISO);
    ctx.fillStyle = "#64748b";
    ctx.font = "400 36px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.fillText(dateStr, W / 2, 606);

    // ── Divider ──────────────────────────────────────────────────────────────
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(80, 660);
    ctx.lineTo(W - 80, 660);
    ctx.stroke();

    // ── Price rows ───────────────────────────────────────────────────────────
    var rows = [
      { label: "Petrol", value: city.petrol, unit: "/L", color: "#10b981" },
      { label: "Diesel", value: city.diesel, unit: "/L", color: "#3b82f6" },
    ];
    if (city.cng != null) {
      rows.push({ label: "CNG", value: city.cng, unit: "/Kg", color: "#f59e0b" });
    }

    var rowH = rows.length === 3 ? 240 : 290;
    var startY = 700;
    var PAD = 80; // left/right margin

    rows.forEach(function (row, i) {
      var y = startY + i * (rowH + 20);

      // Pill background
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      _roundRect(ctx, PAD, y, W - PAD * 2, rowH, 20);
      ctx.fill();

      // Colored left accent bar
      ctx.fillStyle = row.color;
      _roundRect(ctx, PAD, y, 10, rowH, 4);
      ctx.fill();

      // Label
      ctx.fillStyle = "#94a3b8";
      ctx.font = "500 48px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(row.label, PAD + 36, y + rowH / 2 - 14);

      // Price
      var priceStr = "\u20B9" + row.value.toFixed(2);
      ctx.fillStyle = "#ffffff";
      ctx.font = "700 88px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(priceStr, W - PAD - 10, y + rowH / 2 + 26);

      // Unit (below price, right-aligned)
      ctx.fillStyle = "#64748b";
      ctx.font = "400 30px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      ctx.fillText(row.unit, W - PAD - 10, y + rowH / 2 + 66);
    });

    // ── Bottom divider ───────────────────────────────────────────────────────
    var divY = H - 260;
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(80, divY);
    ctx.lineTo(W - 80, divY);
    ctx.stroke();

    // ── Branding ─────────────────────────────────────────────────────────────
    ctx.fillStyle = "#475569";
    ctx.font = "400 42px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("www.fuelpricetoday.in", W / 2, H - 160);

    ctx.fillStyle = "#334155";
    ctx.font = "400 30px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    ctx.fillText("As of " + dateStr, W / 2, H - 100);

    return canvas;
  }

  function _downloadCard(canvas, slug) {
    var a = document.createElement("a");
    a.download = slug + "-fuel-prices.png";
    a.href = canvas.toDataURL("image/png");
    a.click();
  }

  function shareFuelPriceCard(city, updatedISO) {
    var canvas = drawFuelPriceCard(city, updatedISO);
    var slug = city.name.toLowerCase().replace(/\s+/g, "-");

    canvas.toBlob(function (blob) {
      var file = new File([blob], slug + "-fuel-prices.png", { type: "image/png" });

      if (
        navigator.share &&
        navigator.canShare &&
        navigator.canShare({ files: [file] })
      ) {
        var cngText = city.cng != null
          ? " \u00B7 CNG \u20B9" + city.cng.toFixed(2) + "/Kg"
          : "";
        navigator
          .share({
            title: "Fuel Prices in " + city.name,
            text:
              "Petrol \u20B9" + city.petrol.toFixed(2) +
              "/L \u00B7 Diesel \u20B9" + city.diesel.toFixed(2) +
              "/L" + cngText + " \u2014 " + city.name,
            files: [file],
          })
          .catch(function (e) {
            if (e.name !== "AbortError") _downloadCard(canvas, slug);
          });
      } else {
        _downloadCard(canvas, slug);
      }
    }, "image/png");
  }

  // Expose globals
  window.drawFuelPriceCard = drawFuelPriceCard;
  window.shareFuelPriceCard = shareFuelPriceCard;
})();
