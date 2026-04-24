"""
Arduino Data Store — File-backed persistence
Survives Render worker restarts by writing data to /tmp/arduino_data.json
Arduino POSTs to /api/arduino-data every 60s.
"""

import json
import random
import math
import os
from datetime import datetime
from typing import Dict, Any, Optional

CACHE_TTL_SECONDS = 180
DATA_FILE = "/tmp/arduino_data.json"   # survives worker restarts on Render


def _simulate_absent_sensors(soil_temp: float) -> Dict[str, float]:
    now   = datetime.now()
    hour  = now.hour
    month = now.month

    diurnal_swing = 4 * math.sin(math.pi * (hour - 6) / 12)
    air_temp = round(soil_temp + random.uniform(-1.5, 2.5) + diurnal_swing, 1)
    air_temp = max(10.0, min(45.0, air_temp))

    base_hum = 85 - (air_temp - 20) * 1.2
    humidity = round(base_hum + random.uniform(-8, 8), 1)
    humidity = max(35.0, min(98.0, humidity))

    monsoon_months = {6, 7, 8, 9}
    if month in monsoon_months:
        rainfall = round(random.uniform(0, 180), 1) if random.random() < 0.4 else 0.0
    elif month in {10, 11, 3, 4}:
        rainfall = round(random.uniform(0, 40), 1) if random.random() < 0.15 else 0.0
    else:
        rainfall = 0.0

    if 6 <= hour <= 18:
        solar_angle = math.sin(math.pi * (hour - 6) / 12)
        cloud_factor = random.uniform(0.5, 1.0)
        light = round(solar_angle * cloud_factor * 100, 1)
    else:
        light = 0.0

    ph = round(random.uniform(5.8, 7.2), 2)

    return {
        "air_temperature": air_temp,
        "humidity":        humidity,
        "rainfall":        rainfall,
        "light_intensity": light,
        "ph":              ph,
        "simulated":       True,
    }


class ArduinoDataStore:

    def update(self, data: Dict) -> None:
        """Write latest data to file so it survives worker restarts."""
        record = {
            "data":         data,
            "received_at":  datetime.now().isoformat(),
        }
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(record, f)
        except Exception as e:
            print(f"⚠️  Failed to write data file: {e}")

    def _read(self):
        """Read from file. Returns (data, received_at) or (None, None)."""
        try:
            if not os.path.exists(DATA_FILE):
                return None, None
            with open(DATA_FILE, "r") as f:
                record = json.load(f)
            data        = record.get("data")
            received_at = datetime.fromisoformat(record["received_at"])
            return data, received_at
        except Exception as e:
            print(f"⚠️  Failed to read data file: {e}")
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
        soil_temp = result.get("soil_temperature", 25.0)
        result.update(_simulate_absent_sensors(soil_temp))
        result["source"]            = "arduino_direct"
        result["cache_age_seconds"] = round(age, 1)
        result["timestamp"]         = received_at.isoformat()
        return result

    def is_connected(self) -> bool:
        return self._age() < CACHE_TTL_SECONDS

    def connection_status(self) -> Dict:
        data, received_at = self._read()
        age = self._age()
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


