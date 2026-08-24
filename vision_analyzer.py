"""
AgriSetu Edge Vision Analyzer
On-device (server-local) leaf/plant image analysis for:
  - Crop disease signs (spots, blight-like discoloration)
  - Pest damage patterns (holes / irregular dark mottling)
  - Nutrient deficiency cues (chlorosis / yellowing / purpling)

Uses Pillow color-space heuristics — runs without GPU or cloud CV APIs,
suitable for edge / intermittent-connectivity deployments.
Replace with a trained MobileNet/YOLO model later without changing the API shape.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    diff = mx - mn
    if diff == 0:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / diff) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / diff) + 120) % 360
    else:
        h = (60 * ((rf - gf) / diff) + 240) % 360
    s = 0.0 if mx == 0 else diff / mx
    v = mx
    return h, s, v


def analyze_leaf_image(image_bytes: bytes, crop_hint: str = "") -> Dict[str, Any]:
    """
    Analyze an uploaded leaf/plant photo.
    Returns structured findings usable by the advisory engine + UI.
    """
    if not PIL_OK:
        return {
            "success": False,
            "error": "Pillow not installed — run pip install Pillow",
            "edge_processed": True,
        }

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        return {"success": False, "error": f"Invalid image: {e}", "edge_processed": True}

    # Downscale for fast edge inference
    img.thumbnail((320, 320))
    pixels = list(img.getdata())
    n = max(len(pixels), 1)

    green = yellow = brown = white_ish = dark = purple = 0
    for r, g, b in pixels:
        h, s, v = _rgb_to_hsv(r, g, b)
        if v < 0.18:
            dark += 1
        elif s < 0.15 and v > 0.75:
            white_ish += 1
        elif 35 <= h <= 95 and s > 0.2 and v > 0.2:
            green += 1
        elif 20 <= h < 55 and s > 0.25 and v > 0.35:
            yellow += 1
        elif (h < 30 or h > 330) and s > 0.25 and 0.2 < v < 0.75:
            brown += 1
        elif 250 <= h <= 320 and s > 0.2:
            purple += 1

    pct = lambda c: round(100.0 * c / n, 1)
    green_pct  = pct(green)
    yellow_pct = pct(yellow)
    brown_pct  = pct(brown)
    dark_pct   = pct(dark)
    white_pct  = pct(white_ish)
    purple_pct = pct(purple)

    # ── Disease heuristics ────────────────────────────────────────────────────
    disease_score = 0.0
    disease_labels: List[str] = []
    if brown_pct > 8 and yellow_pct > 5:
        disease_score += 0.45
        disease_labels.append("Leaf blight / brown spot pattern")
    if brown_pct > 15:
        disease_score += 0.25
        disease_labels.append("Necrotic lesions")
    if white_pct > 12 and green_pct < 40:
        disease_score += 0.35
        disease_labels.append("Powdery mildew–like whitening")
    if yellow_pct > 25 and brown_pct > 5:
        disease_score += 0.2
        disease_labels.append("Chlorosis with secondary lesions")

    disease_detected = disease_score >= 0.35
    disease_conf = min(0.95, round(0.4 + disease_score * 0.5, 2))

    # ── Pest heuristics ───────────────────────────────────────────────────────
    pest_score = 0.0
    pest_labels: List[str] = []
    # Irregular dark mottling + hole-like dark spots with surrounding yellow
    if dark_pct > 10 and yellow_pct > 8:
        pest_score += 0.4
        pest_labels.append("Chewing / sucking pest damage pattern")
    if dark_pct > 18:
        pest_score += 0.25
        pest_labels.append("Dense dark mottling (possible insect frass / holes)")
    if brown_pct > 6 and dark_pct > 8 and green_pct < 55:
        pest_score += 0.2
        pest_labels.append("Scattered feeding scars")

    pest_detected = pest_score >= 0.35
    pest_conf = min(0.92, round(0.38 + pest_score * 0.5, 2))

    # ── Nutrient deficiency heuristics ────────────────────────────────────────
    nutrient_score = 0.0
    nutrient_labels: List[str] = []
    if yellow_pct > 20 and brown_pct < 8 and green_pct < 50:
        nutrient_score += 0.5
        nutrient_labels.append("General chlorosis — possible N deficiency")
    if yellow_pct > 15 and green_pct > 30 and brown_pct < 5:
        nutrient_score += 0.25
        nutrient_labels.append("Interveinal yellowing risk — Fe / Mg / Mn")
    if purple_pct > 5:
        nutrient_score += 0.35
        nutrient_labels.append("Purpling — possible P deficiency")

    nutrient_flag = nutrient_score >= 0.35
    nutrient_conf = min(0.9, round(0.35 + nutrient_score * 0.5, 2))

    # Overall field health 0–100
    health = 100.0
    health -= min(40, disease_score * 50)
    health -= min(25, pest_score * 40)
    health -= min(20, nutrient_score * 35)
    health = max(5, round(health, 1))

    growth_stage = _estimate_growth_stage(green_pct, yellow_pct, crop_hint)

    recommendations: List[str] = []
    if disease_detected:
        recommendations.append(
            "Isolate affected plants; remove badly infected leaves; consider targeted fungicide."
        )
    if pest_detected:
        recommendations.append(
            "Scout early morning for insects; prefer spot-treatment over blanket spraying."
        )
    if nutrient_flag:
        recommendations.append(
            "Confirm with soil / leaf NPK test before applying fertilizer."
        )
    if not recommendations:
        recommendations.append("Leaf appearance is mostly healthy — continue routine monitoring.")

    return {
        "success": True,
        "edge_processed": True,
        "model": "AgriSetu-Edge-ColorHeuristic-v1",
        "crop_hint": crop_hint or None,
        "image_size": list(img.size),
        "color_profile": {
            "green_pct": green_pct,
            "yellow_pct": yellow_pct,
            "brown_pct": brown_pct,
            "dark_pct": dark_pct,
            "white_pct": white_pct,
            "purple_pct": purple_pct,
        },
        "field_health_score": health,
        "growth_stage": growth_stage,
        "disease_detected": disease_detected,
        "disease_confidence": disease_conf if disease_detected else round(disease_score, 2),
        "disease_labels": disease_labels,
        "disease_summary": (
            "; ".join(disease_labels) if disease_labels
            else "No strong disease pattern in image"
        ),
        "pest_detected": pest_detected,
        "pest_confidence": pest_conf if pest_detected else round(pest_score, 2),
        "pest_labels": pest_labels,
        "pest_summary": (
            "; ".join(pest_labels) if pest_labels
            else "No strong pest-damage pattern in image"
        ),
        "nutrient_flag": nutrient_flag,
        "nutrient_confidence": nutrient_conf if nutrient_flag else round(nutrient_score, 2),
        "nutrient_labels": nutrient_labels,
        "nutrient_summary": (
            "; ".join(nutrient_labels) if nutrient_labels
            else "No strong nutrient-deficiency color pattern"
        ),
        "recommendations": recommendations,
    }


def _estimate_growth_stage(green_pct: float, yellow_pct: float, crop_hint: str) -> str:
    if green_pct > 60 and yellow_pct < 10:
        return "Vegetative / healthy canopy"
    if green_pct > 40 and yellow_pct < 20:
        return "Mid growth"
    if yellow_pct > 25:
        return "Stress / senescence signs"
    return "Uncertain — upload a clearer leaf close-up"


def analyze_demo_profile(profile: str = "healthy") -> Dict[str, Any]:
    """
    Synthetic analysis for demos when no camera image is available.
    Profiles: healthy | disease | pest | nutrient
    """
    demos = {
        "healthy": {
            "disease_detected": False,
            "pest_detected": False,
            "nutrient_flag": False,
            "field_health_score": 88.0,
            "disease_summary": "No strong disease pattern",
            "pest_summary": "No strong pest-damage pattern",
            "nutrient_summary": "No strong nutrient-deficiency color pattern",
            "recommendations": ["Leaf appearance is mostly healthy — continue routine monitoring."],
            "growth_stage": "Vegetative / healthy canopy",
            "color_profile": {
                "green_pct": 72, "yellow_pct": 8, "brown_pct": 3,
                "dark_pct": 5, "white_pct": 2, "purple_pct": 0,
            },
        },
        "disease": {
            "disease_detected": True,
            "pest_detected": False,
            "nutrient_flag": False,
            "field_health_score": 48.0,
            "disease_summary": "Leaf blight / brown spot pattern; Necrotic lesions",
            "pest_summary": "No strong pest-damage pattern",
            "nutrient_summary": "No strong nutrient-deficiency color pattern",
            "recommendations": [
                "Isolate affected plants; remove badly infected leaves; consider targeted fungicide."
            ],
            "growth_stage": "Stress / senescence signs",
            "color_profile": {
                "green_pct": 40, "yellow_pct": 22, "brown_pct": 18,
                "dark_pct": 8, "white_pct": 4, "purple_pct": 0,
            },
        },
        "pest": {
            "disease_detected": False,
            "pest_detected": True,
            "nutrient_flag": False,
            "field_health_score": 55.0,
            "disease_summary": "No strong disease pattern",
            "pest_summary": "Chewing / sucking pest damage pattern; Scattered feeding scars",
            "nutrient_summary": "No strong nutrient-deficiency color pattern",
            "recommendations": [
                "Scout early morning for insects; prefer spot-treatment over blanket spraying."
            ],
            "growth_stage": "Mid growth",
            "color_profile": {
                "green_pct": 50, "yellow_pct": 15, "brown_pct": 10,
                "dark_pct": 16, "white_pct": 2, "purple_pct": 0,
            },
        },
        "nutrient": {
            "disease_detected": False,
            "pest_detected": False,
            "nutrient_flag": True,
            "field_health_score": 62.0,
            "disease_summary": "No strong disease pattern",
            "pest_summary": "No strong pest-damage pattern",
            "nutrient_summary": "General chlorosis — possible N deficiency",
            "recommendations": [
                "Confirm with soil / leaf NPK test before applying fertilizer."
            ],
            "growth_stage": "Stress / senescence signs",
            "color_profile": {
                "green_pct": 35, "yellow_pct": 40, "brown_pct": 4,
                "dark_pct": 3, "white_pct": 5, "purple_pct": 2,
            },
        },
    }
    base = demos.get(profile, demos["healthy"])
    return {
        "success": True,
        "edge_processed": True,
        "model": "AgriSetu-Edge-DemoProfile-v1",
        "demo_profile": profile,
        **base,
        "disease_confidence": 0.78 if base["disease_detected"] else 0.12,
        "pest_confidence": 0.74 if base["pest_detected"] else 0.1,
        "nutrient_confidence": 0.71 if base["nutrient_flag"] else 0.1,
        "disease_labels": base["disease_summary"].split("; ") if base["disease_detected"] else [],
        "pest_labels": base["pest_summary"].split("; ") if base["pest_detected"] else [],
        "nutrient_labels": base["nutrient_summary"].split("; ") if base["nutrient_flag"] else [],
    }
