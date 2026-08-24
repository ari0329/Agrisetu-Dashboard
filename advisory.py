"""
AgriSetu Farmer Advisory Engine
Irrigation scheduling, environmental risk scoring, and actionable alerts
aligned with Smart Farming Assistant requirements for Indian field conditions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def _g(data: dict, key: str, default: float) -> float:
    v = data.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def assess_irrigation(sensor_data: dict) -> Dict[str, Any]:
    """Smart irrigation recommendation from soil moisture, water level, rainfall."""
    moisture = _g(sensor_data, "soil_moisture", 50)
    water    = _g(sensor_data, "water_level", 50)
    rainfall = _g(sensor_data, "rainfall", 0)
    soil_t   = _g(sensor_data, "soil_temperature", 25)
    air_t    = _g(sensor_data, "air_temperature", soil_t + 1.5)
    humidity = _g(sensor_data, "humidity", 60)

    # Evapotranspiration proxy (higher heat + lower humidity → more water need)
    et_proxy = max(0.0, (air_t - 20) * 0.08 + (100 - humidity) * 0.02)

    if rainfall > 40:
        action = "delay_irrigation"
        urgency = "low"
        message = "Irrigate later — recent/expected rainfall is sufficient."
        litres_hint = 0
    elif moisture < 25:
        action = "irrigate_now"
        urgency = "critical"
        message = "Irrigate now — severe water stress detected."
        litres_hint = round(18 + et_proxy * 4, 1)
    elif moisture < 35:
        action = "irrigate_now"
        urgency = "high"
        message = "Irrigate soon — soil moisture below crop comfort zone."
        litres_hint = round(12 + et_proxy * 3, 1)
    elif moisture > 85:
        action = "stop_irrigation"
        urgency = "high"
        message = "Stop irrigation — over-watering / waterlogging risk."
        litres_hint = 0
    elif moisture > 75:
        action = "delay_irrigation"
        urgency = "low"
        message = "Delay irrigation — soil is already well hydrated."
        litres_hint = 0
    else:
        action = "monitor"
        urgency = "normal"
        message = "Moisture is adequate — maintain scheduled light irrigation."
        litres_hint = round(4 + et_proxy * 1.5, 1)

    if water < 20 and action == "irrigate_now":
        message += " Reservoir critically low — top up water source first."
        urgency = "critical"

    # Next check window (hours)
    next_check_h = {
        "irrigate_now": 6,
        "stop_irrigation": 12,
        "delay_irrigation": 24,
        "monitor": 12,
    }.get(action, 12)

    return {
        "action": action,
        "urgency": urgency,
        "message": message,
        "suggested_litres_per_m2": litres_hint,
        "next_check_hours": next_check_h,
        "et_proxy": round(et_proxy, 2),
        "soil_moisture": moisture,
        "water_level": water,
    }


def assess_environmental_risks(sensor_data: dict) -> Dict[str, Any]:
    """
    Localized field risks: drought, flood, heat stress, disease-conducive climate.
    Scores 0–100 (higher = more severe).
    """
    moisture = _g(sensor_data, "soil_moisture", 50)
    water    = _g(sensor_data, "water_level", 50)
    rainfall = _g(sensor_data, "rainfall", 0)
    soil_t   = _g(sensor_data, "soil_temperature", 25)
    air_t    = _g(sensor_data, "air_temperature", soil_t + 1.5)
    humidity = _g(sensor_data, "humidity", 60)

    drought = 0
    if moisture < 20:
        drought = 90
    elif moisture < 30:
        drought = 70
    elif moisture < 40:
        drought = 45
    elif moisture < 50 and rainfall < 5:
        drought = 25
    if water < 25:
        drought = min(100, drought + 15)

    flood = 0
    if rainfall > 120 or moisture > 92:
        flood = 85
    elif rainfall > 60 or moisture > 85:
        flood = 55
    elif rainfall > 30 and moisture > 75:
        flood = 30

    heat = 0
    if air_t >= 42:
        heat = 95
    elif air_t >= 38:
        heat = 75
    elif air_t >= 36:
        heat = 55
    elif air_t >= 34:
        heat = 30

    # High humidity + warm nights favour fungal disease outbreaks
    disease_climate = 0
    if humidity >= 85 and 22 <= air_t <= 32:
        disease_climate = 80
    elif humidity >= 75 and 20 <= air_t <= 34:
        disease_climate = 55
    elif humidity >= 70 and air_t >= 28:
        disease_climate = 35

    risks = [
        {
            "id": "drought",
            "label": "Drought / Water Stress",
            "score": drought,
            "level": _level(drought),
            "advice": "Mulch soil, irrigate in early morning, reduce plant density if prolonged.",
        },
        {
            "id": "flood",
            "label": "Flood / Excess Rainfall",
            "score": flood,
            "level": _level(flood),
            "advice": "Improve drainage channels; avoid fertilizer until soil drains.",
        },
        {
            "id": "heat",
            "label": "Heat Stress",
            "score": heat,
            "level": _level(heat),
            "advice": "Provide shade nets, irrigate lightly at dusk, avoid midday spraying.",
        },
        {
            "id": "disease_climate",
            "label": "Disease Outbreak Climate",
            "score": disease_climate,
            "level": _level(disease_climate),
            "advice": "Scout leaves daily; improve airflow; prepare preventive fungicide if needed.",
        },
    ]

    overall = max(r["score"] for r in risks)
    active  = [r for r in risks if r["score"] >= 30]
    active.sort(key=lambda x: x["score"], reverse=True)

    return {
        "overall_score": overall,
        "overall_level": _level(overall),
        "risks": risks,
        "active_risks": active,
        "yield_risk_pct": min(95, int(overall * 0.85 + (100 - moisture) * 0.1)),
        "timestamp": datetime.now().isoformat(),
    }


def assess_nutrient_from_ph(sensor_data: dict) -> Dict[str, Any]:
    """Heuristic nutrient / pH advisory (no NPK sensor — uses pH + growth proxies)."""
    ph = sensor_data.get("ph")
    moisture = _g(sensor_data, "soil_moisture", 50)

    if ph is None:
        return {
            "status": "unknown",
            "message": "Soil pH sensor not available — consider manual soil test (NPK kit).",
            "deficiencies": [],
            "actions": ["Collect soil sample for NPK and pH lab / kit test."],
        }

    ph = float(ph)
    deficiencies: List[str] = []
    actions: List[str] = []

    if ph < 5.5:
        status = "acidic"
        deficiencies = ["Phosphorus lock-up", "Calcium / Magnesium likely low"]
        actions = [
            "Apply agricultural lime (2–4 kg / 100 m²) after soil test.",
            "Avoid excess ammonium fertilizers until pH rises.",
        ]
    elif ph > 7.8:
        status = "alkaline"
        deficiencies = ["Iron deficiency risk", "Zinc / Manganese availability low"]
        actions = [
            "Use organic compost and acidifying fertilizers (e.g. ammonium sulphate).",
            "Foliar Fe/Zn spray if yellowing between leaf veins appears.",
        ]
    elif ph < 6.0:
        status = "slightly_acidic"
        deficiencies = ["Possible low calcium"]
        actions = ["Monitor for tip burn; light lime if crop is sensitive."]
    elif ph > 7.2:
        status = "slightly_alkaline"
        deficiencies = ["Possible micronutrient stress"]
        actions = ["Add compost; watch for interveinal chlorosis."]
    else:
        status = "optimal"
        deficiencies = []
        actions = ["pH in good range — balance NPK based on crop stage."]

    if moisture < 30:
        actions.append("Correct moisture before fertilizing — dry soil wastes nutrients.")

    return {
        "status": status,
        "ph": ph,
        "message": f"Soil pH is {ph:.1f} ({status.replace('_', ' ')}).",
        "deficiencies": deficiencies,
        "actions": actions,
    }


def build_farmer_advisories(
    sensor_data: dict,
    vision: Optional[dict] = None,
) -> List[Dict[str, Any]]:
    """
    Simple farmer-facing advisories matching problem statement examples:
    Irrigate now / delay, disease, pest, heat, flood.
    """
    advisories: List[Dict[str, Any]] = []
    irrigation = assess_irrigation(sensor_data)
    risks = assess_environmental_risks(sensor_data)
    nutrient = assess_nutrient_from_ph(sensor_data)

    action_map = {
        "irrigate_now": ("Irrigate now", "warning"),
        "delay_irrigation": ("Delay irrigation", "info"),
        "stop_irrigation": ("Stop irrigation — over-watering risk", "danger"),
        "monitor": ("Moisture OK — stick to light schedule", "success"),
    }
    title, severity = action_map.get(irrigation["action"], ("Check irrigation", "info"))
    advisories.append({
        "category": "irrigation",
        "title": title,
        "severity": severity,
        "detail": irrigation["message"],
        "action_code": irrigation["action"],
    })

    for r in risks["active_risks"]:
        if r["id"] == "heat" and r["score"] >= 40:
            advisories.append({
                "category": "environment",
                "title": "Heat-stress warning",
                "severity": "danger" if r["score"] >= 70 else "warning",
                "detail": r["advice"],
                "action_code": "heat_stress",
            })
        elif r["id"] == "flood" and r["score"] >= 40:
            advisories.append({
                "category": "environment",
                "title": "Flood-risk alert",
                "severity": "danger" if r["score"] >= 70 else "warning",
                "detail": r["advice"],
                "action_code": "flood_risk",
            })
        elif r["id"] == "drought" and r["score"] >= 50:
            advisories.append({
                "category": "environment",
                "title": "Drought stress rising",
                "severity": "warning",
                "detail": r["advice"],
                "action_code": "drought",
            })
        elif r["id"] == "disease_climate" and r["score"] >= 50:
            advisories.append({
                "category": "crop_health",
                "title": "Disease-favourable weather",
                "severity": "warning",
                "detail": r["advice"],
                "action_code": "disease_climate",
            })

    if nutrient["deficiencies"]:
        advisories.append({
            "category": "nutrient",
            "title": "Possible nutrient imbalance",
            "severity": "warning",
            "detail": nutrient["message"] + " " + "; ".join(nutrient["deficiencies"]),
            "action_code": "nutrient_check",
        })

    if vision:
        if vision.get("disease_detected"):
            advisories.append({
                "category": "crop_health",
                "title": "Possible disease detected",
                "severity": "danger",
                "detail": vision.get("disease_summary", "Leaf symptoms suggest disease — inspect field."),
                "action_code": "disease_detected",
            })
        if vision.get("pest_detected"):
            advisories.append({
                "category": "pest",
                "title": "Pest activity increasing",
                "severity": "warning",
                "detail": vision.get("pest_summary", "Pest-like patterns on leaf — scout and treat targeted spots."),
                "action_code": "pest_alert",
            })
        if vision.get("nutrient_flag"):
            advisories.append({
                "category": "nutrient",
                "title": "Nutrient deficiency signs on leaf",
                "severity": "warning",
                "detail": vision.get("nutrient_summary", "Leaf color suggests nutrient stress."),
                "action_code": "leaf_nutrient",
            })

    if not advisories:
        advisories.append({
            "category": "general",
            "title": "Field conditions look stable",
            "severity": "success",
            "detail": "Continue routine scouting and scheduled irrigation.",
            "action_code": "ok",
        })

    return advisories


def build_alerts(sensor_data: dict, vision: Optional[dict] = None) -> List[Dict[str, str]]:
    """Unified alerts for predict API + dashboard (extends original threshold alerts)."""
    alerts: List[Dict[str, str]] = []
    for a in build_farmer_advisories(sensor_data, vision):
        alerts.append({
            "type": a["severity"] if a["severity"] != "success" else "success",
            "msg": f"{a['title']} — {a['detail']}",
            "category": a["category"],
            "action_code": a["action_code"],
        })
    return alerts


def full_advisory_bundle(sensor_data: dict, vision: Optional[dict] = None) -> Dict[str, Any]:
    return {
        "irrigation": assess_irrigation(sensor_data),
        "environmental_risks": assess_environmental_risks(sensor_data),
        "nutrient": assess_nutrient_from_ph(sensor_data),
        "advisories": build_farmer_advisories(sensor_data, vision),
        "alerts": build_alerts(sensor_data, vision),
        "edge_mode": True,
        "timestamp": datetime.now().isoformat(),
    }


def _level(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"
