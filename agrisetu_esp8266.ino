/*
 * AgriSetu ESP8266
 * - Services ThingESP every 200 ms
 * - Reads and POSTs telemetry every 5 seconds
 * - Pairs telemetry to a dashboard field using DEVICE_ID_VALUE
 */

#include <Wire.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include "RTClib.h"
#include <ThingESP.h>
#include "arduino_secrets.h"

const char* BACKEND_URL =
  "https://agrisetu-dashboard.onrender.com/api/arduino-data";

ThingESP8266 thing(
  THINGESP_USERNAME_VALUE,
  THINGESP_PROJECT_VALUE,
  THINGESP_TOKEN_VALUE
);
RTC_DS3231 rtc;

#define SOIL_PIN A0
#define LEVEL1 D5
#define LEVEL2 D6
#define LEVEL3 D7
#define LEVEL4 D8

bool rtcAvailable = false;
float soilMoisture = 0.0;
float soilTemperature = 25.0;
int level1 = 0, level2 = 0, level3 = 0, level4 = 0;
String waterStatus = "Unknown";
String sensorTimestamp = "N/A";

unsigned long lastPost = 0;
unsigned long lastWhatsApp = 0;
unsigned long lastThingTick = 0;

const unsigned long POST_INTERVAL_MS = 5000UL;
const unsigned long WHATSAPP_INTERVAL_MS = 300000UL;
const unsigned long THING_TICK_MS = 200UL;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID_VALUE, WIFI_PASSWORD_VALUE);
  Serial.print("Connecting to WiFi");
  for (int attempt = 0; WiFi.status() != WL_CONNECTED; attempt++) {
    delay(500);
    Serial.print(".");
    if (attempt >= 39) {
      Serial.println("\nWiFi failed; restarting");
      delay(1000);
      ESP.restart();
    }
  }
  Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
}

float readMoisturePercent() {
  return constrain((float)map(analogRead(SOIL_PIN), 0, 1023, 100, 0), 0, 100);
}

int readLevelPin(int pin) {
  int activeReads = 0;
  for (int i = 0; i < 5; i++) {
    if (digitalRead(pin) == LOW) activeReads++;
    delay(5);
  }
  return activeReads >= 3 ? 1 : 0;
}

String describeWaterLevel() {
  if (level4) return "Full (100%)";
  if (level3) return "High (75%)";
  if (level2) return "Mid (50%)";
  if (level1) return "Low (25%)";
  return "Empty (0%)";
}

void readSensors() {
  soilMoisture = readMoisturePercent();
  if (rtcAvailable) {
    soilTemperature = rtc.getTemperature();
    DateTime now = rtc.now();
    char value[20];
    snprintf(
      value, sizeof(value), "%04d-%02d-%02d %02d:%02d:%02d",
      now.year(), now.month(), now.day(),
      now.hour(), now.minute(), now.second()
    );
    sensorTimestamp = String(value);
  }
  level1 = readLevelPin(LEVEL1);
  level2 = readLevelPin(LEVEL2);
  level3 = readLevelPin(LEVEL3);
  level4 = readLevelPin(LEVEL4);
  waterStatus = describeWaterLevel();
}

bool postTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return false;

  String payload = "{";
  payload += "\"soil_moisture\":" + String(soilMoisture, 1) + ",";
  payload += "\"soil_temperature\":" + String(soilTemperature, 1) + ",";
  payload += "\"L1\":" + String(level1) + ",";
  payload += "\"L2\":" + String(level2) + ",";
  payload += "\"L3\":" + String(level3) + ",";
  payload += "\"L4\":" + String(level4) + ",";
  payload += "\"water_status\":\"" + waterStatus + "\",";
  payload += "\"timestamp\":\"" + sensorTimestamp + "\",";
  payload += "\"device_id\":\"" DEVICE_ID_VALUE "\"";
  payload += "}";

  for (int attempt = 1; attempt <= 3; attempt++) {
    WiFiClientSecure client;
    client.setFingerprint(BACKEND_TLS_FINGERPRINT);
    client.setTimeout(15);

    HTTPClient http;
    http.setTimeout(15000);
    http.setReuse(false);
    if (!http.begin(client, BACKEND_URL)) {
      Serial.println("HTTP initialization failed");
      delay(1000);
      continue;
    }

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Arduino-Secret", ARDUINO_SECRET_VALUE);
    int code = http.POST(payload);
    String response = http.getString();
    http.end();

    Serial.printf("POST attempt %d: HTTP %d %s\n", attempt, code, response.c_str());
    if (code >= 200 && code < 300) return true;
    if (code == 401 || code == 404) return false;
    delay(1000);
  }
  return false;
}

String handleResponse(String query) {
  query.trim();
  query.toLowerCase();
  if (query == "moisture" || query == "soil")
    return "Soil Moisture: " + String(soilMoisture, 1) + "%";
  if (query == "temp" || query == "temperature")
    return "Soil Temp: " + String(soilTemperature, 1) + " C";
  if (query == "water" || query == "level")
    return "Water: " + waterStatus;
  if (query == "all" || query == "status" || query == "report") {
    readSensors();
    return "AgriSetu\nMoisture: " + String(soilMoisture, 1) +
      "%\nTemp: " + String(soilTemperature, 1) +
      " C\nWater: " + waterStatus + "\nTime: " + sensorTimestamp;
  }
  return "Commands: moisture | temp | water | all";
}

void setup() {
  Serial.begin(115200);
  connectWiFi();

  Wire.begin(D2, D1);
  rtcAvailable = rtc.begin();
  if (rtcAvailable && rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  pinMode(LEVEL1, INPUT_PULLUP);
  pinMode(LEVEL2, INPUT_PULLUP);
  pinMode(LEVEL3, INPUT_PULLUP);
  pinMode(LEVEL4, INPUT_PULLUP);

  thing.initDevice();
  thing.setCallback(&handleResponse);

  readSensors();
  postTelemetry();
  lastPost = millis();
  lastWhatsApp = millis();
  lastThingTick = millis();
}

void loop() {
  unsigned long now = millis();

  if (now - lastThingTick >= THING_TICK_MS) {
    lastThingTick = now;
    thing.Handle();
  }

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    now = millis();
  }

  if (now - lastPost >= POST_INTERVAL_MS) {
    lastPost = now;
    readSensors();
    postTelemetry();
  }

  if (now - lastWhatsApp >= WHATSAPP_INTERVAL_MS) {
    lastWhatsApp = now;
    thing.sendMsg(
      OWNER_PHONE_VALUE,
      "AgriSetu Report\nMoisture: " + String(soilMoisture, 1) +
      "%\nTemp: " + String(soilTemperature, 1) +
      " C\nWater: " + waterStatus
    );
  }

  delay(10);
}
