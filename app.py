"""
AgriSetu IoT Prediction Dashboard — Flask Backend
REST API: sensor data, ML predictions, PDF reports
No WhatsApp integration — pure web dashboard
"""

import os
import random
import logging
import traceback
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template

from config import Config
from thingesp_client import get_sensor_data

# ================== LOGGING ==================
Config.LOGS_DIR.mkdir(exist_ok=True)
log_file = Config.LOGS_DIR / f"agrisetu_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ================== FLASK ==================
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# ================== LOAD ML MODELS ==================
models_loaded = False
crop_model = label_encoder = month_model = scaler = None
month_lookup = {}

try:
    import joblib
    import pandas as pd

    crop_model    = joblib.load(Config.CROP_MODEL_PATH)
    label_encoder = joblib.load(Config.LABEL_ENCODER_PATH)
    month_lookup  = joblib.load(Config.MONTH_LOOKUP_PATH) if Config.MONTH_LOOKUP_PATH.exists() else {}

    if Config.SCALER_PATH.exists():
        scaler = joblib.load(Config.SCALER_PATH)
    if Config.MONTH_MODEL_PATH.exists():
        month_model = joblib.load(Config.MONTH_MODEL_PATH)

    models_loaded = True
    logger.info("✅ ML Models loaded")
except Exception as e:
    logger.warning(f"⚠️  Models not found — using rule-based fallback. ({e})")

FEATURE_COLUMNS = [
    "Soil_Moisture_%", "Soil_Temperature_C",
    "Rainfall_ml", "Air_Temperature_C", "Humidity_%",
]

CROP_THRESHOLDS = {
    "wheat":     {"moisture": (30, 60),  "temp": (15, 25), "rainfall": (50, 100)},
    "rice":      {"moisture": (60, 90),  "temp": (25, 35), "rainfall": (120, 200)},
    "maize":     {"moisture": (40, 70),  "temp": (20, 30), "rainfall": (80, 150)},
    "cotton":    {"moisture": (35, 65),  "temp": (25, 35), "rainfall": (60, 120)},
    "soybean":   {"moisture": (45, 75),  "temp": (20, 30), "rainfall": (90, 160)},
    "potato":    {"moisture": (50, 80),  "temp": (15, 25), "rainfall": (70, 130)},
    "tomato":    {"moisture": (55, 80),  "temp": (20, 30), "rainfall": (80, 140)},
    "sugarcane": {"moisture": (65, 90),  "temp": (25, 38), "rainfall": (130, 210)},
    "sunflower": {"moisture": (35, 65),  "temp": (20, 32), "rainfall": (60, 120)},
    "barley":    {"moisture": (30, 55),  "temp": (12, 22), "rainfall": (45,  90)},
}


# ================== HELPERS ==================
def compute_confidence(sensor_data: dict, crop: str) -> float:
    crop_key = crop.lower()
    if crop_key not in CROP_THRESHOLDS:
        return round(random.uniform(0.68, 0.87), 2)
    th = CROP_THRESHOLDS[crop_key]
    vals = [
        (sensor_data.get("soil_moisture",    50), th["moisture"]),
        (sensor_data.get("soil_temperature", 25), th["temp"]),
        (sensor_data.get("rainfall",         100), th["rainfall"]),
    ]
    scores = []
    for v, (lo, hi) in vals:
        if lo <= v <= hi:
            scores.append(1.0)
        elif v < lo:
            scores.append(max(0.0, 1 - (lo - v) / max(lo, 1)))
        else:
            scores.append(max(0.0, 1 - (v - hi) / max(hi, 1)))
    import numpy as np
    return round(float(np.mean(scores)), 2)


def rule_predict(sensor_data: dict, crop: str) -> dict:
    """Rule-based fallback when ML models are unavailable."""
    moisture = sensor_data.get("soil_moisture",    50)
    temp     = sensor_data.get("soil_temperature", 25)
    rainfall = sensor_data.get("rainfall",        100)

    if moisture > 70 and temp > 27:
        rec, months = "Rice", 4
    elif moisture < 38 and temp < 23:
        rec, months = "Wheat", 5
    elif rainfall > 140:
        rec, months = "Sugarcane", 12
    elif 40 <= moisture <= 70 and 20 <= temp <= 30:
        rec, months = "Maize", 3
    else:
        rec, months = (crop.capitalize() if crop else "Soybean"), 4

    return {"crop": rec, "months": months,
            "confidence": compute_confidence(sensor_data, rec)}


def build_alerts(sensor_data: dict) -> list:
    alerts = []
    m = sensor_data.get("soil_moisture", 50)
    t = sensor_data.get("air_temperature", 28)
    w = sensor_data.get("water_level", 50)
    h = sensor_data.get("humidity", 60)

    if m < 30:
        alerts.append({"type": "warning", "msg": "Low soil moisture — irrigation recommended"})
    elif m > 82:
        alerts.append({"type": "info",    "msg": "High moisture — check drainage"})
    if t > 36:
        alerts.append({"type": "danger",  "msg": "Heat stress risk — apply shade/cooling"})
    if w < 25:
        alerts.append({"type": "warning", "msg": "Water reservoir critically low"})
    if h < 30:
        alerts.append({"type": "info",    "msg": "Low humidity — consider mulching"})
    return alerts


# ================== ROUTES ==================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/sensor-data", methods=["GET"])
def api_sensor_data():
    """Live sensor readings — polled every 5 s by the dashboard."""
    try:
        raw = get_sensor_data()
        l_vals = [raw.get(f"L{i}", 0) for i in range(1, 5)]
        water_pct = int(sum(l_vals) / max(len(l_vals), 1) * 100)

        data = {
            "timestamp":       datetime.now().isoformat(),
            "source":          raw.get("source", "unknown"),
            "soil_moisture":   round(raw.get("soil_moisture",    50.0), 1),
            "soil_temperature":round(raw.get("soil_temperature", 25.0), 1),
            "air_temperature": round(random.uniform(22, 38), 1),
            "humidity":        round(random.uniform(40, 85), 1),
            "rainfall":        round(random.uniform(80, 150), 1),
            "light_intensity": round(random.uniform(200, 1000), 0),
            "water_level":     water_pct if water_pct > 0 else random.randint(30, 80),
            "ph":              round(random.uniform(5.5, 7.5), 1),
        }
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Sensor error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """Run crop prediction (ML or rule-based)."""
    try:
        body           = request.get_json() or {}
        crop           = body.get("crop", "")
        pred_text      = body.get("prediction_text", "")
        sensor_data    = body.get("sensor_data", {})

        if models_loaded and scaler is not None:
            import pandas as pd
            feat = {
                "Soil_Moisture_%":    sensor_data.get("soil_moisture",    50.0),
                "Soil_Temperature_C": sensor_data.get("soil_temperature", 25.0),
                "Rainfall_ml":        sensor_data.get("rainfall",        100.0),
                "Air_Temperature_C":  sensor_data.get("air_temperature",  28.0),
                "Humidity_%":         sensor_data.get("humidity",         60.0),
            }
            df     = pd.DataFrame([feat], columns=FEATURE_COLUMNS)
            scaled = scaler.transform(df)
            rec    = label_encoder.inverse_transform(crop_model.predict(scaled))[0]
            months = (int(month_lookup[rec]) if rec in month_lookup else
                      max(1, int(round(month_model.predict(scaled)[0]))) if month_model else 4)
            conf   = compute_confidence(sensor_data, rec)
        else:
            r = rule_predict(sensor_data, crop)
            rec, months, conf = r["crop"], r["months"], r["confidence"]

        return jsonify({
            "success": True,
            "prediction": {
                "recommended_crop": rec,
                "growth_months":    months,
                "confidence":       conf,
                "confidence_pct":   int(conf * 100),
                "prediction_text":  pred_text,
                "user_crop":        crop,
                "alerts":           build_alerts(sensor_data),
                "model_used":       "RandomForest ML" if models_loaded else "Rule-based fallback",
                "timestamp":        datetime.now().isoformat(),
            }
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/report", methods=["POST"])
def api_report():
    """Generate and return a downloadable PDF report."""
    try:
        from pdf_generator import generate_pdf
        body        = request.get_json() or {}
        sensor_data = body.get("sensor_data",  {})
        prediction  = body.get("prediction",   {})

        pdf_path, crop_name, growth_months = generate_pdf(
            sensor_data,
            prediction.get("recommended_crop", "Unknown"),
            prediction.get("growth_months", 0),
        )
        filename = Path(pdf_path).name
        return jsonify({"success": True,
                        "pdf_url": f"/reports/{filename}",
                        "filename": filename})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/reports/<filename>")
def serve_report(filename):
    if not filename.endswith(".pdf"):
        return "Forbidden", 403
    fp = Config.REPORTS_DIR / filename
    if not fp.exists():
        return "Not found", 404
    return send_file(fp, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


@app.route("/health")
def health():
    return jsonify({"status": "healthy",
                    "models_loaded": models_loaded,
                    "timestamp": datetime.now().isoformat()})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ================== ENTRY POINT ==================
if __name__ == "__main__":
    logger.info("🚀 AgriSetu Dashboard starting…")
    app.run(host="0.0.0.0", port=Config.PORT,
            debug=(Config.FLASK_ENV == "development"))
