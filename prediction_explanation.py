"""
Build farmer-facing explanations that compare the user's note and preferred crop
against live sensor data and the ML recommendation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

CROP_THRESHOLDS = {
    "wheat":     {"moisture": (30, 60),  "temp": (15, 25), "rain_need": "low"},
    "rice":      {"moisture": (60, 90),  "temp": (25, 35), "rain_need": "high"},
    "maize":     {"moisture": (40, 70),  "temp": (20, 30), "rain_need": "moderate"},
    "cotton":    {"moisture": (35, 65),  "temp": (25, 35), "rain_need": "moderate"},
    "soybean":   {"moisture": (45, 75),  "temp": (20, 30), "rain_need": "moderate"},
    "potato":    {"moisture": (50, 80),  "temp": (15, 25), "rain_need": "moderate"},
    "tomato":    {"moisture": (55, 80),  "temp": (20, 30), "rain_need": "moderate"},
    "sugarcane": {"moisture": (65, 90),  "temp": (25, 38), "rain_need": "high"},
    "sunflower": {"moisture": (35, 65),  "temp": (20, 32), "rain_need": "low"},
    "barley":    {"moisture": (30, 55),  "temp": (12, 22), "rain_need": "low"},
}


def _g(data: dict, key: str, default: float) -> float:
    v = data.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_note_intent(note: str) -> Dict[str, bool]:
    text = (note or "").lower().strip()
    if not text:
        return {"expects_rain": False, "expects_dry": False, "expects_heat": False, "expects_cold": False}

    rain_words = ("rain", "rainfall", "monsoon", "wet", "shower", "downpour")
    dry_words = ("dry", "drought", "no rain", "low moisture", "water stress", "arid")
    heat_words = ("heat", "hot", "high temp", "scorching", "summer")
    cold_words = ("cold", "winter", "frost", "cool")

    expects_rain = any(w in text for w in rain_words)
    expects_dry = any(w in text for w in dry_words)
    expects_heat = any(w in text for w in heat_words)
    expects_cold = any(w in text for w in cold_words)

    if "heavy rain" in text or "high rain" in text or "lots of rain" in text:
        expects_rain = True
        expects_dry = False

    return {
        "expects_rain": expects_rain,
        "expects_dry": expects_dry,
        "expects_heat": expects_heat,
        "expects_cold": expects_cold,
    }


def _crop_fit(sensor_data: dict, crop_name: str) -> Tuple[int, List[str]]:
    crop_key = (crop_name or "").strip().lower()
    if crop_key not in CROP_THRESHOLDS:
        return 50, [f"Limited agronomic data for {crop_name or 'this crop'} — review field conditions manually."]

    th = CROP_THRESHOLDS[crop_key]
    moisture = _g(sensor_data, "soil_moisture", 50)
    temp = _g(sensor_data, "soil_temperature", 25)
    display = crop_key.title()
    reasons: List[str] = []
    scores: List[float] = []

    m_lo, m_hi = th["moisture"]
    if m_lo <= moisture <= m_hi:
        scores.append(1.0)
        reasons.append(
            f"{display} suits current soil moisture ({moisture:.1f}% is within the ideal {m_lo}–{m_hi}% range)."
        )
    elif moisture < m_lo:
        scores.append(max(0.0, 1 - (m_lo - moisture) / max(m_lo, 1)))
        reasons.append(
            f"{display} needs more moisture ({m_lo}–{m_hi}%); current reading is only {moisture:.1f}% — water stress is likely."
        )
    else:
        scores.append(max(0.0, 1 - (moisture - m_hi) / max(100 - m_hi, 1)))
        reasons.append(
            f"{display} prefers drier soil ({m_lo}–{m_hi}%); current moisture {moisture:.1f}% is too high — rot or disease risk rises."
        )

    t_lo, t_hi = th["temp"]
    if t_lo <= temp <= t_hi:
        scores.append(1.0)
        reasons.append(
            f"Soil temperature ({temp:.1f}°C) is within the {t_lo}–{t_hi}°C comfort zone for {display}."
        )
    elif temp < t_lo:
        scores.append(max(0.0, 1 - (t_lo - temp) / max(t_lo, 1)))
        reasons.append(
            f"Soil is too cool for {display} ({t_lo}–{t_hi}°C ideal); current {temp:.1f}°C may slow germination."
        )
    else:
        scores.append(max(0.0, 1 - (temp - t_hi) / max(t_hi, 1)))
        reasons.append(
            f"Soil is too warm for {display} ({t_lo}–{t_hi}°C ideal); current {temp:.1f}°C raises heat-stress risk."
        )

    return int(round(sum(scores) / len(scores) * 100)), reasons


def _note_vs_sensors(note: str, sensor_data: dict) -> List[str]:
    intent = _parse_note_intent(note)
    if not any(intent.values()):
        return []

    moisture = _g(sensor_data, "soil_moisture", 50)
    rainfall = _g(sensor_data, "rainfall", 0)
    air_t = _g(sensor_data, "air_temperature", _g(sensor_data, "soil_temperature", 25) + 1.5)
    lines: List[str] = []

    if intent["expects_rain"]:
        if rainfall < 15 and moisture < 40:
            lines.append(
                f"Your note mentions rainfall, but live sensors show dry field conditions "
                f"(rainfall {rainfall:.0f} mm, soil moisture {moisture:.1f}%) — heavy rain is unlikely right now."
            )
        elif rainfall >= 30 or moisture >= 70:
            lines.append(
                f"Your note about rainfall aligns with sensors (rainfall {rainfall:.0f} mm, moisture {moisture:.1f}%)."
            )
        else:
            lines.append(
                f"Your note expects rain, but sensors show only moderate moisture ({moisture:.1f}%) "
                f"and limited rainfall ({rainfall:.0f} mm) — a sustained wet spell is not confirmed yet."
            )

    if intent["expects_dry"]:
        if moisture >= 60:
            lines.append(
                f"You noted dry conditions, but soil moisture is still relatively high ({moisture:.1f}%) — drought stress is not severe yet."
            )
        elif moisture < 35:
            lines.append(
                f"Your dry-condition note matches sensors: soil moisture is low ({moisture:.1f}%)."
            )

    if intent["expects_heat"] and air_t >= 34:
        lines.append(f"Your heat concern matches air temperature ({air_t:.1f}°C) — plan shade and evening irrigation.")
    elif intent["expects_heat"] and air_t < 30:
        lines.append(
            f"You mentioned heat, but air temperature ({air_t:.1f}°C) is moderate — heat stress is not the main limiting factor today."
        )

    if intent["expects_cold"] and _g(sensor_data, "soil_temperature", 25) < 18:
        lines.append("Cool conditions you noted are reflected in current soil temperature readings.")

    return lines


def _rain_crop_advice(crop_key: str, sensor_data: dict) -> Optional[str]:
    if crop_key not in CROP_THRESHOLDS:
        return None
    rain_need = CROP_THRESHOLDS[crop_key]["rain_need"]
    moisture = _g(sensor_data, "soil_moisture", 50)
    rainfall = _g(sensor_data, "rainfall", 0)
    display = crop_key.title()

    if rain_need == "high" and moisture < 45 and rainfall < 20:
        return f"{display} depends on wet conditions; current dryness makes it a poor match."
    if rain_need == "low" and (moisture > 80 or rainfall > 80):
        return f"{display} tolerates drier spells better, but current excess moisture favours other crops."
    return None


def build_prediction_explanation(
    sensor_data: dict,
    recommended_crop: str,
    user_crop: str = "",
    prediction_text: str = "",
) -> Dict[str, Any]:
    """
    Compare user note + preferred crop with sensors and ML recommendation.
    Returns short UI text and a longer PDF-ready explanation.
    """
    note = (prediction_text or "").strip()
    preferred = (user_crop or "").strip()
    recommended = (recommended_crop or "").strip().title()
    preferred_display = preferred.title() if preferred else ""

    rec_score, rec_reasons = _crop_fit(sensor_data, recommended)
    pref_score, pref_reasons = (0, [])
    if preferred:
        pref_score, pref_reasons = _crop_fit(sensor_data, preferred)

    note_lines = _note_vs_sensors(note, sensor_data)
    paragraphs: List[str] = []
    summary_parts: List[str] = []

    if note:
        paragraphs.append(f'<b>Your note:</b> "{note}"')
        summary_parts.append(f'You wrote: "{note}".')

    if preferred_display:
        paragraphs.append(f'<b>Your preferred crop:</b> {preferred_display} (suitability score {pref_score}%)')
        summary_parts.append(f"You preferred {preferred_display}.")

    paragraphs.append(
        f'<b>AI recommendation:</b> {recommended} (suitability score {rec_score}%)'
    )

    if note_lines:
        paragraphs.extend(note_lines)
        summary_parts.append(note_lines[0])

    if preferred_display and preferred.lower() != recommended.lower():
        if pref_score < 55:
            rain_note = _rain_crop_advice(preferred.lower(), sensor_data)
            verdict = (
                f"{preferred_display} is <b>not well suited</b> to current field conditions "
                f"(score {pref_score}%). {pref_reasons[0] if pref_reasons else ''}"
            )
            if rain_note:
                verdict += f" {rain_note}"
            verdict += (
                f" It will be wiser to farm <b>{recommended}</b>, which better matches today's sensors "
                f"(score {rec_score}%)."
            )
            paragraphs.append(verdict)
            summary_parts.append(
                re.sub(r"<[^>]+>", "", verdict.replace("</b>", "").replace("<b>", ""))
            )
        elif pref_score >= rec_score - 10:
            paragraphs.append(
                f"{preferred_display} could work (score {pref_score}%), but <b>{recommended}</b> "
                f"still scores higher ({rec_score}%) for current moisture and temperature."
            )
            summary_parts.append(
                f"{preferred_display} is acceptable, yet {recommended} is the stronger match today."
            )
        else:
            paragraphs.append(
                f"Although {preferred_display} is viable (score {pref_score}%), "
                f"<b>{recommended}</b> is the safer choice (score {rec_score}%)."
            )
            summary_parts.append(
                f"{recommended} is recommended over {preferred_display} for current conditions."
            )
    elif preferred_display and preferred.lower() == recommended.lower():
        paragraphs.append(
            f"Your preferred crop <b>{preferred_display}</b> matches the AI recommendation — "
            f"current sensors support this choice (score {rec_score}%)."
        )
        summary_parts.append(f"{preferred_display} aligns with the AI recommendation.")
    elif not preferred_display and note:
        paragraphs.append(
            f"Based on your note and live sensors, <b>{recommended}</b> is the most appropriate crop "
            f"for these conditions (score {rec_score}%). {rec_reasons[0] if rec_reasons else ''}"
        )
        summary_parts.append(f"{recommended} fits your note and current sensor readings.")
    elif not preferred_display and not note:
        paragraphs.append(
            f"<b>{recommended}</b> is recommended from sensor data alone (score {rec_score}%). "
            f"{rec_reasons[0] if rec_reasons else ''}"
        )
        summary_parts.append(f"{recommended} is recommended from current sensor data.")

    detailed_sections = {
        "user_note": note,
        "preferred_crop": preferred_display or None,
        "recommended_crop": recommended,
        "preferred_crop_score": pref_score if preferred else None,
        "recommended_crop_score": rec_score,
        "preferred_crop_reasons": pref_reasons,
        "recommended_crop_reasons": rec_reasons,
        "note_sensor_alignment": note_lines,
    }

    if recommended.lower() not in " ".join(summary_parts).lower():
        summary_parts.append(f"{recommended} is recommended for current field conditions.")

    explanation_short = " ".join(summary_parts[:4]).strip()
    if len(explanation_short) > 420:
        explanation_short = explanation_short[:417] + "..."

    return {
        "explanation": explanation_short,
        "explanation_html": "<br/>".join(paragraphs),
        "explanation_detailed": paragraphs,
        "explanation_sections": detailed_sections,
        "preferred_crop_suitable": pref_score >= 55 if preferred else None,
        "preferred_crop_score": pref_score if preferred else None,
    }
