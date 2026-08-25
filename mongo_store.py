"""MongoDB-backed users, fields, telemetry, and analytics."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

from config import Config


class StoreUnavailable(RuntimeError):
    pass


class DuplicateDevice(ValueError):
    pass


_client: Optional[MongoClient] = None
_db = None
_indexes_ready = False


def _database():
    global _client, _db, _indexes_ready
    if not Config.MONGODB_URI:
        raise StoreUnavailable("MONGODB_URI is not configured")

    if _db is None:
        _client = MongoClient(
            Config.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        _client.admin.command("ping")
        _db = _client[Config.MONGODB_DATABASE]

    if not _indexes_ready:
        _db.fields.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
        _db.fields.create_index("device_key", unique=True)
        _db.telemetry_latest.create_index("field_id", unique=True)
        _db.telemetry_history.create_index(
            [("field_id", ASCENDING), ("received_at", DESCENDING)]
        )
        _indexes_ready = True
    return _db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _public_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name") or user.get("email", "").split("@", 1)[0],
        "email": user.get("email", ""),
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Validate an existing bcrypt user from the shared users collection."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None

    users = _database()[Config.MONGODB_USERS_COLLECTION]
    user = users.find_one({"email": email})
    if not user:
        return None

    password_hash = user.get("password", "")
    if not isinstance(password_hash, str) or not password_hash.startswith(
        ("$2a$", "$2b$", "$2y$")
    ):
        raise ValueError("The shared user password is not a supported bcrypt hash")

    if not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
        return None
    return _public_user(user)


def user_exists(email: str) -> bool:
    email = (email or "").strip().lower()
    if not email:
        return False
    users = _database()[Config.MONGODB_USERS_COLLECTION]
    return users.count_documents({"email": email}, limit=1) == 1


def _device_key(device_id: str) -> str:
    normalized = (device_id or "").strip()
    if not normalized:
        raise ValueError("Device ID is required")
    return hmac.new(
        Config.DEVICE_ID_PEPPER.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def list_fields(user_id: str) -> List[dict]:
    cursor = _database().fields.find({"user_id": user_id}).sort("created_at", ASCENDING)
    return [
        {
            "id": str(field["_id"]),
            "name": field["name"],
            "paired": True,
            "created_at": field["created_at"].isoformat(),
        }
        for field in cursor
    ]


def create_field(user_id: str, name: str, device_id: str) -> dict:
    name = (name or "").strip()
    device_id = (device_id or "").strip()
    if not 1 <= len(name) <= 80:
        raise ValueError("Field name must be between 1 and 80 characters")
    if not 6 <= len(device_id) <= 128:
        raise ValueError("Device ID must be between 6 and 128 characters")

    doc = {
        "user_id": user_id,
        "name": name,
        "device_key": _device_key(device_id),
        "created_at": _utcnow(),
    }
    try:
        result = _database().fields.insert_one(doc)
    except DuplicateKeyError as exc:
        raise DuplicateDevice("This Device ID is already paired") from exc
    return {
        "id": str(result.inserted_id),
        "name": name,
        "paired": True,
        "created_at": doc["created_at"].isoformat(),
    }


def get_field(user_id: str, field_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(field_id)
    except Exception:
        return None
    return _database().fields.find_one({"_id": oid, "user_id": user_id})


def save_device_telemetry(device_id: str, data: dict) -> Optional[dict]:
    """Resolve a paired Device ID and store its latest reading plus history."""
    db = _database()
    field = db.fields.find_one({"device_key": _device_key(device_id)})
    if not field:
        return None

    received_at = _utcnow()
    record = {
        "field_id": str(field["_id"]),
        "user_id": field["user_id"],
        "received_at": received_at,
        "data": data,
    }
    db.telemetry_latest.replace_one(
        {"field_id": record["field_id"]}, record, upsert=True
    )
    db.telemetry_history.insert_one(record.copy())
    return {"field_id": record["field_id"], "received_at": received_at}


def get_sensor_data(user_id: str, field_id: str) -> Optional[Dict[str, Any]]:
    if not get_field(user_id, field_id):
        return None
    record = _database().telemetry_latest.find_one(
        {"field_id": field_id, "user_id": user_id}
    )
    if not record:
        return None

    age = (_utcnow() - record["received_at"]).total_seconds()
    if age > Config.SENSOR_FRESHNESS_SECONDS:
        return None

    result = dict(record["data"])
    result.update(
        {
            "source": "arduino_direct",
            "cache_age_seconds": round(age, 1),
            "timestamp": record["received_at"].isoformat(),
        }
    )
    return result


def get_connection_status(user_id: str, field_id: str) -> dict:
    if not get_field(user_id, field_id):
        return {
            "connected": False,
            "last_seen": None,
            "age_seconds": None,
            "error": "Select a valid field",
        }
    record = _database().telemetry_latest.find_one(
        {"field_id": field_id, "user_id": user_id}
    )
    if not record:
        return {
            "connected": False,
            "last_seen": None,
            "age_seconds": None,
            "error": "No data received for this field yet",
        }
    age = (_utcnow() - record["received_at"]).total_seconds()
    connected = age <= Config.SENSOR_FRESHNESS_SECONDS
    return {
        "connected": connected,
        "last_seen": record["received_at"].isoformat(),
        "age_seconds": round(age, 1),
        "error": "" if connected else f"No data for {age:.0f}s — device offline?",
    }


def append_snapshot(
    user_id: str,
    field_id: str,
    sensor_data: dict,
    advisory: Optional[dict] = None,
    vision: Optional[dict] = None,
    prediction: Optional[dict] = None,
) -> dict:
    if not get_field(user_id, field_id):
        raise ValueError("Unknown field")
    point = {
        "user_id": user_id,
        "field_id": field_id,
        "timestamp": _utcnow(),
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
    _database().analytics.insert_one(point.copy())
    point["timestamp"] = point["timestamp"].isoformat()
    return point


def get_history(user_id: str, field_id: str, limit: int = 50) -> List[dict]:
    cursor = (
        _database()
        .analytics.find({"user_id": user_id, "field_id": field_id}, {"_id": 0})
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    history = list(cursor)
    history.reverse()
    for point in history:
        point["timestamp"] = point["timestamp"].isoformat()
    return history


def get_analytics_summary(user_id: str, field_id: str) -> Dict[str, Any]:
    history = get_history(user_id, field_id, limit=100)
    if not history:
        return {
            "field_id": field_id,
            "points": 0,
            "avg_moisture": None,
            "avg_yield_risk": None,
            "disease_events": 0,
            "pest_events": 0,
            "irrigation_irrigate_now_count": 0,
            "trend": [],
        }

    moistures = [p["soil_moisture"] for p in history if p.get("soil_moisture") is not None]
    risks = [p["yield_risk_pct"] for p in history if p.get("yield_risk_pct") is not None]
    return {
        "field_id": field_id,
        "points": len(history),
        "avg_moisture": round(sum(moistures) / len(moistures), 1) if moistures else None,
        "avg_yield_risk": round(sum(risks) / len(risks), 1) if risks else None,
        "latest_yield_risk": risks[-1] if risks else None,
        "disease_events": sum(1 for p in history if p.get("disease_detected")),
        "pest_events": sum(1 for p in history if p.get("pest_detected")),
        "irrigation_irrigate_now_count": sum(
            1 for p in history if p.get("irrigation_action") == "irrigate_now"
        ),
        "trend": [
            {
                "t": p["timestamp"][11:16],
                "moisture": p.get("soil_moisture"),
                "yield_risk": p.get("yield_risk_pct"),
                "health": p.get("field_health_score"),
            }
            for p in history[-24:]
        ],
    }
