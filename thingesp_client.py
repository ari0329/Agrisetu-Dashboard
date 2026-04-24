"""
Arduino Data Store
Arduino POSTs to /api/arduino-data every 30 s.
This module holds the latest reading in memory.
Absent sensors (air_temp, humidity, rainfall, light, pH) are filled
with seasonally-appropriate random values so the ML model always has
a full feature vector.
"""

import random
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

CACHE_TTL_SECONDS = 60   # data older than 60 s = device offline


def _simulate_absent_sensors(soil_temp: float) -> Dict[str, float]:
    """
    Generate realistic simulated values for sensors not physically present
    on this Arduino.  Values are correlated with soil_temp and time-of-day
    so they look plausible rather than purely random.
    """
    now   = datetime.now()
    hour  = now.hour
    month = now.month  # 1-12

    # ── Air temperature: close to soil temp, +/- small diurnal variation ──
    diurnal_swing = 4 * math.sin(math.pi * (hour - 6) / 12)   # peak at 18:00
    air_temp = round(soil_temp + random.uniform(-1.5, 2.5) + diurnal_swing, 1)
    air_temp = max(10.0, min(45.0, air_temp))

    # ── Humidity: inversely correlated with temperature, 40-95% ──
    base_hum  = 85 - (air_temp - 20) * 1.2
    humidity  = round(base_hum + random.uniform(-8, 8), 1)
    humidity  = max(35.0, min(98.0, humidity))

    # ── Rainfall: seasonal (Indian monsoon: Jun-Sep high) ──
    monsoon_months = {6, 7, 8, 9}
    if month in monsoon_months:
        # 40 % chance of some rain during monsoon
        rainfall = round(random.uniform(0, 180), 1) if random.random() < 0.4 else 0.0
    elif month in {10, 11, 3, 4}:
        rainfall = round(random.uniform(0, 40), 1)  if random.random() < 0.15 else 0.0
    else:
        rainfall = 0.0

    # ── Light intensity: LUX-like 0-100 scale, zero at night ──
    if 6 <= hour <= 18:
        solar_angle = math.sin(math.pi * (hour - 6) / 12)
        cloud_factor = random.uniform(0.5, 1.0)
        light = round(solar_angle * cloud_factor * 100, 1)
    else:
        light = 0.0

    # ── Soil pH: typical agricultural range 5.5-7.5 ──
    ph = round(random.uniform(5.8, 7.2), 2)

    return {
        "air_temperature": air_temp,
        "humidity":        humidity,
        "rainfall":        rainfall,
        "light_intensity": light,
        "ph":              ph,
        "simulated":       True,   # flag so frontend can show a tooltip
    }


class ArduinoDataStore:

    def __init__(self):
        self.latest:    Optional[Dict] = None
        self.received_at: Optional[datetime] = None
        self.last_error:  str = "No data received yet"

    def update(self, data: Dict) -> None:
        """Called by /api/arduino-data when Arduino POSTs."""
        self.latest      = data
        self.received_at = datetime.now()
        self.last_error  = ""

    def get(self) -> Optional[Dict[str, Any]]:
        """Returns latest data if fresh, None if stale/missing.
        Absent sensors are filled with correlated simulated values."""
        if not self.latest or not self.received_at:
            return None
        if self._age() > CACHE_TTL_SECONDS:
            self.last_error = f"No data for {self._age():.0f}s — Arduino offline?"
            return None

        result = dict(self.latest)

        # Fill absent sensors with realistic simulated values
        soil_temp = result.get("soil_temperature", 25.0)
        simulated = _simulate_absent_sensors(soil_temp)
        result.update(simulated)

        result["source"]            = "arduino_direct"
        result["cache_age_seconds"] = round(self._age(), 1)
        result["timestamp"]         = self.received_at.isoformat()
        return result

    def is_connected(self) -> bool:
        return self.latest is not None and self._age() < CACHE_TTL_SECONDS

    def connection_status(self) -> Dict:
        return {
            "connected":    self.is_connected(),
            "last_seen":    self.received_at.isoformat() if self.received_at else None,
            "age_seconds":  round(self._age(), 1),
            "error":        self.last_error,
            "token_configured": True,   # not needed for direct push
        }

    def _age(self) -> float:
        if not self.received_at:
            return 99999.0
        return (datetime.now() - self.received_at).total_seconds()


# Singleton
arduino_store = ArduinoDataStore()


def get_sensor_data() -> Optional[Dict[str, Any]]:
    return arduino_store.get()


def get_connection_status() -> Dict:
    return arduino_store.connection_status()