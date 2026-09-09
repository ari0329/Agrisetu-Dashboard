"""
AgriSetu Farm Risk ML Predictor
Loads farm_risk_model.pkl (IsolationForest + KMeans) and returns
model-derived yield risk, regime, and per-risk scores.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from config import Config

logger = logging.getLogger(__name__)

_bundle: Optional[dict] = None
_load_error: Optional[str] = None
_ref_decisions: Optional[np.ndarray] = None

FEATURE_MAP = {
    "Soil_Moisture_%": "soil_moisture",
    "Soil_Temperature_C": "soil_temperature",
    "Rainfall_ml": "rainfall",
    "Air_Temperature_C": "air_temperature",
    "Humidity_%": "humidity",
}

DEFAULTS = {
    "soil_moisture": 50.0,
    "soil_temperature": 25.0,
    "rainfall": 0.0,
    "air_temperature": 28.0,
    "humidity": 60.0,
}


def _level(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


def is_model_available() -> bool:
    return _load_bundle() is not None


def model_load_error() -> Optional[str]:
    _load_bundle()
    return _load_error


def _load_bundle() -> Optional[dict]:
    global _bundle, _load_error, _ref_decisions
    if _bundle is not None:
        return _bundle
    if _load_error is not None:
        return None
    if not Config.FARM_RISK_MODEL_PATH.is_file():
        _load_error = f"Missing {Config.FARM_RISK_MODEL_PATH.name}"
        logger.warning(_load_error)
        return None
    try:
        import joblib

        _bundle = joblib.load(Config.FARM_RISK_MODEL_PATH)
        required = ("scaler", "kmeans", "isoforest", "regime_names", "percentile_ref", "features")
        missing = [k for k in required if k not in _bundle]
        if missing:
            raise ValueError(f"farm_risk_model.pkl missing keys: {', '.join(missing)}")

        features = _bundle["features"]
        ref = _bundle["percentile_ref"]
        X = np.column_stack([ref[f] for f in features])
        X_scaled = _bundle["scaler"].transform(X)
        _ref_decisions = _bundle["isoforest"].decision_function(X_scaled)
        logger.info("Farm risk ML model loaded")
        return _bundle
    except Exception as exc:
        _load_error = str(exc)
        logger.warning(f"Farm risk model unavailable: {exc}")
        return None


def _sensor_value(sensor_data: dict, feature_col: str) -> float:
    key = FEATURE_MAP[feature_col]
    raw = sensor_data.get(key)
    if raw is None:
        if key == "air_temperature":
            soil_t = sensor_data.get("soil_temperature")
            if soil_t is not None:
                return float(soil_t) + 1.5
        return DEFAULTS[key]
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULTS[key]


def _feature_vector(sensor_data: dict, features: List[str]) -> np.ndarray:
    return np.array([[_sensor_value(sensor_data, f) for f in features]])


def _feature_percentile(feature_col: str, value: float, percentile_ref: dict) -> float:
    ref = percentile_ref[feature_col]
    return float(100.0 * (ref < value).mean())


def _anomaly_to_risk_pct(decision: float, ref_decisions: np.ndarray) -> int:
    lo, hi = float(ref_decisions.min()), float(ref_decisions.max())
    if hi <= lo:
        return 50
    pct = 100.0 * (hi - decision) / (hi - lo)
    return int(min(100, max(0, round(pct))))


def _component_risks(
    sensor_data: dict,
    percentile_ref: dict,
) -> List[Dict[str, Any]]:
    moisture = _sensor_value(sensor_data, "Soil_Moisture_%")
    rainfall = _sensor_value(sensor_data, "Rainfall_ml")
    soil_t = _sensor_value(sensor_data, "Soil_Temperature_C")
    air_t = _sensor_value(sensor_data, "Air_Temperature_C")
    humidity = _sensor_value(sensor_data, "Humidity_%")
    water = sensor_data.get("water_level")
    try:
        water = float(water) if water is not None else 50.0
    except (TypeError, ValueError):
        water = 50.0

    moisture_pct = _feature_percentile("Soil_Moisture_%", moisture, percentile_ref)
    rainfall_pct = _feature_percentile("Rainfall_ml", rainfall, percentile_ref)
    soil_t_pct = _feature_percentile("Soil_Temperature_C", soil_t, percentile_ref)
    air_t_pct = _feature_percentile("Air_Temperature_C", air_t, percentile_ref)
    humidity_pct = _feature_percentile("Humidity_%", humidity, percentile_ref)

    drought = int(min(100, max(0, round(100 - moisture_pct + max(0, 25 - water) * 0.4))))
    flood = int(min(100, max(0, round((rainfall_pct + moisture_pct) / 2))))
    heat = int(min(100, max(0, round((air_t_pct + soil_t_pct) / 2))))
    if 20 <= air_t <= 34 and humidity_pct >= 55:
        disease_climate = int(min(100, round(humidity_pct * 0.65 + air_t_pct * 0.35)))
    else:
        disease_climate = int(min(100, max(0, round(humidity_pct * 0.25))))

    return [
        {
            "id": "drought",
            "label": "Drought / Water Stress",
            "score": drought,
            "level": _level(drought),
            "advice": "Mulch soil, irrigate in early morning, reduce plant density if prolonged.",
            "ml_percentile": round(100 - moisture_pct, 1),
        },
        {
            "id": "flood",
            "label": "Flood / Excess Rainfall",
            "score": flood,
            "level": _level(flood),
            "advice": "Improve drainage channels; avoid fertilizer until soil drains.",
            "ml_percentile": round((rainfall_pct + moisture_pct) / 2, 1),
        },
        {
            "id": "heat",
            "label": "Heat Stress",
            "score": heat,
            "level": _level(heat),
            "advice": "Provide shade nets, irrigate lightly at dusk, avoid midday spraying.",
            "ml_percentile": round((air_t_pct + soil_t_pct) / 2, 1),
        },
        {
            "id": "disease_climate",
            "label": "Disease Outbreak Climate",
            "score": disease_climate,
            "level": _level(disease_climate),
            "advice": "Scout leaves daily; improve airflow; prepare preventive fungicide if needed.",
            "ml_percentile": round(humidity_pct, 1),
        },
    ]


def predict_farm_risk(sensor_data: dict) -> Dict[str, Any]:
    """
    Run farm_risk_model.pkl on live sensor readings.
    Returns environmental_risks-shaped dict with ML predictions.
    """
    bundle = _load_bundle()
    if bundle is None or _ref_decisions is None:
        raise RuntimeError(_load_error or "Farm risk model not loaded")

    features = bundle["features"]
    scaler = bundle["scaler"]
    kmeans = bundle["kmeans"]
    isoforest = bundle["isoforest"]
    regime_names = bundle["regime_names"]
    percentile_ref = bundle["percentile_ref"]

    values = {FEATURE_MAP[f]: _sensor_value(sensor_data, f) for f in features}
    row = _feature_vector(sensor_data, features)
    scaled = scaler.transform(row)
    cluster_id = int(kmeans.predict(scaled)[0])
    decision = float(isoforest.decision_function(scaled)[0])
    sample_score = float(isoforest.score_samples(scaled)[0])

    yield_risk_pct = _anomaly_to_risk_pct(decision, _ref_decisions)
    predicted_regime = regime_names.get(cluster_id, f"Cluster {cluster_id}")
    risks = _component_risks(sensor_data, percentile_ref)
    overall = max(r["score"] for r in risks)
    active = [r for r in risks if r["score"] >= 30]
    active.sort(key=lambda x: x["score"], reverse=True)

    feature_percentiles = {
        FEATURE_MAP[f]: round(_feature_percentile(f, values[FEATURE_MAP[f]], percentile_ref), 1)
        for f in features
    }

    return {
        "overall_score": overall,
        "overall_level": _level(yield_risk_pct),
        "risks": risks,
        "active_risks": active,
        "yield_risk_pct": yield_risk_pct,
        "predicted_regime": predicted_regime,
        "cluster_id": cluster_id,
        "anomaly_decision": round(decision, 4),
        "anomaly_score": round(sample_score, 4),
        "model_used": "farm_risk_model",
        "prediction_source": "ml",
        "feature_values": {k: round(v, 2) for k, v in values.items()},
        "feature_percentiles": feature_percentiles,
        "timestamp": datetime.now().isoformat(),
    }
