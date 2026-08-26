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
  advisory:      null,
  vision:        null,
  connected:     false,
  fieldId:       "",
  fields:        [],
  historyMoist:  [],
  historyTemp:   [],
  historyLabels: [],
  chart:         null,
  analyticsChart: null,
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
    const fieldId = getFieldId();
    const res  = await fetch(`/api/status?field_id=${encodeURIComponent(fieldId)}`);
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
    let msg = getFieldId() ? "Device offline" : "No field selected";
    if (status.error) msg += ` — ${status.error}`;
    text.textContent = msg;
  }
}

function updateButtonStates() {
  const btnPredict = $("#btn-predict");
  const btnReport  = $("#btn-report");
  if (!btnPredict) return;

  // Buttons ONLY enabled when Arduino is actually connected — never for simulated/offline data
  const canPredict = window.state.connected === true;

  btnPredict.disabled = !canPredict;
  btnPredict.title    = canPredict ? "" : "Arduino must be online to predict";
  btnReport.disabled  = !canPredict;
  btnReport.title     = canPredict ? "" : "Arduino must be online to generate report";
}

function getFieldId() {
  const el = $("#field-id");
  return (el && el.value) || window.state.fieldId || "";
}

async function loadFields(selectFieldId = "") {
  const res = await fetch("/api/fields");
  if (res.status === 401) {
    window.location.href = "/login";
    return [];
  }
  const json = await res.json();
  if (!json.success) throw new Error(json.error || "Unable to load fields");

  const fields = json.fields || [];
  window.state.fields = fields;
  const select = $("#field-id");
  if (!select) return fields;

  select.innerHTML = fields.length
    ? fields.map(field =>
        `<option value="${field.id}">${escapeHtml(field.name)}</option>`
      ).join("")
    : `<option value="">No fields yet</option>`;

  const nextId = selectFieldId || window.state.fieldId || fields[0]?.id || "";
  if (fields.some(field => field.id === nextId)) select.value = nextId;
  window.state.fieldId = select.value;
  renderFieldList(fields);
  return fields;
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function clearFieldFormError() {
  const error = $("#field-form-error");
  if (!error) return;
  error.textContent = "";
  error.classList.add("hidden");
}

function showFieldFormError(message) {
  const error = $("#field-form-error");
  if (!error) return;
  error.textContent = message;
  error.classList.remove("hidden");
}

function formatFieldDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function renderFieldList(fields = window.state.fields || []) {
  const list = $("#field-list");
  if (!list) return;

  if (!fields.length) {
    list.innerHTML = '<p class="field-list-empty">No fields yet. Add one with + Field.</p>';
    return;
  }

  list.innerHTML = fields.map(field => `
    <div class="field-list-item" data-field-id="${escapeHtml(field.id)}">
      <div class="field-list-meta">
        <div class="field-list-name">${escapeHtml(field.name)}</div>
        <div class="field-list-date">Paired ${escapeHtml(formatFieldDate(field.created_at))}</div>
      </div>
      <div class="field-list-actions">
        <button class="btn btn-outline btn-sm btn-edit-field" type="button" data-field-id="${escapeHtml(field.id)}">Edit</button>
        <button class="btn btn-outline btn-sm btn-delete-field" type="button" data-field-id="${escapeHtml(field.id)}">Delete</button>
      </div>
    </div>
  `).join("");
}

function openAddFieldDialog() {
  const form = $("#field-form");
  const deviceInput = $("#field-device-id");
  clearFieldFormError();
  $("#field-edit-id").value = "";
  $("#field-dialog-title").textContent = "Add a field";
  $("#field-dialog-copy").textContent =
    "Enter the exact Device ID configured in the ESP8266 sketch. It is used once to securely pair incoming readings with this field.";
  $("#field-device-hint")?.classList.add("hidden");
  $("#btn-save-field").textContent = "Pair field";
  if (deviceInput) {
    deviceInput.value = "";
    deviceInput.required = true;
  }
  form?.reset();
  $("#fields-manage-dialog")?.close();
  $("#field-dialog")?.showModal();
}

function openEditFieldDialog(fieldId) {
  const field = (window.state.fields || []).find(item => item.id === fieldId);
  if (!field) return;

  clearFieldFormError();
  $("#field-edit-id").value = field.id;
  $("#field-name").value = field.name;
  const deviceInput = $("#field-device-id");
  if (deviceInput) {
    deviceInput.value = "";
    deviceInput.required = false;
  }
  $("#field-dialog-title").textContent = "Edit field";
  $("#field-dialog-copy").textContent =
    "Update the field name or enter a new Device ID to re-pair the ESP8266.";
  $("#field-device-hint")?.classList.remove("hidden");
  $("#btn-save-field").textContent = "Save changes";
  $("#fields-manage-dialog")?.close();
  $("#field-dialog")?.showModal();
}

async function saveField(event) {
  event.preventDefault();
  const button = $("#btn-save-field");
  const editId = $("#field-edit-id").value.trim();
  const isEdit = Boolean(editId);
  const name = $("#field-name").value.trim();
  const deviceId = $("#field-device-id").value.trim();

  clearFieldFormError();

  if (!isEdit && !deviceId) {
    showFieldFormError("Device ID is required when pairing a new field.");
    return;
  }

  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span> ${isEdit ? "Saving…" : "Pairing…"}`;
  try {
    const payload = { name };
    if (deviceId) payload.device_id = deviceId;

    const res = await fetch(isEdit ? `/api/fields/${encodeURIComponent(editId)}` : "/api/fields", {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(isEdit ? payload : { name, device_id: deviceId }),
    });
    const json = await res.json();

    if (res.status === 409) {
      showFieldFormError(json.error || "This Device ID is already paired");
      return;
    }
    if (!json.success) throw new Error(json.error || "Unable to save field");

    const fieldId = isEdit ? editId : json.field.id;
    await loadFields(fieldId);
    $("#field-form").reset();
    $("#field-edit-id").value = "";
    $("#field-dialog").close();
    await fetchConnectionStatus();
    await fetchSensorData();
    fetchAnalytics();
    toast(
      isEdit ? `Field "${json.field.name}" updated` : `Field "${json.field.name}" paired`,
      "success"
    );
  } catch (err) {
    showFieldFormError(err.message);
  } finally {
    button.disabled = false;
    button.textContent = isEdit ? "Save changes" : "Pair field";
  }
}

async function deleteField(fieldId) {
  const field = (window.state.fields || []).find(item => item.id === fieldId);
  if (!field) return;

  const confirmed = window.confirm(
    `Delete "${field.name}"? This removes its telemetry and analytics history.`
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/fields/${encodeURIComponent(fieldId)}`, {
      method: "DELETE",
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.error || "Unable to delete field");

    const wasSelected = getFieldId() === fieldId;
    await loadFields();
    if (wasSelected) {
      await fetchConnectionStatus();
      await fetchSensorData();
      fetchAnalytics();
    }
    toast(`Field "${field.name}" deleted`, "success");
  } catch (err) {
    toast(err.message, "error");
  }
}

function openManageFieldsDialog() {
  renderFieldList(window.state.fields || []);
  $("#fields-manage-dialog")?.showModal();
}

// ── Farmer advisory + environmental risk ──────────────────────────────────────
async function fetchAdvisory() {
  if (!window.state.connected || !window.state.sensorData) {
    renderAdvisoryOffline();
    return;
  }
  try {
    const res = await fetch("/api/advisory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        field_id: getFieldId(),
        vision: window.state.vision || undefined,
      }),
    });
    const json = await res.json();
    if (res.status === 503) {
      renderAdvisoryOffline();
      return;
    }
    if (!json.success) throw new Error(json.error);
    window.state.advisory = json;
    renderAdvisory(json);
    fetchAnalytics();
  } catch (err) {
    console.warn("Advisory error:", err);
  }
}

function renderAdvisoryOffline() {
  const list = $("#advisory-list");
  if (list) {
    list.innerHTML = `<div class="no-result" style="padding:16px;">
      Arduino offline — advisory unavailable. Connect sensors for live advice.
    </div>`;
  }
  const msg = $("#irrigation-msg");
  if (msg) msg.innerHTML = `<span class="irrigation-text">Waiting for live soil moisture…</span>`;
  const meta = $("#irrigation-meta");
  if (meta) meta.innerHTML = "";
  const score = $("#risk-score");
  if (score) score.textContent = "—";
  const level = $("#risk-level");
  if (level) level.textContent = "Yield risk";
  const bars = $("#risk-bars");
  if (bars) bars.innerHTML = "";
}

function renderAdvisory(bundle) {
  const list = $("#advisory-list");
  if (list) {
    const items = bundle.advisories || [];
    list.innerHTML = items.map(a => {
      const speech = `${a.title}. ${a.detail}`;
      return `<div class="alert-item ${a.severity}">
        <span>${{warning:"⚠",info:"ℹ",danger:"🔴",success:"✅"}[a.severity]||"•"}</span>
        <span class="alert-text"><b>${a.title}</b> — ${a.detail}</span>
        ${window.ttsBtn ? window.ttsBtn(speech, "Listen to alert") : ""}
      </div>`;
    }).join("") || `<div class="alert-item success">✅ Conditions stable</div>`;
  }

  const irr = bundle.irrigation || {};
  const msg = $("#irrigation-msg");
  if (msg) {
    const irrText = irr.message || "—";
    msg.innerHTML = `<span class="irrigation-text">${irrText}</span>${window.ttsBtn ? window.ttsBtn(irrText, "Listen to irrigation advice") : ""}`;
  }
  const meta = $("#irrigation-meta");
  if (meta) {
    const metaText = irr.action
      ? `Action: ${irr.action.replace(/_/g, " ")} · Urgency: ${irr.urgency} · Next check: ${irr.next_check_hours}h · ~${irr.suggested_litres_per_m2 || 0} L/m²`
      : "";
    meta.innerHTML = metaText
      ? `<span class="irrigation-meta-text">${metaText}</span>${window.ttsBtn ? window.ttsBtn(metaText, "Listen to irrigation details") : ""}`
      : "";
  }
  const box = $("#irrigation-box");
  if (box) {
    box.className = "irrigation-box " + (irr.urgency || "");
  }

  const risks = bundle.environmental_risks || {};
  const scoreEl = $("#risk-score");
  if (scoreEl) scoreEl.textContent = `${risks.yield_risk_pct ?? "—"}%`;
  const levelEl = $("#risk-level");
  if (levelEl) levelEl.textContent = `Yield risk · ${(risks.overall_level || "").toUpperCase()}`;

  const bars = $("#risk-bars");
  if (bars && risks.risks) {
    bars.innerHTML = risks.risks.map(r => {
      const speech = `${r.label}. Score ${r.score}. Level ${r.level}.`;
      return `
      <div class="risk-row">
        <div class="risk-row-top">
          <span>${r.label}</span>
          <span class="risk-row-actions">
            <span class="risk-pct level-${r.level}">${r.score}</span>
            ${window.ttsBtn ? window.ttsBtn(speech, "Listen to risk") : ""}
          </span>
        </div>
        <div class="risk-track"><div class="risk-fill level-${r.level}" style="width:${r.score}%"></div></div>
      </div>`;
    }).join("");
  }
}

// ── Edge vision (disease / pest / nutrient) ───────────────────────────────────
async function runVisionScan(demoProfile = null) {
  const btn = $("#btn-vision");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scanning…';
  }

  try {
    let res;
    if (demoProfile) {
      res = await fetch("/api/vision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          demo_profile: demoProfile,
          field_id: getFieldId(),
          crop: $("#crop-select")?.value || "",
        }),
      });
    } else {
      const fileInput = $("#leaf-image");
      const file = fileInput?.files?.[0];
      if (!file) {
        toast("Select a leaf image first, or use a Demo button.", "warning");
        return;
      }
      const preview = $("#vision-preview");
      const wrap = $("#vision-preview-wrap");
      if (preview && wrap) {
        preview.src = URL.createObjectURL(file);
        wrap.classList.remove("hidden");
      }
      const fd = new FormData();
      fd.append("image", file);
      fd.append("field_id", getFieldId());
      fd.append("crop", $("#crop-select")?.value || "");
      res = await fetch("/api/vision", { method: "POST", body: fd });
    }

    const json = await res.json();
    if (!json.success) throw new Error(json.error || "Vision scan failed");

    window.state.vision = json.vision;
    if (json.advisory) {
      window.state.advisory = json.advisory;
      renderAdvisory(json.advisory);
    }
    renderVision(json.vision);
    fetchAnalytics();
    toast("Leaf scan complete (edge processed)", "success");
  } catch (err) {
    toast(`Vision error: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "Scan Leaf";
    }
  }
}

function renderVision(v) {
  const panel = $("#vision-panel-body");
  if (!panel || !v) return;

  const flag = (ok, label, conf) =>
    `<div class="vision-flag ${ok ? "on" : "off"}">
      <span>${ok ? "⚠" : "✓"} ${label}</span>
      <span class="vision-conf">${Math.round((conf || 0) * 100)}%</span>
    </div>`;

  panel.innerHTML = `
    <div class="vision-health">
      <div class="vision-health-score">${v.field_health_score ?? "—"}</div>
      <div>
        <div class="gauge-crop" style="font-size:20px;">Field health</div>
        <div class="gauge-months">${v.growth_stage || ""}</div>
        <div class="gauge-model">via ${v.model || "edge vision"}</div>
      </div>
    </div>
    <div class="vision-flags">
      ${flag(v.disease_detected, "Disease", v.disease_confidence)}
      ${flag(v.pest_detected, "Pest", v.pest_confidence)}
      ${flag(v.nutrient_flag, "Nutrient", v.nutrient_confidence)}
    </div>
    <div class="alerts-list">
      <div class="alert-item ${v.disease_detected ? "danger" : "success"}">
        <span>${v.disease_detected ? "🔴" : "✅"}</span>
        <span class="alert-text">${v.disease_summary || "—"}</span>
        ${window.ttsBtn ? window.ttsBtn(v.disease_summary || "No disease detected", "Listen to disease summary") : ""}
      </div>
      <div class="alert-item ${v.pest_detected ? "warning" : "success"}">
        <span>${v.pest_detected ? "⚠" : "✅"}</span>
        <span class="alert-text">${v.pest_summary || "—"}</span>
        ${window.ttsBtn ? window.ttsBtn(v.pest_summary || "No pest detected", "Listen to pest summary") : ""}
      </div>
      <div class="alert-item ${v.nutrient_flag ? "warning" : "info"}">
        <span>${v.nutrient_flag ? "⚠" : "ℹ"}</span>
        <span class="alert-text">${v.nutrient_summary || "—"}</span>
        ${window.ttsBtn ? window.ttsBtn(v.nutrient_summary || "No nutrient issues", "Listen to nutrient summary") : ""}
      </div>
    </div>
    <ul class="rec-list">
      ${(v.recommendations || []).map(r =>
        `<li class="rec-item"><span>${r}</span>${window.ttsBtn ? window.ttsBtn(r, "Listen to recommendation") : ""}</li>`
      ).join("")}
    </ul>`;
}

// ── Farm analytics ────────────────────────────────────────────────────────────
async function fetchAnalytics() {
  try {
    const res = await fetch(`/api/analytics?field_id=${encodeURIComponent(getFieldId())}&limit=50`);
    const json = await res.json();
    if (!json.success) return;
    renderAnalytics(json.summary);
  } catch (err) {
    console.warn("Analytics error:", err);
  }
}

function renderAnalytics(s) {
  if (!s) return;
  const set = (id, html) => { const el = $(id); if (el) el.innerHTML = html; };
  set("#an-moist", s.avg_moisture != null
    ? `${s.avg_moisture}<span class="mini-stat-unit"> %</span>` : `— <span class="mini-stat-unit">%</span>`);
  set("#an-risk", s.avg_yield_risk != null
    ? `${s.avg_yield_risk}<span class="mini-stat-unit"> %</span>` : `— <span class="mini-stat-unit">%</span>`);
  set("#an-disease", String(s.disease_events ?? "—"));
  set("#an-pest", String(s.pest_events ?? "—"));
  set("#an-irrigate", String(s.irrigation_irrigate_now_count ?? "—"));

  const trend = s.trend || [];
  if (!window.state.analyticsChart) return;
  window.state.analyticsChart.data.labels = trend.map(t => t.t);
  window.state.analyticsChart.data.datasets[0].data = trend.map(t => t.moisture);
  window.state.analyticsChart.data.datasets[1].data = trend.map(t => t.yield_risk);
  window.state.analyticsChart.update("quiet");
}

function initAnalyticsChart() {
  const ctx = $("#analyticsChart");
  if (!ctx) return;
  window.state.analyticsChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Moisture (%)",
          data: [],
          borderColor: "#A8FF3E",
          backgroundColor: "rgba(168,255,62,0.08)",
          borderWidth: 2, pointRadius: 2, tension: 0.4, fill: true, yAxisID: "y",
        },
        {
          label: "Yield risk (%)",
          data: [],
          borderColor: "#FF6B6B",
          backgroundColor: "rgba(255,107,107,0.06)",
          borderWidth: 2, pointRadius: 2, tension: 0.4, fill: true, yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      animation: { duration: 350 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#C8DEC9", font: { family: "JetBrains Mono", size: 11 } },
        },
      },
      scales: {
        x: {
          ticks: { color: "#4A6350", font: { family: "JetBrains Mono", size: 10 } },
          grid:  { color: "rgba(168,255,62,.06)" },
        },
        y: {
          position: "left", min: 0, max: 100,
          ticks: { color: "#A8FF3E", font: { family: "JetBrains Mono", size: 10 } },
          grid:  { color: "rgba(168,255,62,.08)" },
        },
        y1: {
          position: "right", min: 0, max: 100,
          ticks: { color: "#FF6B6B", font: { family: "JetBrains Mono", size: 10 } },
          grid:  { display: false },
        },
      },
    },
  });
}

// ── Sensor data polling ───────────────────────────────────────────────────────
async function fetchSensorData() {
  try {
    const fieldId = getFieldId();
    if (!fieldId) {
      window.state.connected = false;
      window.state.sensorData = null;
      renderSensorCardsOffline();
      updateButtonStates();
      return;
    }
    const res  = await fetch(`/api/sensor-data?field_id=${encodeURIComponent(fieldId)}`);

    if (res.status === 503) {
      window.state.connected  = false;
      window.state.sensorData = null;
      renderSensorCardsOffline();
      updateSensorSummary();
      updateQuickStats();
      updateButtonStates();
      return;
    }

    const json = await res.json();
    if (!json.success) throw new Error(json.error);

    const wasOffline = !window.state.connected;

    window.state.sensorData = json.data;
    window.state.connected  = true;
    renderSensorCards(json.data);
    pushToHistory(json.data);
    updateChart();
    updateSensorSummary();
    updateQuickStats();
    updateButtonStates();

    // Refresh farmer advisory when sensors update
    if (wasOffline || !window.state.advisory) {
      fetchAdvisory();
    }

    // If Arduino just came online, clear the "waiting" placeholder in result panel
    if (wasOffline) {
      const panel = $("#result-panel");
      if (panel && panel.querySelector(".no-result")) {
        panel.innerHTML = `
          <div class="no-result">
            <span class="no-result-icon">✅</span>
            Arduino connected!<br>
            <span style="font-size:11px;margin-top:8px;display:block;color:var(--text-dim);">
              Fill in your details and click <b>Predict</b> to get a crop recommendation.
            </span>
          </div>`;
      }
    }

  } catch (err) {
    console.warn("Sensor fetch error:", err);
    // Network error — clear data and show offline state
    window.state.connected  = false;
    window.state.sensorData = null;
    renderSensorCardsOffline();
    updateSensorSummary();
    updateQuickStats();
    updateButtonStates();
  }
}

// ── Render sensor cards ───────────────────────────────────────────────────────
function renderSensorCards(d) {
  // Real sensors on Arduino
  setCard("sm",  d.soil_moisture,    100, d.soil_moisture < 30 ? "coral" : "");
  setCard("st",  d.soil_temperature,  60, "");
  setCard("wl",  d.water_level,      100, d.water_level < 25 ? "coral" : "sky");

  // Absent sensors — backend provides simulated values correlated with soil data
  const sim = d.simulated;  // true when values are estimated

  if (d.air_temperature != null) {
    setCard("at", d.air_temperature, 50, "amber");
    markSimulated("at", sim);
  } else { setCardNA("at"); }

  if (d.humidity != null) {
    setCard("hum", d.humidity, 100, "");
    markSimulated("hum", sim);
  } else { setCardNA("hum"); }

  if (d.rainfall != null) {
    setCard("rain", d.rainfall, 200, "sky");
    markSimulated("rain", sim);
  } else { setCardNA("rain"); }

  if (d.light_intensity != null) {
    setCard("lux", d.light_intensity, 100, "amber");
    markSimulated("lux", sim);
  } else { setCardNA("lux"); }

  if (d.ph != null) {
    setCard("ph", d.ph, 14, d.ph < 6 || d.ph > 7.5 ? "coral" : "");
    markSimulated("ph", sim);
  } else { setCardNA("ph"); }
}

function markSimulated(id, isSimulated) {
  const unitEl = document.querySelector(`#card-${id} .sensor-unit`);
  if (!unitEl) return;
  if (isSimulated) {
    unitEl.innerHTML = unitEl.textContent.replace(/\s*~sim.*$/, "") +
      ' <span style="font-size:9px;color:var(--text-dim);opacity:0.7;" title="Sensor not on device — estimated value">~sim</span>';
  }
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
    const humEl = $("#sum-hum");
    if (humEl) {
      if (d.humidity != null) {
        humEl.textContent = d.humidity.toFixed(1) + (d.simulated ? " ~sim" : "");
      } else {
        humEl.textContent = "N/A";
      }
    }
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
    set("#mini-at-val",  `— <span class="mini-stat-unit">°C</span>`);
    set("#mini-hum-val", `— <span class="mini-stat-unit">%</span>`);
    const src = $("#data-source");
    if (src) src.textContent = "❌ Arduino offline";
    return;
  }

  const simTag = d.simulated
    ? `<span style="font-size:9px;color:var(--text-dim);margin-left:2px;" title="Estimated — sensor not on device">~sim</span>`
    : "";

  set("#mini-sm-val",
    `${d.soil_moisture?.toFixed(1) ?? "—"}<span class="mini-stat-unit"> %</span>`);
  set("#mini-at-val",
    d.air_temperature != null
      ? `${d.air_temperature.toFixed(1)}<span class="mini-stat-unit"> °C</span>${simTag}`
      : `N/A <span class="mini-stat-unit">°C</span>`);
  set("#mini-hum-val",
    d.humidity != null
      ? `${d.humidity.toFixed(1)}<span class="mini-stat-unit"> %</span>${simTag}`
      : `N/A <span class="mini-stat-unit">%</span>`);

  const src = $("#data-source");
  if (src) {
    src.textContent = d.source === "arduino_direct" ? "🔌 Arduino Direct"
                    : d.source === "cached"         ? "🕐 Cached data"
                    : "🔄 Live";
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

// ── Local rule-based prediction (runs in-browser when backend is offline) ────
function localRulePredict(sensor, preferredCrop) {
  const m = sensor.soil_moisture    ?? 50;
  const t = sensor.soil_temperature ?? 25;
  const h = sensor.humidity         ?? 60;
  const r = sensor.rainfall         ?? 0;

  let crop, months, reason;
  if (m > 70 && t > 27)        { crop = "Rice";      months = 4;  reason = "High moisture + warm temp ideal for rice"; }
  else if (m < 38 && t < 23)   { crop = "Wheat";     months = 5;  reason = "Low moisture + cool temp suits wheat"; }
  else if (m > 65 || r > 100)  { crop = "Sugarcane"; months = 12; reason = "High moisture / rainfall suits sugarcane"; }
  else if (40 <= m && m <= 70) { crop = "Maize";     months = 3;  reason = "Moderate moisture ideal for maize"; }
  else if (preferredCrop)      { crop = preferredCrop.charAt(0).toUpperCase() + preferredCrop.slice(1); months = 4; reason = "Based on your preferred crop selection"; }
  else                         { crop = "Soybean";   months = 4;  reason = "Balanced conditions suit soybean"; }

  const thresholds = {
    wheat:{moisture:[30,60],temp:[15,25]}, rice:{moisture:[60,90],temp:[25,35]},
    maize:{moisture:[40,70],temp:[20,30]}, sugarcane:{moisture:[65,90],temp:[25,38]},
    soybean:{moisture:[45,75],temp:[20,30]},
  };
  const key = crop.toLowerCase();
  const th  = thresholds[key];
  let conf  = 0.72;
  if (th) {
    const ms = m >= th.moisture[0] && m <= th.moisture[1] ? 1.0 : Math.max(0, 1 - Math.abs(m - (th.moisture[0]+th.moisture[1])/2)/40);
    const ts = t >= th.temp[0]    && t <= th.temp[1]    ? 1.0 : Math.max(0, 1 - Math.abs(t - (th.temp[0]+th.temp[1])/2)/20);
    conf = Math.round((ms*0.5 + ts*0.5) * 100) / 100;
  }

  const alerts = [];
  if (m < 30) alerts.push({type:"warning", msg:"Low soil moisture — irrigation recommended"});
  if (m > 82) alerts.push({type:"info",    msg:"High moisture — check drainage"});
  if (t > 36) alerts.push({type:"danger",  msg:"Heat stress risk — apply shade/cooling"});

  return {
    recommended_crop: crop,
    growth_months:    months,
    confidence:       conf,
    confidence_pct:   Math.round(conf * 100),
    prediction_text:  "",
    user_crop:        preferredCrop,
    alerts,
    model_used:       "In-browser rule engine (Arduino offline)",
    reason,
    timestamp:        new Date().toISOString(),
  };
}

// ── Prediction ────────────────────────────────────────────────────────────────
async function runPrediction() {
  if (!window.state.connected) {
    toast("❌ Arduino must be online to run a prediction.", "error");
    return;
  }
  if (!window.state.sensorData) {
    toast("⚠️ No sensor data yet — please wait a moment.", "error");
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
        field_id: getFieldId(),
      }),
    });
    const json = await res.json();

    if (res.status === 503) {
      toast("❌ Arduino offline — prediction blocked.", "error");
      return;
    }
    if (!json.success) throw new Error(json.error);

    window.state.prediction = json.prediction;
    json.prediction.prediction_text = ptext;
    renderPrediction(json.prediction);
    if (json.prediction.advisory) {
      window.state.advisory = json.prediction.advisory;
      renderAdvisory(json.prediction.advisory);
    }
    fetchAnalytics();
    toast(`✅ Predicted: ${json.prediction.recommended_crop}`, "success");

  } catch (err) {
    toast(`Prediction error: ${err.message}`, "error");
  } finally {
    btn.disabled = !window.state.connected;
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
          <span class="alert-text">${a.msg}</span>
          ${window.ttsBtn ? window.ttsBtn(a.msg, "Listen to alert") : ""}
        </div>`
      ).join("")
    : `<div class="alert-item success">✅ All conditions look favourable!</div>`;

  const noteText = p.prediction_text
    ? `Your note: ${p.prediction_text}`
    : "No custom note provided.";
  const cropSpeech = window.collectPredictionSpeech
    ? window.collectPredictionSpeech(p)
    : `${p.recommended_crop}. Confidence ${p.confidence_pct} percent.`;

  panel.innerHTML = `
    <div class="card-head" style="margin-bottom:12px;">
      <h2 style="font-size:16px;margin:0;">Prediction Result</h2>
      ${window.ttsBtn ? window.ttsBtn(cropSpeech, "Listen to full prediction") : ""}
    </div>
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
    <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-dim);display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span>${p.prediction_text
        ? `<b style="color:var(--text)">Your note:</b> "${p.prediction_text}"`
        : "No custom note provided."}</span>
      ${window.ttsBtn && p.prediction_text ? window.ttsBtn(noteText, "Listen to your note") : ""}
    </div>`;

  requestAnimationFrame(() => {
    const arc = $("#gauge-arc");
    if (arc) arc.style.strokeDashoffset = offset;
  });
}

// ── Report ────────────────────────────────────────────────────────────────────
async function generateReport() {
  if (!window.state.prediction) {
    toast("⚠️ Run a prediction first before downloading the report.", "error");
    return;
  }
  if (!window.state.connected) {
    toast("❌ Arduino must be online to generate a PDF report.", "error");
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
        prediction:  window.state.prediction || {},
        field_id: getFieldId(),
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
  initAnalyticsChart();

  // ── Wire up button click listeners ──────────────────────────────────────
  const btnPredict = $("#btn-predict");
  const btnReport  = $("#btn-report");
  if (btnPredict) btnPredict.addEventListener("click", runPrediction);
  if (btnReport)  btnReport.addEventListener("click",  generateReport);

  const btnAdvisory = $("#btn-advisory");
  if (btnAdvisory) btnAdvisory.addEventListener("click", fetchAdvisory);

  $("#btn-tts-advisory")?.addEventListener("click", () => {
    if (window.collectAdvisorySpeech && window.playTts) {
      window.playTts(window.collectAdvisorySpeech(window.state.advisory));
    }
  });
  $("#btn-tts-risk")?.addEventListener("click", () => {
    if (window.collectAdvisorySpeech && window.playTts) {
      window.playTts(window.collectAdvisorySpeech(window.state.advisory));
    }
  });
  $("#btn-tts-vision")?.addEventListener("click", () => {
    if (window.collectVisionSpeech && window.playTts) {
      window.playTts(window.collectVisionSpeech(window.state.vision));
    }
  });
  $("#btn-tts-prediction")?.addEventListener("click", () => {
    if (window.collectPredictionSpeech && window.playTts) {
      window.playTts(window.collectPredictionSpeech(window.state.prediction));
    }
  });

  const btnVision = $("#btn-vision");
  if (btnVision) btnVision.addEventListener("click", () => runVisionScan());

  const demoDisease = $("#btn-demo-disease");
  const demoPest = $("#btn-demo-pest");
  const demoNutrient = $("#btn-demo-nutrient");
  if (demoDisease) demoDisease.addEventListener("click", () => runVisionScan("disease"));
  if (demoPest) demoPest.addEventListener("click", () => runVisionScan("pest"));
  if (demoNutrient) demoNutrient.addEventListener("click", () => runVisionScan("nutrient"));

  const fieldSel = $("#field-id");
  if (fieldSel) {
    fieldSel.addEventListener("change", async () => {
      window.state.fieldId = getFieldId();
      window.state.sensorData = null;
      window.state.advisory = null;
      await fetchConnectionStatus();
      await fetchSensorData();
      fetchAdvisory();
      fetchAnalytics();
    });
  }

  const fieldDialog = $("#field-dialog");
  const manageDialog = $("#fields-manage-dialog");
  $("#btn-add-field")?.addEventListener("click", openAddFieldDialog);
  $("#btn-manage-fields")?.addEventListener("click", openManageFieldsDialog);
  $("#btn-manage-add-field")?.addEventListener("click", openAddFieldDialog);
  $("#btn-close-field")?.addEventListener("click", () => fieldDialog?.close());
  $("#btn-cancel-field")?.addEventListener("click", () => fieldDialog?.close());
  $("#btn-close-manage-fields")?.addEventListener("click", () => manageDialog?.close());
  $("#btn-close-manage-fields-bottom")?.addEventListener("click", () => manageDialog?.close());
  $("#field-form")?.addEventListener("submit", saveField);
  $("#field-list")?.addEventListener("click", event => {
    const editBtn = event.target.closest(".btn-edit-field");
    const deleteBtn = event.target.closest(".btn-delete-field");
    if (editBtn) {
      openEditFieldDialog(editBtn.dataset.fieldId);
      return;
    }
    if (deleteBtn) deleteField(deleteBtn.dataset.fieldId);
  });

  // Show offline state immediately before first fetch
  renderSensorCardsOffline();
  updateButtonStates();
  try {
    await loadFields();
  } catch (err) {
    toast(err.message, "error");
  }
  fetchAnalytics();

  // First fetches
  await fetchConnectionStatus();
  await fetchSensorData();

  if (typeof maybeStartProductTour === "function") {
    maybeStartProductTour();
  }

  // Polling intervals
  setInterval(fetchConnectionStatus, 5000);   // connection banner
  setInterval(fetchSensorData,       5000);   // sensor cards
  setInterval(fetchAdvisory,        30000);   // advisory refresh
  setInterval(fetchAnalytics,       60000);   // analytics refresh
}

document.addEventListener("DOMContentLoaded", init);