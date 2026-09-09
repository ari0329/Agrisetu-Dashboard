"""
AgriSetu Configuration
Loads environment variables; provides sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".") / ".env")


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────────
    FLASK_ENV  = os.getenv("FLASK_ENV", "production")
    PORT       = int(os.getenv("PORT", 10000))
    BASE_URL   = os.getenv("BASE_URL", "https://agrisetu-21.onrender.com")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

    # ── Shared MongoDB identity + farm data ───────────────────────────────────
    MONGODB_URI              = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE         = os.getenv("MONGODB_DATABASE", "test")
    MONGODB_USERS_COLLECTION = os.getenv("MONGODB_USERS_COLLECTION", "users")
    SIGNUP_URL               = os.getenv(
        "SIGNUP_URL", "https://agrisetu-1-f5md.onrender.com/signup"
    )
    DEVICE_ID_PEPPER         = os.getenv("DEVICE_ID_PEPPER", SECRET_KEY)
    SENSOR_FRESHNESS_SECONDS = int(os.getenv("SENSOR_FRESHNESS_SECONDS", "30"))

    # ── ThingESP ───────────────────────────────────────────────────────────────
    THINGESP_USERNAME = os.getenv("THINGESP_USERNAME", "Noctum")
    THINGESP_PROJECT  = os.getenv("THINGESP_PROJECT",  "Agrisetu")
    THINGESP_TOKEN    = os.getenv("THINGESP_TOKEN")
    THINGESP_API_URL  = os.getenv(
        "THINGESP_API_URL",
        f"https://thingesp.com/api/users/{os.getenv('THINGESP_USERNAME','Noctum')}"
        f"/projects/{os.getenv('THINGESP_PROJECT','Agrisetu')}/webhooks/twilio",
    )

    # ── ML Model paths ─────────────────────────────────────────────────────────
    MODEL_DIR           = Path(__file__).parent / "models"
    CROP_MODEL_PATH     = MODEL_DIR / "crop_model.pkl"
    LABEL_ENCODER_PATH  = MODEL_DIR / "label_encoder.pkl"
    MONTH_MODEL_PATH    = MODEL_DIR / "month_model.pkl"
    MONTH_LOOKUP_PATH   = MODEL_DIR / "crop_month_lookup.pkl"
    SCALER_PATH         = MODEL_DIR / "scaler.pkl"
    MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.pkl"
    FARM_RISK_MODEL_PATH = MODEL_DIR / "farm_risk_model.pkl"

    # ── Directories ───────────────────────────────────────────────────────────
    REPORTS_DIR = Path(__file__).parent / "reports"
    LOGS_DIR    = Path(__file__).parent / "logs"
    DATA_DIR    = Path(__file__).parent / "data"
    UPLOADS_DIR = Path(__file__).parent / "uploads"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls):
        cls.REPORTS_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.UPLOADS_DIR.mkdir(exist_ok=True)
        if not cls.THINGESP_TOKEN:
            print("⚠️  THINGESP_TOKEN not set — Arduino direct ingest still works via /api/arduino-data.")
        if not cls.MONGODB_URI:
            print("WARNING: MONGODB_URI not set; login, fields, and telemetry are unavailable.")
        return True


Config.validate()
