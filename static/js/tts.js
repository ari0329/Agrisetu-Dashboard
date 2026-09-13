/* AgriSetu — Text-to-Speech (gTTS via /api/tts) */

let currentTtsAudio = null;

function ttsLang() {
  return window.i18n?.lang || window.AGRISETU_LANG || "en";
}

function ttsLabel(key, fallback = "Listen") {
  return window.t ? window.t(key) : fallback;
}

function encodeTtsAttr(text) {
  return encodeURIComponent(String(text || "").trim());
}

function decodeTtsAttr(encoded) {
  try {
    return decodeURIComponent(encoded || "");
  } catch {
    return encoded || "";
  }
}

/** Inline 🔊 button for alert rows, risk labels, etc. */
function ttsBtn(text, label = "Listen") {
  const encoded = encodeTtsAttr(text);
  if (!encoded) return "";
  const safeLabel = String(label).replace(/"/g, "&quot;");
  return `<button type="button" class="btn-tts" data-tts-text="${encoded}" title="${safeLabel}" aria-label="${safeLabel}">🔊</button>`;
}

async function playTts(text) {
  const spoken = decodeTtsAttr(encodeTtsAttr(text));
  if (!spoken) {
    if (typeof toast === "function") toast(ttsLabel("tts.nothing_to_read", "Nothing to read aloud."), "warning");
    return;
  }

  const buttons = document.querySelectorAll(".btn-tts.playing");
  buttons.forEach((b) => b.classList.remove("playing"));

  try {
    if (currentTtsAudio) {
      currentTtsAudio.pause();
      currentTtsAudio = null;
    }

    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: spoken, lang: ttsLang() }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Speech generation failed");
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    currentTtsAudio = new Audio(url);
    currentTtsAudio.onended = () => {
      URL.revokeObjectURL(url);
      document.querySelectorAll(".btn-tts.playing").forEach((b) => b.classList.remove("playing"));
    };
    await currentTtsAudio.play();
  } catch (err) {
    if (typeof toast === "function") {
      toast(ttsLabel("tts.speech_error", "Speech error: {msg}").replace("{msg}", err.message), "error");
    }
    console.warn("TTS error:", err);
  }
}

function bindTtsDelegation() {
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".btn-tts");
    if (!btn || btn.disabled) return;
    event.preventDefault();
    event.stopPropagation();

    document.querySelectorAll(".btn-tts.playing").forEach((b) => b.classList.remove("playing"));
    btn.classList.add("playing");

    const text = decodeTtsAttr(btn.dataset.ttsText || "");
    playTts(text);
  });
}

function collectAdvisorySpeech(bundle) {
  if (!bundle) return ttsLabel("tts.no_advisory", "No advisory data available.");
  const parts = [];
  (bundle.advisories || []).forEach((a) => {
    parts.push(`${a.title}. ${a.detail}`);
  });
  const irr = bundle.irrigation || {};
  if (irr.message) parts.push(`${ttsLabel("tts.smart_irrigation", "Smart irrigation.")} ${irr.message}`);
  const risks = bundle.environmental_risks || {};
  if (risks.yield_risk_pct != null) {
    const regime = risks.predicted_regime
      ? ttsLabel("tts.predicted_regime", " Predicted regime {regime}.").replace("{regime}", risks.predicted_regime)
      : "";
    const source = risks.prediction_source === "ml"
      ? ttsLabel("tts.ml_model", " Machine learning model.")
      : "";
    parts.push(
      ttsLabel("tts.overall_yield_risk", "Overall yield risk {pct} percent. Level {level}.")
        .replace("{pct}", risks.yield_risk_pct)
        .replace("{level}", risks.overall_level_label || risks.overall_level || "unknown")
      + regime + source
    );
  }
  (risks.risks || []).forEach((r) => {
    parts.push(
      ttsLabel("tts.risk_row", "{label}. Score {score}. Level {level}.")
        .replace("{label}", r.label)
        .replace("{score}", r.score)
        .replace("{level}", r.level_label || r.level)
    );
  });
  return parts.join(" ") || ttsLabel("tts.no_alerts", "No alerts at this time.");
}

function collectVisionSpeech(v) {
  if (!v) return ttsLabel("tts.no_vision", "No vision scan results yet.");
  const parts = [
    ttsLabel("tts.field_health_score", "Field health score {score}.").replace("{score}", v.field_health_score ?? "unknown"),
    v.disease_summary || "",
    v.pest_summary || "",
    v.nutrient_summary || "",
  ];
  (v.recommendations || []).forEach((r) => parts.push(r));
  return parts.filter(Boolean).join(" ");
}

function collectPredictionSpeech(p) {
  if (!p) return ttsLabel("tts.no_prediction", "No prediction yet. Run predict to get a crop recommendation.");
  const parts = [
    ttsLabel("tts.recommended_crop", "Recommended crop {crop}.").replace("{crop}", p.recommended_crop),
    ttsLabel("tts.confidence_pct", "Confidence {pct} percent.").replace("{pct}", p.confidence_pct),
    ttsLabel("tts.growth_period", "Growth period {months} months.").replace("{months}", p.growth_months),
  ];
  if (p.user_crop) {
    parts.push(ttsLabel("tts.preferred_was", "Your preferred crop was {crop}.").replace("{crop}", p.user_crop));
  }
  if (p.explanation) parts.push(p.explanation);
  (p.alerts || []).forEach((a) => parts.push(a.msg));
  if (p.prediction_text && !p.explanation) {
    parts.push(ttsLabel("tts.your_note", "Your note: {text}").replace("{text}", p.prediction_text));
  }
  return parts.join(" ");
}

window.ttsBtn = ttsBtn;
window.playTts = playTts;
window.bindTtsDelegation = bindTtsDelegation;
window.collectAdvisorySpeech = collectAdvisorySpeech;
window.collectVisionSpeech = collectVisionSpeech;
window.collectPredictionSpeech = collectPredictionSpeech;

document.addEventListener("DOMContentLoaded", bindTtsDelegation);
