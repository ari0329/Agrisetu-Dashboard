"""
ThingESP Client - Fetches real-time sensor data from ThingESP platform
Includes fallback to serial/simulated data if ThingESP is unavailable
"""

import requests
import json
import random
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from config import Config

logger = logging.getLogger(__name__)

class ThingESPClient:
    """Client for fetching sensor data from ThingESP"""
    
    def __init__(self):
        self.base_url = Config.THINGESP_API_URL
        self.token = Config.THINGESP_TOKEN
        self.timeout = 10
        
    def get_sensor_data(self) -> Dict[str, Any]:
        """
        Fetch real-time sensor data from ThingESP
        
        Returns:
            Dict containing sensor readings
        """
        # Try ThingESP first
        data = self._fetch_from_thingesp()
        
        if data:
            logger.info("✅ Data fetched from ThingESP")
            return self._normalize_data(data)
        
        # Fallback to simulated data
        logger.warning("⚠️ ThingESP unavailable, using simulated data")
        return self._get_simulated_data()
    
    def _fetch_from_thingesp(self) -> Optional[Dict]:
        """Fetch raw data from ThingESP API"""
        try:
            url = f"{self.base_url}?token={self.token}"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"ThingESP timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError:
            logger.error("ThingESP connection error")
        except requests.exceptions.HTTPError as e:
            logger.error(f"ThingESP HTTP error: {e}")
        except json.JSONDecodeError:
            logger.error("ThingESP returned invalid JSON")
        except Exception as e:
            logger.error(f"ThingESP unexpected error: {e}")
        
        return None
    
    def _normalize_data(self, raw_data: Dict) -> Dict[str, Any]:
        """
        Normalize ThingESP data to expected format
        
        Handles different data formats from ESP8266:
        - JSON format: {"soil_moisture": 45, "soil_temp": 28.5, ...}
        - String format: "soil_moisture=45,soil_temp=28.5,..."
        """
        normalized = {
            'timestamp': datetime.now().isoformat(),
            'source': 'thingesp'
        }
        
        # Handle JSON format
        if isinstance(raw_data, dict):
            normalized['soil_moisture'] = self._extract_value(raw_data, 
                ['soil_moisture', 'soil', 'Soil_Moisture_%', 'moisture'])
            normalized['soil_temperature'] = self._extract_value(raw_data,
                ['soil_temp', 'temperature', 'Soil_Temperature_C', 'temp'])
            normalized['water_level'] = self._extract_value(raw_data,
                ['water_level', 'level'], 'UNKNOWN')
            normalized['L1'] = int(self._extract_value(raw_data, ['L1'], 0))
            normalized['L2'] = int(self._extract_value(raw_data, ['L2'], 0))
            normalized['L3'] = int(self._extract_value(raw_data, ['L3'], 0))
            normalized['L4'] = int(self._extract_value(raw_data, ['L4'], 0))
        
        # Handle string format (comma-separated key=value)
        elif isinstance(raw_data, str):
            for pair in raw_data.split(','):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key in ['soil_moisture', 'soil']:
                        normalized['soil_moisture'] = float(value)
                    elif key in ['soil_temp', 'temp']:
                        normalized['soil_temperature'] = float(value)
                    elif key == 'l1':
                        normalized['L1'] = int(value)
                    elif key == 'l2':
                        normalized['L2'] = int(value)
                    elif key == 'l3':
                        normalized['L3'] = int(value)
                    elif key == 'l4':
                        normalized['L4'] = int(value)
        
        # Ensure required fields exist with defaults
        normalized.setdefault('soil_moisture', 50.0)
        normalized.setdefault('soil_temperature', 25.0)
        normalized.setdefault('L1', 0)
        normalized.setdefault('L2', 0)
        normalized.setdefault('L3', 0)
        normalized.setdefault('L4', 0)
        
        return normalized
    
    def _extract_value(self, data: Dict, keys: list, default=None):
        """Extract value using multiple possible keys"""
        for key in keys:
            if key in data:
                return data[key]
        return default
    
    def _get_simulated_data(self) -> Dict[str, Any]:
        """Generate realistic simulated sensor data"""
        return {
            'timestamp': datetime.now().isoformat(),
            'source': 'simulated',
            'soil_moisture': round(random.uniform(30, 80), 2),
            'soil_temperature': round(random.uniform(20, 35), 2),
            'L1': random.choice([0, 1]),
            'L2': random.choice([0, 1]),
            'L3': random.choice([0, 1]),
            'L4': random.choice([0, 1]),
        }

# Singleton instance
thingesp_client = ThingESPClient()

def get_sensor_data() -> Dict[str, Any]:
    """Public function to get sensor data"""
    return thingesp_client.get_sensor_data()