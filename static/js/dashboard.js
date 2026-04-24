/* ============================================================
   AgriSetu Dashboard — Frontend Logic
   Fixes applied vs previous version:
   1. state exposed on window so inline HTML scripts can read it
   2. Separate /api/status polling (every 5 s) for connection banner
   3. Sensor cards show "N/A" for fields the Arduino doesn't have
   4. Predict / Report buttons disabled when Arduino is offline
   5. Quick Stats and Sensor Summary update from the same state object
   ============================================================ */

// ── State (on window so templates can access it) ──────────────────────────────
window.state = {
  sensorData:    null,
  prediction:    null,
  connected:     false,
  historyMoist:  [],
  historyTemp:   [],
  historyLabels: [],
  chart:         null,
  maxHistory:    20,
};

// ── DOM helpers ───────────────────────────────────────────────────────────────
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = $("#clock");
  if (el) el.textContent = new Date().toLocaleTimeString("en-IN", { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Connection status polling ─────────────────────────────────────────────────
async function fetchConnectionStatus() {
  try {
    const res  = await fetch("/api/status");
    const json = await res.json();
    updateConnectionBanner(json);
    window.state.connected = json.connected;
    updateButtonStates();
  } catch {
    updateConnectionBanner({ connected: false, error: "Cannot reach server" });
  }
}

function updateConnectionBanner(status) {
  const banner   = $("#connection-banner");
  const dot      = $("#banner-dot");
  const text     = $("#banner-text");
  if (!banner) return;

  if (status.connected) {
    banner.className = "connection-banner connected";
    dot.className    = "banner-dot";
    const age = status.age_seconds < 70
      ? `${Math.round(status.age_seconds)}s ago`
      : "cached";
    text.textContent = `Arduino online — last data ${age}`;
  } else {
    banner.className = "connection-banner offline";
    dot.className    = "banner-dot offline";
    let msg = "Arduino offline";
    if (!status.token_configured) msg += " — THINGESP_TOKEN not set";
    else if (status.error)        msg += ` — ${status.error}`;
    text.textContent = msg;
  }
}

function updateButtonStates() {
  const btnPredict = $("#btn-predict");
  const btnReport  = $("#btn-report");
  if (!btnPredict) return;

  if (window.state.connected) {
    btnPredict.disabled = false;
    btnPredict.title    = "";
    btnReport.disabled  = false;
    btnReport.title     = "";
  } else {
    btnPredict.disabled = true;
    btnPredict.title    = "Arduino must be online to predict";
    btnReport.disabled  = true;
    btnReport.title     = "Arduino must be online to generate report";
  }
}

// ── Sensor data polling ───────────────────────────────────────────────────────
async function fetchSensorData() {
  try {
    const res  = await fetch("/api/sensor-data");

    if (res.status === 503) {
      // Arduino offline
      const json = await res.json();
      window.state.sensorData = null;
      window.state.connected  = false;
      renderSensorCardsOffline();
      updateButtonStates();
      updateSensorSummary();
      updateQuickStats();
      return;
    }

    const json = await res.json();
    if (!json.success) throw new Error(json.error);

    window.state.sensorData = json.data;
    window.state.connected  = true;
    renderSensorCards(json.data);
    pushToHistory(json.data);
    updateChart();
    updateSensorSummary();
    updateQuickStats();
    updateButtonStates();

  } catch (err) {
    console.warn("Sensor fetch error:", err);
  }
}

// ── Render sensor cards ───────────────────────────────────────────────────────
function renderSensorCards(d) {
  // Real sensors on Arduino
  setCard("sm",  d.soil_moisture,    100, d.soil_moisture < 30 ? "coral" : "");
  setCard("st",  d.soil_temperature,  60, "");
  setCard("wl",  d.water_level,      100, d.water_level < 25 ? "coral" : "sky");

  // Sensors NOT on this Arduino — show N/A
  setCardNA("at");
  setCardNA("hum");
  setCardNA("rain");
  setCardNA("lux");
  setCardNA("ph");
}

function renderSensorCardsOffline() {
  ["sm","st","wl","at","hum","rain","lux","ph"].forEach(id => setCardOffline(id));
}

function setCard(id, value, max, colorClass) {
  const card  = $(`#card-${id}`);
  const valEl = $(`#val-${id}`);
  const bar   = $(`#bar-${id}`);
  if (!valEl) return;

  valEl.textContent = Number.isInteger(value) ? value : value.toFixed(1);
  card?.classList.remove("amber", "sky", "coral", "offline-card");
  if (colorClass) card?.classList.add(colorClass);
  if (bar) bar.style.width = `${Math.min(100, (value / max) * 100)}%`;
}

function setCardNA(id) {
  const valEl = $(`#val-${id}`);
  const bar   = $(`#bar-${id}`);
  if (valEl) {
    valEl.textContent = "N/A";
    valEl.style.color = "var(--text-dim)";
    valEl.style.fontSize = "16px";
  }
  if (bar) bar.style.width = "0%";
}

function setCardOffline(id) {
  const valEl = $(`#val-${id}`);
  const bar   = $(`#bar-${id}`);
  if (valEl) {
    valEl.textContent  = "—";
    valEl.style.color  = "var(--text-dim)";
    valEl.style.fontSize = "26px";
  }
  if (bar) bar.style.width = "0%";
}

// ── Sensor summary row (in form card) ────────────────────────────────────────
function updateSensorSummary() {
  const d = window.state.sensorData;
  const set = (id, val) => {
    const el = $(id);
    if (el) el.textContent = val;
  };

  if (!d) {
    set("#sum-sm",  "—");
    set("#sum-st",  "—");
    set("#sum-hum", "N/A");
  } else {
    set("#sum-sm",  d.soil_moisture?.toFixed(1)    ?? "—");
    set("#sum-st",  d.soil_temperature?.toFixed(1) ?? "—");
    set("#sum-hum", d.humidity != null ? d.humidity.toFixed(1) : "N/A");
  }
}

// ── Quick Stats panel ────────────────────────────────────────────────────────
// FIX: was using window.state inside a setInterval in index.html,
// but state was a module-level local — not on window. Now it's on window.
function updateQuickStats() {
  const d   = window.state.sensorData;
  const set = (id, val) => { const el = $(id); if (el) el.innerHTML = val; };

  if (!d) {
    set("#mini-sm-val",  `— <span class="mini-stat-unit">%</span>`);
    set("#mini-at-val",  `N/A <span class="mini-stat-unit">°C</span>`);
    set("#mini-hum-val", `N/A <span class="mini-stat-unit">%</span>`);
    const src = $("#data-source");
    if (src) src.textContent = "❌ Arduino offline";
    return;
  }

  set("#mini-sm-val",
    `${d.soil_moisture?.toFixed(1) ?? "—"}<span class="mini-stat-unit"> %</span>`);
  set("#mini-at-val",
    d.air_temperature != null
      ? `${d.air_temperature.toFixed(1)}<span class="mini-stat-unit"> °C</span>`
      : `N/A <span class="mini-stat-unit">°C</span>`);
  set("#mini-hum-val",
    d.humidity != null
      ? `${d.humidity.toFixed(1)}<span class="mini-stat-unit"> %</span>`
      : `N/A <span class="mini-stat-unit">%</span>`);

  const src = $("#data-source");
  if (src) {
    src.textContent = d.source === "thingesp" ? "📡 ThingESP Live"
                    : d.source === "cached"   ? "🕐 Cached data"
                    : "🔄 Unknown";
  }
}

// ── Chart ─────────────────────────────────────────────────────────────────────
function pushToHistory(d) {
  const now = new Date().toLocaleTimeString("en-IN",
    { hour12: false, timeStyle: "short" });
  window.state.historyMoist.push(d.soil_moisture   ?? null);
  window.state.historyTemp.push(d.soil_temperature ?? null);
  window.state.historyLabels.push(now);
  if (window.state.historyMoist.length > window.state.maxHistory) {
    window.state.historyMoist.shift();
    window.state.historyTemp.shift();
    window.state.historyLabels.shift();
  }
}

function initChart() {
  const ctx = $("#liveChart");
  if (!ctx) return;
  window.state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: window.state.historyLabels,
      datasets: [
        {
          label: "Soil Moisture (%)",
          data: window.state.historyMoist,
          borderColor: "#A8FF3E",
          backgroundColor: "rgba(168,255,62,0.08)",
          borderWidth: 2, pointRadius: 3,
          pointBackgroundColor: "#A8FF3E",
          tension: 0.45, fill: true, yAxisID: "y",
          spanGaps: true,
        },
        {
          label: "Soil Temperature (°C)",
          data: window.state.historyTemp,
          borderColor: "#FFAB40",
          backgroundColor: "rgba(255,171,64,0.06)",
          borderWidth: 2, pointRadius: 3,
          pointBackgroundColor: "#FFAB40",
          tension: 0.45, fill: true, yAxisID: "y1",
          spanGaps: true,
        },
      ],
    },
    options: {
      responsive: true,
      animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#C8DEC9", font: { family: "JetBrains Mono", size: 11 } },
        },
        tooltip: {
          backgroundColor: "#0D1810",
          borderColor: "rgba(168,255,62,.3)", borderWidth: 1,
          titleColor: "#A8FF3E", bodyColor: "#C8DEC9",
          titleFont: { family: "JetBrains Mono", size: 11 },
          bodyFont:  { family: "JetBrains Mono", size: 11 },
        },
      },
      scales: {
        x: {
          ticks: { color: "#4A6350", font: { family: "JetBrains Mono", size: 10 }, maxRotation: 0 },
          grid:  { color: "rgba(168,255,62,.06)" },
        },
        y: {
          position: "left", min: 0, max: 100,
          ticks: { color: "#A8FF3E", font: { family: "JetBrains Mono", size: 10 } },
          grid:  { color: "rgba(168,255,62,.08)" },
        },
        y1: {
          position: "right", min: 0, max: 60,
          ticks: { color: "#FFAB40", font: { family: "JetBrains Mono", size: 10 } },
          grid:  { display: false },
        },
      },
    },
  });
}

function updateChart() {
  if (!window.state.chart) return;
  window.state.chart.data.labels            = window.state.historyLabels;
  window.state.chart.data.datasets[0].data  = window.state.historyMoist;
  window.state.chart.data.datasets[1].data  = window.state.historyTemp;
  window.state.chart.update("quiet");
}

// ── Prediction ────────────────────────────────────────────────────────────────
async function runPrediction() {
  if (!window.state.connected) {
    toast("❌ Arduino is offline — cannot predict without real sensor data.", "error");
    return;
  }
  if (!window.state.sensorData) {
    toast("Sensor data not loaded yet — please wait.", "error");
    return;
  }

  const btn   = $("#btn-predict");
  const crop  = $("#crop-select").value;
  const ptext = $("#pred-text").value.trim();

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Predicting…';

  try {
    const res  = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        crop, prediction_text: ptext,
        sensor_data: window.state.sensorData,
      }),
    });
    const json = await res.json();

    if (res.status === 503) {
      toast("❌ Arduino offline — prediction blocked.", "error");
      return;
    }
    if (!json.success) throw new Error(json.error);

    window.state.prediction = json.prediction;
    renderPrediction(json.prediction);
    toast(`✅ Predicted: ${json.prediction.recommended_crop}`, "success");

  } catch (err) {
    toast(`Prediction error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "🌾 Predict";
  }
}

function renderPrediction(p) {
  const panel = $("#result-panel");
  if (!panel) return;

  const conf   = p.confidence_pct;
  const circum = 2 * Math.PI * 44;
  const offset = circum * (1 - conf / 100);
  const stroke = conf >= 80 ? "#A8FF3E" : conf >= 60 ? "#FFAB40" : "#FF6B6B";

  const alertsHTML = (p.alerts || []).length
    ? p.alerts.map(a =>
        `<div class="alert-item ${a.type}">
          <span>${{warning:"⚠",info:"ℹ",danger:"🔴",success:"✅"}[a.type]||"•"}</span>
          <span>${a.msg}</span>
        </div>`
      ).join("")
    : `<div class="alert-item success">✅ All conditions look favourable!</div>`;

  panel.innerHTML = `
    <div>
      <div class="gauge-wrap">
        <svg class="gauge-svg" width="110" height="110" viewBox="0 0 110 110">
          <circle class="gauge-arc-bg" cx="55" cy="55" r="44"
            stroke-dasharray="${circum}" stroke-dashoffset="0"
            transform="rotate(-90 55 55)"/>
          <circle class="gauge-arc-fill" id="gauge-arc" cx="55" cy="55" r="44"
            stroke="${stroke}" stroke-dasharray="${circum}"
            stroke-dashoffset="${circum}" transform="rotate(-90 55 55)"/>
          <text class="gauge-label" x="55" y="60">${conf}%</text>
          <text class="gauge-sub"   x="55" y="74">CONFIDENCE</text>
        </svg>
        <div class="gauge-info">
          <div class="gauge-crop">${p.recommended_crop}</div>
          <div class="gauge-months">⏱ ${p.growth_months} months to harvest</div>
          <div class="gauge-model">via ${p.model_used}</div>
        </div>
      </div>
    </div>
    <div class="alerts-list">${alertsHTML}</div>
    <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">
      ${p.prediction_text
        ? `<b style="color:var(--text)">Your note:</b> "${p.prediction_text}"`
        : "No custom note provided."}
    </div>`;

  requestAnimationFrame(() => {
    const arc = $("#gauge-arc");
    if (arc) arc.style.strokeDashoffset = offset;
  });
}

// ── Report ────────────────────────────────────────────────────────────────────
async function generateReport() {
  if (!window.state.connected) {
    toast("❌ Arduino is offline — report requires real sensor data.", "error");
    return;
  }

  const btn = $("#btn-report");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating PDF…';

  try {
    const res  = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sensor_data: window.state.sensorData,
        prediction:  window.state.prediction || {},
      }),
    });
    const json = await res.json();

    if (res.status === 503) {
      toast("❌ Arduino offline — report blocked.", "error");
      return;
    }
    if (!json.success) throw new Error(json.error);

    const link = document.createElement("a");
    link.href     = json.pdf_url;
    link.download = json.filename;
    link.click();
    toast("📄 PDF report downloaded!", "success");

  } catch (err) {
    toast(`Report error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "📄 Download Report";
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = "") {
  const container = $("#toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  initChart();

  // Show offline state immediately before first fetch
  renderSensorCardsOffline();
  updateButtonStates();

  // First fetches
  await fetchConnectionStatus();
  await fetchSensorData();

  // Polling intervals
  setInterval(fetchConnectionStatus, 5000);   // connection banner
  setInterval(fetchSensorData,       5000);   // sensor cards
}

document.addEventListener("DOMContentLoaded", init);
