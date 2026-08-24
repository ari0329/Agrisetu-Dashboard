"""
AgriSetu Farm Analytics Store
Persists sensor snapshots, advisories, and vision results for:
  - Historical trends
  - Field-level performance
  - Yield-risk forecasting charts

Uses JSON file locally; optionally mirrors latest summary to Upstash Redis.
Supports multiple field_id values for scalable multi-plot deployments.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.Lock()
_DATA_DIR = Path(__file__).parent / "data"
_HISTORY_FILE = _DATA_DIR / "farm_history.json"
_MAX_POINTS = 500


def _ensure():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _HISTORY_FILE.exists():
        _HISTORY_FILE.write_text(json.dumps({"fields": {}}, indent=2), encoding="utf-8")


def _load() -> dict:
    _ensure()
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"fields": {}}


def _save(db: dict) -> None:
    _ensure()
    tmp = _HISTORY_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    tmp.replace(_HISTORY_FILE)


def append_snapshot(
    sensor_data: dict,
    advisory: Optional[dict] = None,
    vision: Optional[dict] = None,
    field_id: str = "field-1",
    prediction: Optional[dict] = None,
) -> dict:
    """Append one analytics point for a field."""
    point = {
        "timestamp": datetime.now().isoformat(),
        "soil_moisture": sensor_data.get("soil_moisture"),
        "soil_temperature": sensor_data.get("soil_temperature"),
        "water_level": sensor_data.get("water_level"),
        "air_temperature": sensor_data.get("air_temperature"),
        "humidity": sensor_data.get("humidity"),
        "rainfall": sensor_data.get("rainfall"),
        "ph": sensor_data.get("ph"),
        "yield_risk_pct": (
            (advisory or {}).get("environmental_risks", {}).get("yield_risk_pct")
        ),
        "irrigation_action": (advisory or {}).get("irrigation", {}).get("action"),
        "field_health_score": (vision or {}).get("field_health_score"),
        "disease_detected": (vision or {}).get("disease_detected"),
        "pest_detected": (vision or {}).get("pest_detected"),
        "recommended_crop": (prediction or {}).get("recommended_crop"),
    }

    with _LOCK:
        db = _load()
        fields = db.setdefault("fields", {})
        series = fields.setdefault(field_id, [])
        series.append(point)
        if len(series) > _MAX_POINTS:
            fields[field_id] = series[-_MAX_POINTS:]
        _save(db)

    return point


def get_history(field_id: str = "field-1", limit: int = 50) -> List[dict]:
    with _LOCK:
        db = _load()
        series = db.get("fields", {}).get(field_id, [])
    return series[-limit:]


def list_fields() -> List[str]:
    with _LOCK:
        db = _load()
        return sorted(db.get("fields", {}).keys()) or ["field-1"]


def get_analytics_summary(field_id: str = "field-1") -> Dict[str, Any]:
    history = get_history(field_id, limit=100)
    if not history:
        return {
            "field_id": field_id,
            "points": 0,
            "message": "No history yet — connect sensors or run advisory to start logging.",
            "avg_moisture": None,
            "avg_yield_risk": None,
            "disease_events": 0,
            "pest_events": 0,
            "irrigation_irrigate_now_count": 0,
            "trend": [],
        }

    moistures = [p["soil_moisture"] for p in history if p.get("soil_moisture") is not None]
    risks = [p["yield_risk_pct"] for p in history if p.get("yield_risk_pct") is not None]
    disease_events = sum(1 for p in history if p.get("disease_detected"))
    pest_events = sum(1 for p in history if p.get("pest_detected"))
    irrigate_now = sum(1 for p in history if p.get("irrigation_action") == "irrigate_now")

    # Compact trend for charts (last 24 points)
    trend = []
    for p in history[-24:]:
        trend.append({
            "t": p["timestamp"][11:16] if p.get("timestamp") else "",
            "moisture": p.get("soil_moisture"),
            "yield_risk": p.get("yield_risk_pct"),
            "health": p.get("field_health_score"),
        })

    return {
        "field_id": field_id,
        "points": len(history),
        "avg_moisture": round(sum(moistures) / len(moistures), 1) if moistures else None,
        "avg_yield_risk": round(sum(risks) / len(risks), 1) if risks else None,
        "latest_yield_risk": risks[-1] if risks else None,
        "disease_events": disease_events,
        "pest_events": pest_events,
        "irrigation_irrigate_now_count": irrigate_now,
        "trend": trend,
        "fields": list_fields(),
    }
