"""
Arduino Data Store — Upstash Redis backend
Survives ALL Render restarts. Free tier: 10,000 requests/day.
Arduino POSTs to /api/arduino-data every 60s.
"""

import json
import os
import random
import math
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional

CACHE_TTL_SECONDS = 180   # 3 missed cycles before offline
REDIS_KEY         = "agrisetu:arduino:latest"

# ── Upstash Redis REST client (no extra library needed) ───────────────────────
REDIS_URL   = os.getenv("UPSTASH_REDIS_REST_URL",   "")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")


def _redis_set(key: str, value: str, ex: int = 300) -> bool:
    """SET key value EX seconds via Upstash REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        return False
    try:
        url  = f"{REDIS_URL}/set/{urllib.parse.quote(key)}/{urllib.parse.quote(value)}/ex/{ex}"
        req  = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()).get("result") == "OK"
    except Exception as e:
        print(f"⚠️  Redis SET error: {e}")
        return False


def _redis_get(key: str) -> Optional[str]:
    """GET key via Upstash REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    try:
        url  = f"{REDIS_URL}/get/{urllib.parse.quote(key)}"
        req  = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            result = json.loads(r.read()).get("result")
            return result  # None if key missing
    except Exception as e:
        print(f"⚠️  Redis GET error: {e}")
        return None


# ── Fallback: file-based store when Redis not configured ─────────────────────
DATA_FILE = "/tmp/arduino_data.json"


def _file_set(data: dict, received_at: str):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({"data": data, "received_at": received_at}, f)
    except Exception as e:
        print(f"⚠️  File write error: {e}")


def _file_get():
    try:
        if not os.path.exists(DATA_FILE):
            return None, None
        with open(DATA_FILE, "r") as f:
            rec = json.load(f)
        return rec.get("data"), rec.get("received_at")
    except Exception as e:
        print(f"⚠️  File read error: {e}")
        return None, None


# ── Simulated absent sensors ──────────────────────────────────────────────────
def _simulate_absent_sensors(soil_temp: float) -> Dict[str, float]:
    now   = datetime.now()
    hour  = now.hour
    month = now.month

    diurnal   = 4 * math.sin(math.pi * (hour - 6) / 12)
    air_temp  = round(max(10.0, min(45.0, soil_temp + random.uniform(-1.5, 2.5) + diurnal)), 1)
    humidity  = round(max(35.0, min(98.0, 85 - (air_temp - 20) * 1.2 + random.uniform(-8, 8))), 1)

    monsoon   = {6, 7, 8, 9}
    rainfall  = (round(random.uniform(0, 180), 1) if random.random() < 0.4 else 0.0) \
                if month in monsoon else \
                (round(random.uniform(0, 40),  1) if random.random() < 0.15 else 0.0) \
                if month in {10, 11, 3, 4} else 0.0

    if 6 <= hour <= 18:
        light = round(math.sin(math.pi * (hour - 6) / 12) * random.uniform(0.5, 1.0) * 100, 1)
    else:
        light = 0.0

    return {
        "air_temperature": air_temp,
        "humidity":        humidity,
        "rainfall":        rainfall,
        "light_intensity": light,
        "ph":              round(random.uniform(5.8, 7.2), 2),
        "simulated":       True,
    }


# ── Data Store ────────────────────────────────────────────────────────────────
class ArduinoDataStore:

    def update(self, data: Dict) -> None:
        """Save latest Arduino data — tries Redis first, falls back to file."""
        received_at = datetime.now().isoformat()
        record      = json.dumps({"data": data, "received_at": received_at})

        if REDIS_URL and REDIS_TOKEN:
            ok = _redis_set(REDIS_KEY, record, ex=300)  # auto-expire 5 min
            if ok:
                print(f"✅ Redis saved: moisture={data.get('soil_moisture')}%")
                return
            print("⚠️  Redis failed — falling back to file")

        _file_set(data, received_at)
        print(f"✅ File saved: moisture={data.get('soil_moisture')}%")

    def _read(self):
        """Read latest record — tries Redis first, falls back to file."""
        if REDIS_URL and REDIS_TOKEN:
            raw = _redis_get(REDIS_KEY)
            if raw:
                try:
                    rec         = json.loads(raw)
                    data        = rec.get("data")
                    received_at = datetime.fromisoformat(rec["received_at"])
                    return data, received_at
                except Exception as e:
                    print(f"⚠️  Redis parse error: {e}")

        # Fallback to file
        data, ts = _file_get()
        if data and ts:
            try:
                return data, datetime.fromisoformat(ts)
            except Exception:
                pass
        return None, None

    def _age(self) -> float:
        _, received_at = self._read()
        if received_at is None:
            return 99999.0
        return (datetime.now() - received_at).total_seconds()

    def get(self) -> Optional[Dict[str, Any]]:
        data, received_at = self._read()
        if data is None or received_at is None:
            return None

        age = (datetime.now() - received_at).total_seconds()
        if age > CACHE_TTL_SECONDS:
            return None

        result = dict(data)
        result.update(_simulate_absent_sensors(result.get("soil_temperature", 25.0)))
        result["source"]            = "arduino_direct"
        result["cache_age_seconds"] = round(age, 1)
        result["timestamp"]         = received_at.isoformat()
        return result

    def is_connected(self) -> bool:
        return self._age() < CACHE_TTL_SECONDS

    def connection_status(self) -> Dict:
        data, received_at = self._read()
        age   = self._age()
        error = ""
        if received_at is None:
            error = "No data received yet"
        elif age > CACHE_TTL_SECONDS:
            error = f"No data for {age:.0f}s — Arduino offline?"
        return {
            "connected":        age < CACHE_TTL_SECONDS,
            "last_seen":        received_at.isoformat() if received_at else None,
            "age_seconds":      round(age, 1),
            "error":            error,
            "token_configured": True,
        }


# Singleton
arduino_store = ArduinoDataStore()


def get_sensor_data() -> Optional[Dict[str, Any]]:
    return arduino_store.get()


def get_connection_status() -> Dict:
    return arduino_store.connection_status()