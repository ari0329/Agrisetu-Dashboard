/* AgriSetu — Text-to-Speech (gTTS via /api/tts) */

let currentTtsAudio = null;

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
    if (typeof toast === "function") toast("Nothing to read aloud.", "warning");
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
      body: JSON.stringify({ text: spoken }),
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
    if (typeof toast === "function") toast(`Speech error: ${err.message}`, "error");
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
  if (!bundle) return "No advisory data available.";
  const parts = [];
  (bundle.advisories || []).forEach((a) => {
    parts.push(`${a.title}. ${a.detail}`);
  });
  const irr = bundle.irrigation || {};
  if (irr.message) parts.push(`Smart irrigation. ${irr.message}`);
  const risks = bundle.environmental_risks || {};
  if (risks.yield_risk_pct != null) {
    parts.push(`Overall yield risk ${risks.yield_risk_pct} percent. Level ${risks.overall_level || "unknown"}.`);
  }
  (risks.risks || []).forEach((r) => {
    parts.push(`${r.label}. Score ${r.score}. Level ${r.level}.`);
  });
  return parts.join(" ") || "No alerts at this time.";
}

function collectVisionSpeech(v) {
  if (!v) return "No vision scan results yet.";
  const parts = [
    `Field health score ${v.field_health_score ?? "unknown"}.`,
    v.disease_summary || "",
    v.pest_summary || "",
    v.nutrient_summary || "",
  ];
  (v.recommendations || []).forEach((r) => parts.push(r));
  return parts.filter(Boolean).join(" ");
}

function collectPredictionSpeech(p) {
  if (!p) return "No prediction yet. Run predict to get a crop recommendation.";
  const parts = [
    `Recommended crop ${p.recommended_crop}.`,
    `Confidence ${p.confidence_pct} percent.`,
    `Growth period ${p.growth_months} months.`,
  ];
  (p.alerts || []).forEach((a) => parts.push(a.msg));
  if (p.prediction_text) parts.push(`Your note: ${p.prediction_text}`);
  return parts.join(" ");
}

window.ttsBtn = ttsBtn;
window.playTts = playTts;
window.bindTtsDelegation = bindTtsDelegation;
window.collectAdvisorySpeech = collectAdvisorySpeech;
window.collectVisionSpeech = collectVisionSpeech;
window.collectPredictionSpeech = collectPredictionSpeech;

document.addEventListener("DOMContentLoaded", bindTtsDelegation);
