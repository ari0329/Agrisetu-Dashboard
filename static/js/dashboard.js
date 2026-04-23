/* ============================================================
   AgriSetu Dashboard — Frontend Logic
   Handles: sensor polling, predictions, Chart.js, PDF report
   ============================================================ */

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  sensorData:    null,
  prediction:    null,
  historyMoist:  [],
  historyTemp:   [],
  historyLabels: [],
  chart:         null,
  polling:       null,
  maxHistory:    20,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = $('#clock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-IN', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Sensor data fetch ─────────────────────────────────────────────────────────
async function fetchSensorData() {
  try {
    const res  = await fetch('/api/sensor-data');
    const json = await res.json();
    if (!json.success) throw new Error(json.error || 'Fetch failed');

    state.sensorData = json.data;
    renderSensorCards(json.data);
    pushToHistory(json.data);
    updateChart();
  } catch (err) {
    console.warn('Sensor fetch error:', err);
  }
}

// ── Render sensor cards ───────────────────────────────────────────────────────
function renderSensorCards(d) {
  setCard('sm',   d.soil_moisture,    100, d.soil_moisture < 30 ? 'coral' : '');
  setCard('st',   d.soil_temperature,  60, '');
  setCard('at',   d.air_temperature,   50, d.air_temperature > 36 ? 'coral' : 'amber');
  setCard('hum',  d.humidity,         100, '');
  setCard('rain', d.rainfall,         200, 'sky');
  setCard('lux',  d.light_intensity, 1200, 'amber');
  setCard('wl',   d.water_level,      100, d.water_level < 25 ? 'coral' : 'sky');
  setCard('ph',   d.ph,                14, '');
}

function setCard(id, value, max, colorClass) {
  const card  = $(`#card-${id}`);
  const valEl = $(`#val-${id}`);
  const bar   = $(`#bar-${id}`);
  if (!card || !valEl) return;

  valEl.textContent = Number.isInteger(value) ? value : value.toFixed(1);

  // colour classes
  card.classList.remove('amber', 'sky', 'coral');
  if (colorClass) card.classList.add(colorClass);

  // bar fill
  if (bar) bar.style.width = `${Math.min(100, (value / max) * 100)}%`;
}

// ── History + Chart ───────────────────────────────────────────────────────────
function pushToHistory(d) {
  const now = new Date().toLocaleTimeString('en-IN', { hour12: false, timeStyle: 'short' });
  state.historyMoist.push(d.soil_moisture);
  state.historyTemp.push(d.soil_temperature);
  state.historyLabels.push(now);

  if (state.historyMoist.length > state.maxHistory) {
    state.historyMoist.shift();
    state.historyTemp.shift();
    state.historyLabels.shift();
  }
}

function initChart() {
  const ctx = $('#liveChart');
  if (!ctx) return;

  state.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: state.historyLabels,
      datasets: [
        {
          label: 'Soil Moisture (%)',
          data: state.historyMoist,
          borderColor: '#A8FF3E',
          backgroundColor: 'rgba(168,255,62,0.08)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#A8FF3E',
          tension: 0.45,
          fill: true,
          yAxisID: 'y',
        },
        {
          label: 'Soil Temperature (°C)',
          data: state.historyTemp,
          borderColor: '#FFAB40',
          backgroundColor: 'rgba(255,171,64,0.06)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#FFAB40',
          tension: 0.45,
          fill: true,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#C8DEC9', font: { family: 'JetBrains Mono', size: 11 } },
        },
        tooltip: {
          backgroundColor: '#0D1810',
          borderColor: 'rgba(168,255,62,.3)',
          borderWidth: 1,
          titleColor: '#A8FF3E',
          bodyColor: '#C8DEC9',
          titleFont: { family: 'JetBrains Mono', size: 11 },
          bodyFont: { family: 'JetBrains Mono', size: 11 },
        },
      },
      scales: {
        x: {
          ticks: { color: '#4A6350', font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0 },
          grid:  { color: 'rgba(168,255,62,.06)' },
        },
        y: {
          position: 'left',
          min: 0, max: 100,
          ticks: { color: '#A8FF3E', font: { family: 'JetBrains Mono', size: 10 } },
          grid:  { color: 'rgba(168,255,62,.08)' },
        },
        y1: {
          position: 'right',
          min: 0, max: 60,
          ticks: { color: '#FFAB40', font: { family: 'JetBrains Mono', size: 10 } },
          grid:  { display: false },
        },
      },
    },
  });
}

function updateChart() {
  if (!state.chart) return;
  state.chart.data.labels = state.historyLabels;
  state.chart.data.datasets[0].data = state.historyMoist;
  state.chart.data.datasets[1].data = state.historyTemp;
  state.chart.update('quiet');
}

// ── Mini stats ────────────────────────────────────────────────────────────────
function updateMiniStats(d) {
  setMini('mini-sm',  d.soil_moisture.toFixed(1),   '%');
  setMini('mini-at',  d.air_temperature.toFixed(1), '°C');
  setMini('mini-hum', d.humidity.toFixed(1),         '%');
}

function setMini(id, value, unit) {
  const v = $(`#${id}-val`);
  if (v) v.innerHTML = `${value}<span class="mini-stat-unit"> ${unit}</span>`;
}

// ── Prediction ────────────────────────────────────────────────────────────────
async function runPrediction() {
  const btn    = $('#btn-predict');
  const crop   = $('#crop-select').value;
  const ptext  = $('#pred-text').value.trim();

  if (!state.sensorData) {
    toast('Sensor data not loaded yet — please wait.', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Predicting…';

  try {
    const res  = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        crop, prediction_text: ptext, sensor_data: state.sensorData,
      }),
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.error);

    state.prediction = json.prediction;
    renderPrediction(json.prediction);
    toast(`Predicted: ${json.prediction.recommended_crop}`, 'success');
  } catch (err) {
    toast(`Prediction error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🌾 Predict';
  }
}

function renderPrediction(p) {
  const panel = $('#result-panel');
  if (!panel) return;

  const conf   = p.confidence_pct;
  const circum = 2 * Math.PI * 44;          // radius 44
  const offset = circum * (1 - conf / 100);

  // gauge stroke colour based on confidence
  const stroke = conf >= 80 ? '#A8FF3E' : conf >= 60 ? '#FFAB40' : '#FF6B6B';

  const alertsHTML = (p.alerts || []).length
    ? p.alerts.map(a =>
        `<div class="alert-item ${a.type}">
          <span>${alertIcon(a.type)}</span>
          <span>${a.msg}</span>
        </div>`
      ).join('')
    : `<div class="alert-item success">✅ All conditions look favourable!</div>`;

  panel.innerHTML = `
    <div>
      <div class="gauge-wrap">
        <svg class="gauge-svg" width="110" height="110" viewBox="0 0 110 110">
          <circle class="gauge-arc-bg"   cx="55" cy="55" r="44"
            stroke-dasharray="${circum}" stroke-dashoffset="0"
            transform="rotate(-90 55 55)"/>
          <circle class="gauge-arc-fill" id="gauge-arc" cx="55" cy="55" r="44"
            stroke="${stroke}"
            stroke-dasharray="${circum}"
            stroke-dashoffset="${circum}"
            transform="rotate(-90 55 55)"/>
          <text class="gauge-label" x="55" y="60">${conf}%</text>
          <text class="gauge-sub"   x="55" y="74">CONFIDENCE</text>
        </svg>
        <div class="gauge-info">
          <div class="gauge-crop" id="crop-name">${p.recommended_crop}</div>
          <div class="gauge-months">⏱ ${p.growth_months} months to harvest</div>
          <div class="gauge-model">via ${p.model_used}</div>
        </div>
      </div>
    </div>

    <div class="alerts-list">${alertsHTML}</div>

    <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim)">
      ${p.prediction_text
        ? `<b style="color:var(--text)">Your note:</b> "${p.prediction_text}"`
        : 'No custom note provided.'}
    </div>
  `;

  // Animate gauge
  requestAnimationFrame(() => {
    const arc = $('#gauge-arc');
    if (arc) arc.style.strokeDashoffset = offset;
  });
}

function alertIcon(type) {
  return { warning: '⚠', info: 'ℹ', danger: '🔴', success: '✅' }[type] || '•';
}

// ── Report ────────────────────────────────────────────────────────────────────
async function generateReport() {
  if (!state.sensorData) {
    toast('Sensor data required — please wait for data.', 'error');
    return;
  }

  const btn = $('#btn-report');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating PDF…';

  try {
    const res  = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sensor_data: state.sensorData,
        prediction:  state.prediction || {},
      }),
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.error);

    // Auto-download
    const link = document.createElement('a');
    link.href     = json.pdf_url;
    link.download = json.filename;
    link.click();
    toast('📄 PDF report downloaded!', 'success');
  } catch (err) {
    toast(`Report error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '📄 Download Report';
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type = '') {
  const container = $('#toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  initChart();
  await fetchSensorData();               // first fetch immediately
  state.polling = setInterval(fetchSensorData, 5000);  // then every 5 s

  // Wire up buttons
  $('#btn-predict')?.addEventListener('click', runPrediction);
  $('#btn-report')?.addEventListener('click',  generateReport);

  // Show initial placeholder in result panel
  const panel = $('#result-panel');
  if (panel) panel.innerHTML = `
    <div class="no-result">
      <span class="no-result-icon">🌱</span>
      Fill in the form and click <b>Predict</b><br>to see your crop recommendation here.
    </div>`;
}

document.addEventListener('DOMContentLoaded', init);
