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
import hmac
import logging
import traceback
from datetime import datetime
from pathlib import Path
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from config import Config
from advisory import full_advisory_bundle
from farm_risk import is_model_available, model_load_error as farm_risk_load_error
from prediction_explanation import build_prediction_explanation
from tts_service import sanitize_tts_text, synthesize_speech
from vision_analyzer import analyze_leaf_image, analyze_demo_profile
from mongo_store import (
    DuplicateDevice,
    StoreUnavailable,
    append_snapshot,
    authenticate_user,
    create_field,
    delete_field,
    get_analytics_summary,
    get_connection_status,
    get_history,
    get_sensor_data,
    list_fields,
    save_device_telemetry,
    update_field,
    user_exists,
)

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
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
)

# ── ML models ─────────────────────────────────────────────────────────────────
models_loaded = False
crop_model = label_encoder = month_model = scaler = None
month_lookup = {}
model_load_error = ""

try:
    import joblib, pandas as pd, numpy as np

    required_model_paths = (
        Config.CROP_MODEL_PATH,
        Config.LABEL_ENCODER_PATH,
        Config.SCALER_PATH,
    )
    missing = [path.name for path in required_model_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing model artifacts: {', '.join(missing)}")

    crop_model    = joblib.load(Config.CROP_MODEL_PATH)
    label_encoder = joblib.load(Config.LABEL_ENCODER_PATH)
    month_lookup  = (joblib.load(Config.MONTH_LOOKUP_PATH)
                     if Config.MONTH_LOOKUP_PATH.exists() else {})
    if Config.SCALER_PATH.exists():
        scaler = joblib.load(Config.SCALER_PATH)
    if Config.MONTH_MODEL_PATH.exists():
        month_model = joblib.load(Config.MONTH_MODEL_PATH)

    models_loaded = True
    logger.info("ML models loaded")
except Exception as e:
    model_load_error = str(e)
    logger.warning(f"Models unavailable; using rule-based fallback ({e})")

farm_risk_loaded = is_model_available()
if farm_risk_loaded:
    logger.info("Farm risk ML model ready for advisory")
else:
    _farm_risk_err = farm_risk_load_error()
    if _farm_risk_err:
        logger.warning(f"Farm risk model unavailable ({_farm_risk_err})")

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

def _user_id():
    return session.get("user", {}).get("id", "")


def _requested_field_id(body=None):
    return (
        (body or {}).get("field_id")
        or request.args.get("field_id")
        or ""
    ).strip()


def _offline_error(field_id):
    status = get_connection_status(_user_id(), field_id)
    return jsonify({
        "success": False,
        "arduino_offline": True,
        "error": "Device is offline or this field has no sensor data",
        "detail": status.get("error", ""),
        "last_seen": status.get("last_seen"),
    }), 503


@app.before_request
def require_login():
    public_endpoints = {"login", "logout", "health", "receive_arduino_data", "static"}
    if request.endpoint in public_endpoints or session.get("user"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("home"))

    error = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        try:
            if not user_exists(email):
                return redirect(Config.SIGNUP_URL)
            user = authenticate_user(email, password)
            if user:
                session.clear()
                session["user"] = user
                session.permanent = True
                session["fresh_login"] = True
                return redirect(url_for("home"))
            error = "Incorrect email or password."
        except StoreUnavailable:
            error = "Login is temporarily unavailable because MongoDB is not configured."
        except Exception as exc:
            logger.warning("Login failed: %s", exc)
            error = "Unable to sign in. Please try again."

    return render_template("login.html", error=error, signup_url=Config.SIGNUP_URL)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/me")
def api_me():
    return jsonify({"success": True, "user": session["user"]})


@app.route("/api/fields", methods=["GET", "POST"])
def api_fields():
    try:
        if request.method == "GET":
            return jsonify({"success": True, "fields": list_fields(_user_id())})

        body = request.get_json(silent=True) or {}
        field = create_field(
            _user_id(),
            body.get("name", ""),
            body.get("device_id", ""),
        )
        return jsonify({"success": True, "field": field}), 201
    except DuplicateDevice as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except StoreUnavailable as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


@app.route("/api/fields/<field_id>", methods=["PATCH", "DELETE"])
def api_field_detail(field_id):
    try:
        if request.method == "DELETE":
            if not delete_field(_user_id(), field_id):
                return jsonify({"success": False, "error": "Field not found"}), 404
            return jsonify({"success": True, "message": "Field deleted"})

        body = request.get_json(silent=True) or {}
        field = update_field(
            _user_id(),
            field_id,
            body.get("name", ""),
            body.get("device_id"),
        )
        return jsonify({"success": True, "field": field})
    except DuplicateDevice as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except StoreUnavailable as exc:
        return jsonify({"success": False, "error": str(exc)}), 503


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
    fresh_login = session.pop("fresh_login", False)
    return render_template("index.html", user=session["user"], fresh_login=fresh_login)


@app.route("/api/status")
def api_status():
    """
    Arduino / ThingESP connection status.
    The frontend polls this to show the connection banner.
    """
    field_id = _requested_field_id()
    if not field_id:
        return jsonify({
            "success": True,
            "connected": False,
            "last_seen": None,
            "age_seconds": None,
            "error": "Add or select a field",
        })
    status = get_connection_status(_user_id(), field_id)
    return jsonify({
        "success":    True,
        "connected":  status["connected"],
        "last_seen":  status["last_seen"],
        "age_seconds":status["age_seconds"],
        "error":      status["error"],
    })


@app.route("/api/sensor-data")
def api_sensor_data():
    """
    Returns real Arduino sensor data.
    Returns 503 when Arduino is offline — never returns fake values.
    """
    field_id = _requested_field_id()
    if not field_id:
        return jsonify({"success": False, "error": "Select a field"}), 400
    data = get_sensor_data(_user_id(), field_id)

    if data is None:
        return _offline_error(field_id)

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
    body = request.get_json(silent=True) or {}
    field_id = _requested_field_id(body)
    sensor_data = get_sensor_data(_user_id(), field_id)
    if sensor_data is None:
        return _offline_error(field_id)

    try:
        preferred     = body.get("crop", "")
        pred_text     = body.get("prediction_text", "")

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
        explanation = build_prediction_explanation(
            sensor_data, rec, preferred, pred_text,
        )
        prediction = {
            "recommended_crop": rec,
            "growth_months":    months,
            "confidence":       conf,
            "confidence_pct":   int(conf * 100),
            "prediction_text":  pred_text,
            "user_crop":        preferred,
            "explanation":      explanation["explanation"],
            "explanation_html": explanation["explanation_html"],
            "explanation_detailed": explanation["explanation_detailed"],
            "explanation_sections": explanation["explanation_sections"],
            "preferred_crop_suitable": explanation["preferred_crop_suitable"],
            "preferred_crop_score": explanation["preferred_crop_score"],
            "alerts":           advisory["alerts"],
            "advisory":         advisory,
            "model_used":       engine,
            "timestamp":        datetime.now().isoformat(),
        }

        try:
            append_snapshot(
                _user_id(),
                field_id,
                sensor_data,
                advisory=advisory,
                prediction=prediction,
            )
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
    field_id = _requested_field_id(body)
    sensor_data = get_sensor_data(_user_id(), field_id)
    if sensor_data is None:
        return _offline_error(field_id)

    vision = body.get("vision")
    bundle = full_advisory_bundle(sensor_data, vision=vision)

    try:
        append_snapshot(
            _user_id(),
            field_id,
            sensor_data,
            advisory=bundle,
            vision=vision,
        )
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
        field_id = ""
        result = None

        if request.content_type and "multipart/form-data" in request.content_type:
            crop_hint = (request.form.get("crop") or "").strip()
            field_id = (request.form.get("field_id") or "").strip()
            file = request.files.get("image") or request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No image file uploaded"}), 400
            result = analyze_leaf_image(file.read(), crop_hint=crop_hint)
        else:
            body = request.get_json(silent=True) or {}
            crop_hint = (body.get("crop") or "").strip()
            field_id = (body.get("field_id") or "").strip()
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

        if not field_id:
            return jsonify({"success": False, "error": "Select a field"}), 400

        if not result.get("success"):
            return jsonify(result), 400

        sensor_data = get_sensor_data(_user_id(), field_id)
        advisory = None
        if sensor_data:
            advisory = full_advisory_bundle(sensor_data, vision=result)
            try:
                append_snapshot(
                    _user_id(),
                    field_id,
                    sensor_data,
                    advisory=advisory,
                    vision=result,
                )
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
    field_id = _requested_field_id()
    if not field_id:
        return jsonify({"success": True, "summary": None, "history": [], "fields": []})
    limit = min(int(request.args.get("limit", 50)), 200)
    summary = get_analytics_summary(_user_id(), field_id)
    return jsonify({
        "success": True,
        "summary": summary,
        "history": get_history(_user_id(), field_id, limit=limit),
        "fields": list_fields(_user_id()),
    })


@app.route("/api/report", methods=["POST"])
def api_report():
    """
    Generate PDF report.
    Blocked with 503 if no real Arduino data.
    """
    body = request.get_json(silent=True) or {}
    field_id = _requested_field_id(body)
    sensor_data = get_sensor_data(_user_id(), field_id)
    if sensor_data is None:
        return _offline_error(field_id)

    try:
        from pdf_generator import generate_pdf
        prediction = body.get("prediction", {})

        pdf_path, crop_name, growth_months = generate_pdf(
            sensor_data,
            prediction.get("recommended_crop", "Unknown"),
            prediction.get("growth_months", 0),
            prediction=prediction,
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


@app.route("/api/tts", methods=["POST"])
def api_tts():
    """Generate spoken audio for dashboard text using gTTS."""
    body = request.get_json(silent=True) or {}
    text = sanitize_tts_text(body.get("text", ""))
    lang = (body.get("lang") or "en").strip()[:5]
    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400
    try:
        audio = synthesize_speech(text, lang=lang)
        return Response(audio, mimetype="audio/mpeg")
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error(f"TTS error: {exc}")
        return jsonify({"success": False, "error": "Could not generate speech"}), 500


@app.route("/health")
def health():
    missing_models = [
        str(path.name)
        for path in (
            Config.CROP_MODEL_PATH,
            Config.LABEL_ENCODER_PATH,
            Config.SCALER_PATH,
        )
        if not path.exists()
    ]
    return jsonify({
        "status":         "healthy",
        "models_loaded":  models_loaded,
        "model_load_error": model_load_error or None,
        "farm_risk_model_loaded": is_model_available(),
        "farm_risk_model_error": farm_risk_load_error() or None,
        "missing_model_files": missing_models,
        "mongodb_configured": bool(Config.MONGODB_URI),
        "modules": {
            "advisory": True,
            "vision": True,
            "analytics": True,
        },
        "timestamp":      datetime.now().isoformat(),
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ── Secret key Arduino must send ─────────────────────────────────────────────
ARDUINO_SECRET = os.getenv("ARDUINO_SECRET", "")

@app.route("/api/arduino-data", methods=["POST"])
def receive_arduino_data():
    """Accept telemetry from a configured, user-paired device."""

    # Validate secret header
    secret = request.headers.get("X-Arduino-Secret", "")
    if not ARDUINO_SECRET:
        logger.error("ARDUINO_SECRET is not configured")
        return jsonify({"success": False, "error": "Ingest is not configured"}), 503
    if not hmac.compare_digest(secret, ARDUINO_SECRET):
        logger.warning("Rejected Arduino POST: wrong secret")
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    body = request.get_json()
    if not body:
        return jsonify({"success": False, "error": "Empty body"}), 400

    device_id = (body.get("device_id") or "").strip()
    if not device_id:
        return jsonify({"success": False, "error": "device_id is required"}), 400

    try:
        L1 = int(body.get("L1", 0))
        L2 = int(body.get("L2", 0))
        L3 = int(body.get("L3", 0))
        L4 = int(body.get("L4", 0))

        air_temp_raw = body.get("air_temperature")
        water_level_raw = body.get("water_level")
        if water_level_raw is not None:
            water_level = min(max(round(float(water_level_raw)), 0), 100)
        else:
            water_level = min(L1*25 + L2*25 + L3*25 + L4*25, 100)
        normalized = {
            "soil_moisture":    round(float(body.get("soil_moisture", 0)), 1),
            "soil_temperature": round(float(body.get("soil_temperature", 25)), 1),
            "water_level":      water_level,
            "water_status":     str(body.get("water_status", ""))[:40],
            "L1": L1, "L2": L2, "L3": L3, "L4": L4,
            "air_temperature":  round(float(air_temp_raw), 1) if air_temp_raw is not None else None,
            "humidity":         None,
            "rainfall":         None,
            "light_intensity":  None,
            "ph":               None,
        }
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid sensor values"}), 400

    try:
        stored = save_device_telemetry(device_id, normalized)
    except StoreUnavailable as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    if not stored:
        return jsonify({
            "success": False,
            "error": "Device ID is not paired to a field",
        }), 404

    logger.info(f"Arduino data received: "
                f"moisture={normalized['soil_moisture']}% "
                f"temp={normalized['soil_temperature']} C "
                f"water={normalized['water_level']}%")

    return jsonify({
        "success": True,
        "message": "Data stored",
        "field_id": stored["field_id"],
        "received_at": stored["received_at"].isoformat(),
    })

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("AgriSetu Dashboard starting")
    app.run(host="0.0.0.0", port=Config.PORT,
            debug=(Config.FLASK_ENV == "development"))



