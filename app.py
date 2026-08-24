"""
AgriSetu Smart Farming Assistant — Flask Backend
- /api/sensor-data   : returns real Arduino data or 503 if offline
- /api/status        : Arduino connection status
- /api/predict       : crop ML + farmer advisories
- /api/advisory      : irrigation, env risk, nutrient advisories (edge)
- /api/vision        : leaf image disease / pest / nutrient analysis
- /api/analytics     : field history + yield-risk trends
- /api/report        : PDF report
"""
import os
import logging
import traceback
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template

from config import Config
from thingesp_client import get_sensor_data, get_connection_status
from advisory import full_advisory_bundle
from vision_analyzer import analyze_leaf_image, analyze_demo_profile
from farm_store import append_snapshot, get_analytics_summary, list_fields

# ── Logging ───────────────────────────────────────────────────────────────────
Config.LOGS_DIR.mkdir(exist_ok=True)
log_file = Config.LOGS_DIR / f"agrisetu_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY

# ── ML models ─────────────────────────────────────────────────────────────────
models_loaded = False
crop_model = label_encoder = month_model = scaler = None
month_lookup = {}

try:
    import joblib, pandas as pd, numpy as np

    crop_model    = joblib.load(Config.CROP_MODEL_PATH)
    label_encoder = joblib.load(Config.LABEL_ENCODER_PATH)
    month_lookup  = (joblib.load(Config.MONTH_LOOKUP_PATH)
                     if Config.MONTH_LOOKUP_PATH.exists() else {})
    if Config.SCALER_PATH.exists():
        scaler = joblib.load(Config.SCALER_PATH)
    if Config.MONTH_MODEL_PATH.exists():
        month_model = joblib.load(Config.MONTH_MODEL_PATH)

    models_loaded = True
    logger.info("✅ ML models loaded")
except Exception as e:
    logger.warning(f"⚠️  Models unavailable — rule-based fallback ({e})")

FEATURE_COLUMNS = [
    "Soil_Moisture_%", "Soil_Temperature_C",
    "Rainfall_ml", "Air_Temperature_C", "Humidity_%",
]

CROP_THRESHOLDS = {
    "wheat":     {"moisture": (30, 60),  "temp": (15, 25)},
    "rice":      {"moisture": (60, 90),  "temp": (25, 35)},
    "maize":     {"moisture": (40, 70),  "temp": (20, 30)},
    "cotton":    {"moisture": (35, 65),  "temp": (25, 35)},
    "soybean":   {"moisture": (45, 75),  "temp": (20, 30)},
    "potato":    {"moisture": (50, 80),  "temp": (15, 25)},
    "tomato":    {"moisture": (55, 80),  "temp": (20, 30)},
    "sugarcane": {"moisture": (65, 90),  "temp": (25, 38)},
    "sunflower": {"moisture": (35, 65),  "temp": (20, 32)},
    "barley":    {"moisture": (30, 55),  "temp": (12, 22)},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _offline_error():
    status = get_connection_status()
    return jsonify({
        "success": False,
        "arduino_offline": True,
        "error": "Arduino is offline — no real sensor data available",
        "detail": status.get("error", ""),
        "last_seen": status.get("last_seen"),
        "token_configured": status.get("token_configured", False),
    }), 503


def compute_confidence(sensor_data, crop):
    crop_key = crop.lower()
    if crop_key not in CROP_THRESHOLDS:
        return 0.70
    th = CROP_THRESHOLDS[crop_key]
    scores = []
    for v, (lo, hi) in [
        (sensor_data.get("soil_moisture",    50), th["moisture"]),
        (sensor_data.get("soil_temperature", 25), th["temp"]),
    ]:
        if lo <= v <= hi:
            scores.append(1.0)
        elif v < lo:
            scores.append(max(0.0, 1 - (lo - v) / max(lo, 1)))
        else:
            scores.append(max(0.0, 1 - (v - hi) / max(hi, 1)))
    return round(sum(scores) / len(scores), 2)


def rule_predict(sensor_data, preferred_crop):
    m = sensor_data.get("soil_moisture",    50)
    t = sensor_data.get("soil_temperature", 25)

    if m > 70 and t > 27:   rec, months = "Rice",      4
    elif m < 38 and t < 23: rec, months = "Wheat",     5
    elif m > 65:            rec, months = "Sugarcane", 12
    elif 40 <= m <= 70:     rec, months = "Maize",     3
    else:                   rec, months = (preferred_crop.capitalize()
                                           if preferred_crop else "Soybean"), 4

    return {"crop": rec, "months": months,
            "confidence": compute_confidence(sensor_data, rec)}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """
    Arduino / ThingESP connection status.
    The frontend polls this to show the connection banner.
    """
    status = get_connection_status()
    return jsonify({
        "success":    True,
        "connected":  status["connected"],
        "last_seen":  status["last_seen"],
        "age_seconds":status["age_seconds"],
        "error":      status["error"],
        "token_configured": status["token_configured"],
    })


@app.route("/api/sensor-data")
def api_sensor_data():
    """
    Returns real Arduino sensor data.
    Returns 503 when Arduino is offline — never returns fake values.
    """
    data = get_sensor_data()

    if data is None:
        return _offline_error()

    return jsonify({
        "success": True,
        "data":    data,
        "arduino_connected": data.get("source") != "cached",
        "source":  data.get("source", "unknown"),
    })


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """
    Run ML / rule-based prediction.
    Blocked with 503 if no real Arduino data available.
    """
    # Gate: refuse if Arduino is offline
    sensor_data = get_sensor_data()
    if sensor_data is None:
        return _offline_error()

    try:
        body          = request.get_json() or {}
        preferred     = body.get("crop", "")
        pred_text     = body.get("prediction_text", "")

        # Prefer sensor_data from body if supplied, otherwise use fresh fetch
        client_sensor = body.get("sensor_data", {})
        if client_sensor:
            sensor_data = client_sensor

        if models_loaded and scaler is not None:
            import pandas as pd
            # Fill missing fields with reasonable defaults for ML model
            feat = {
                "Soil_Moisture_%":    sensor_data.get("soil_moisture",    50.0),
                "Soil_Temperature_C": sensor_data.get("soil_temperature", 25.0),
                "Rainfall_ml":        sensor_data.get("rainfall")  or 100.0,
                "Air_Temperature_C":  sensor_data.get("air_temperature") or 28.0,
                "Humidity_%":         sensor_data.get("humidity")  or 60.0,
            }
            df     = pd.DataFrame([feat], columns=FEATURE_COLUMNS)
            scaled = scaler.transform(df)
            rec    = label_encoder.inverse_transform(
                        crop_model.predict(scaled))[0]
            months = (int(month_lookup[rec]) if rec in month_lookup
                      else max(1, int(round(month_model.predict(scaled)[0])))
                      if month_model else 4)
            conf   = compute_confidence(sensor_data, rec)
            engine = "RandomForest ML"
        else:
            r = rule_predict(sensor_data, preferred)
            rec, months, conf = r["crop"], r["months"], r["confidence"]
            engine = "Rule-based (ML models not loaded)"

        advisory = full_advisory_bundle(sensor_data)
        prediction = {
            "recommended_crop": rec,
            "growth_months":    months,
            "confidence":       conf,
            "confidence_pct":   int(conf * 100),
            "prediction_text":  pred_text,
            "user_crop":        preferred,
            "alerts":           advisory["alerts"],
            "advisory":         advisory,
            "model_used":       engine,
            "timestamp":        datetime.now().isoformat(),
        }

        field_id = (body.get("field_id") or "field-1").strip() or "field-1"
        try:
            append_snapshot(sensor_data, advisory=advisory, prediction=prediction,
                            field_id=field_id)
        except Exception as store_err:
            logger.warning(f"Analytics store skip: {store_err}")

        return jsonify({"success": True, "prediction": prediction})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/advisory", methods=["GET", "POST"])
def api_advisory():
    """
    Edge-style farmer advisory: irrigation, drought/flood/heat, nutrients.
    Uses live Arduino data when available; POST may supply sensor_data for demos.
    """
    body = request.get_json(silent=True) or {}
    sensor_data = body.get("sensor_data") or get_sensor_data()
    if sensor_data is None:
        return _offline_error()

    vision = body.get("vision")
    field_id = (body.get("field_id") or request.args.get("field_id") or "field-1").strip()
    bundle = full_advisory_bundle(sensor_data, vision=vision)

    try:
        append_snapshot(sensor_data, advisory=bundle, vision=vision, field_id=field_id)
    except Exception as store_err:
        logger.warning(f"Analytics store skip: {store_err}")

    return jsonify({
        "success": True,
        "field_id": field_id,
        "edge_processed": True,
        "sensor_source": sensor_data.get("source", "unknown"),
        **bundle,
    })


@app.route("/api/vision", methods=["POST"])
def api_vision():
    """
    Crop health / pest / nutrient analysis from a leaf image (multipart)
    or demo_profile JSON for demos without a camera.
    Runs locally on the server (edge-friendly, no cloud CV).
    """
    try:
        crop_hint = ""
        field_id = "field-1"
        result = None

        if request.content_type and "multipart/form-data" in request.content_type:
            crop_hint = (request.form.get("crop") or "").strip()
            field_id = (request.form.get("field_id") or "field-1").strip() or "field-1"
            file = request.files.get("image") or request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No image file uploaded"}), 400
            result = analyze_leaf_image(file.read(), crop_hint=crop_hint)
        else:
            body = request.get_json(silent=True) or {}
            crop_hint = (body.get("crop") or "").strip()
            field_id = (body.get("field_id") or "field-1").strip() or "field-1"
            demo = body.get("demo_profile")
            if demo:
                result = analyze_demo_profile(demo)
            elif body.get("image_base64"):
                import base64
                raw = body["image_base64"]
                if "," in raw:
                    raw = raw.split(",", 1)[1]
                result = analyze_leaf_image(base64.b64decode(raw), crop_hint=crop_hint)
            else:
                return jsonify({
                    "success": False,
                    "error": "Provide multipart image, image_base64, or demo_profile",
                }), 400

        if not result.get("success"):
            return jsonify(result), 400

        sensor_data = get_sensor_data()
        advisory = None
        if sensor_data:
            advisory = full_advisory_bundle(sensor_data, vision=result)
            try:
                append_snapshot(sensor_data, advisory=advisory, vision=result,
                                field_id=field_id)
            except Exception as store_err:
                logger.warning(f"Analytics store skip: {store_err}")

        return jsonify({
            "success": True,
            "field_id": field_id,
            "vision": result,
            "advisory": advisory,
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analytics")
def api_analytics():
    """Farm analytics: historical trends, yield-risk, disease/pest event counts."""
    field_id = (request.args.get("field_id") or "field-1").strip() or "field-1"
    limit = min(int(request.args.get("limit", 50)), 200)
    summary = get_analytics_summary(field_id)
    from farm_store import get_history
    return jsonify({
        "success": True,
        "summary": summary,
        "history": get_history(field_id, limit=limit),
        "fields": list_fields(),
    })


@app.route("/api/report", methods=["POST"])
def api_report():
    """
    Generate PDF report.
    Blocked with 503 if no real Arduino data.
    """
    sensor_data = get_sensor_data()
    if sensor_data is None:
        return _offline_error()

    try:
        from pdf_generator import generate_pdf
        body       = request.get_json() or {}
        prediction = body.get("prediction", {})

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
    status = get_connection_status()
    return jsonify({
        "status":         "healthy",
        "models_loaded":  models_loaded,
        "arduino":        status,
        "modules": {
            "advisory": True,
            "vision": True,
            "analytics": True,
        },
        "fields": list_fields(),
        "timestamp":      datetime.now().isoformat(),
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ── Secret key Arduino must send ─────────────────────────────────────────────
ARDUINO_SECRET = os.getenv("ARDUINO_SECRET", "agrisetu-secret-key-2024")

@app.route("/api/arduino-data", methods=["POST"])
def receive_arduino_data():
    """Arduino POSTs real sensor JSON here every 30 seconds."""

    # Validate secret header
    secret = request.headers.get("X-Arduino-Secret", "")
    if secret != ARDUINO_SECRET:
        logger.warning("⛔ Rejected Arduino POST — wrong secret")
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    body = request.get_json()
    if not body:
        return jsonify({"success": False, "error": "Empty body"}), 400

    from thingesp_client import arduino_store

    L1 = int(body.get("L1", 0))
    L2 = int(body.get("L2", 0))
    L3 = int(body.get("L3", 0))
    L4 = int(body.get("L4", 0))

    normalized = {
        "soil_moisture":    round(float(body.get("soil_moisture",    0)), 1),
        "soil_temperature": round(float(body.get("soil_temperature", 25)), 1),
        "water_level":      min(L1*25 + L2*25 + L3*25 + L4*25, 100),
        "L1": L1, "L2": L2, "L3": L3, "L4": L4,
        "air_temperature":  None,
        "humidity":         None,
        "rainfall":         None,
        "light_intensity":  None,
        "ph":               None,
    }

    arduino_store.update(normalized)
    logger.info(f"✅ Arduino data received: "
                f"moisture={normalized['soil_moisture']}% "
                f"temp={normalized['soil_temperature']}°C "
                f"water={normalized['water_level']}%")

    return jsonify({"success": True, "message": "Data stored"})

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 AgriSetu Dashboard starting…")
    app.run(host="0.0.0.0", port=Config.PORT,
            debug=(Config.FLASK_ENV == "development"))



