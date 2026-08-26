/*
 * AgriSetu ESP8266
 * - POSTs telemetry to the dashboard every 5 seconds
 * - Optional ThingESP WhatsApp (disable if credentials fail — it blocks WiFi)
 * - Pairs telemetry using DEVICE_ID_VALUE from arduino_secrets.h
 */

#include <Wire.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>
#include "RTClib.h"
#include "arduino_secrets.h"

#ifndef THINGESP_ENABLED
#define THINGESP_ENABLED 0
#endif

#if THINGESP_ENABLED
#include <ThingESP.h>
ThingESP8266 thing(
  THINGESP_USERNAME_VALUE,
  THINGESP_PROJECT_VALUE,
  THINGESP_TOKEN_VALUE
);
#endif

const char* BACKEND_URL =
  "https://agrisetu-dashboard.onrender.com/api/arduino-data";

RTC_DS3231 rtc;
WiFiClientSecure secureClient;

#define SOIL_PIN A0
#define LEVEL1 D5
#define LEVEL2 D6
#define LEVEL3 D7
#define LEVEL4 D8

bool rtcAvailable = false;
bool telemetryBusy = false;
float soilMoisture = 0.0;
float soilTemperature = 25.0;
int level1 = 0, level2 = 0, level3 = 0, level4 = 0;
char sensorTimestamp[20] = "N/A";

unsigned long lastPost = 0;
unsigned long lastWhatsApp = 0;
unsigned long lastThingTick = 0;
unsigned long postCount = 0;

const unsigned long POST_INTERVAL_MS = 5000UL;
const unsigned long WHATSAPP_INTERVAL_MS = 300000UL;
const unsigned long THING_TICK_MS = 200UL;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(false);
  WiFi.begin(WIFI_SSID_VALUE, WIFI_PASSWORD_VALUE);

  Serial.print("Connecting to WiFi");
  for (int attempt = 0; WiFi.status() != WL_CONNECTED; attempt++) {
    delay(500);
    Serial.print(".");
    yield();
    ESP.wdtFeed();
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

const char* describeWaterLevel() {
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
    snprintf(
      sensorTimestamp, sizeof(sensorTimestamp), "%04d-%02d-%02d %02d:%02d:%02d",
      now.year(), now.month(), now.day(),
      now.hour(), now.minute(), now.second()
    );
  }
  level1 = readLevelPin(LEVEL1);
  level2 = readLevelPin(LEVEL2);
  level3 = readLevelPin(LEVEL3);
  level4 = readLevelPin(LEVEL4);
}

bool postTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return false;

  telemetryBusy = true;

  char payload[320];
  snprintf(
    payload, sizeof(payload),
    "{"
    "\"soil_moisture\":%.1f,"
    "\"soil_temperature\":%.1f,"
    "\"L1\":%d,"
    "\"L2\":%d,"
    "\"L3\":%d,"
    "\"L4\":%d,"
    "\"water_status\":\"%s\","
    "\"timestamp\":\"%s\","
    "\"device_id\":\"" DEVICE_ID_VALUE "\""
    "}",
    soilMoisture,
    soilTemperature,
    level1, level2, level3, level4,
    describeWaterLevel(),
    sensorTimestamp
  );

  bool ok = false;
  for (int attempt = 1; attempt <= 3; attempt++) {
    secureClient.stop();
    yield();
    ESP.wdtFeed();

    HTTPClient http;
    http.setTimeout(15000);
    http.setReuse(false);

    if (!http.begin(secureClient, BACKEND_URL)) {
      Serial.println("HTTP initialization failed");
      delay(1000);
      continue;
    }

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Arduino-Secret", ARDUINO_SECRET_VALUE);
    int code = http.POST(payload);
    String response = http.getString();
    http.end();
    secureClient.stop();

    Serial.printf(
      "POST #%lu attempt %d: HTTP %d %s (heap %u)\n",
      postCount + 1, attempt, code, response.c_str(), ESP.getFreeHeap()
    );

    if (code >= 200 && code < 300) {
      ok = true;
      break;
    }
    if (code == 401 || code == 404) break;
    delay(1000);
  }

  telemetryBusy = false;
  return ok;
}

#if THINGESP_ENABLED
String handleResponse(String query) {
  query.trim();
  query.toLowerCase();
  if (query == "moisture" || query == "soil")
    return "Soil Moisture: " + String(soilMoisture, 1) + "%";
  if (query == "temp" || query == "temperature")
    return "Soil Temp: " + String(soilTemperature, 1) + " C";
  if (query == "water" || query == "level")
    return String("Water: ") + describeWaterLevel();
  if (query == "all" || query == "status" || query == "report") {
    readSensors();
    return "AgriSetu\nMoisture: " + String(soilMoisture, 1) +
      "%\nTemp: " + String(soilTemperature, 1) +
      " C\nWater: " + String(describeWaterLevel()) + "\nTime: " + sensorTimestamp;
  }
  return "Commands: moisture | temp | water | all";
}
#endif

void setup() {
  Serial.begin(115200);
  delay(100);

  secureClient.setInsecure();
  secureClient.setTimeout(15000);

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

#if THINGESP_ENABLED
  thing.initDevice();
  thing.setCallback(&handleResponse);
  Serial.println("ThingESP enabled for WhatsApp commands.");
#else
  Serial.println("ThingESP disabled — dashboard telemetry only.");
#endif

  readSensors();
  postTelemetry();
  postCount++;
  lastPost = millis();
  lastWhatsApp = millis();
  lastThingTick = millis();

  Serial.printf("Ready. Free heap: %u bytes\n", ESP.getFreeHeap());
}

void loop() {
  unsigned long now = millis();

#if THINGESP_ENABLED
  if (!telemetryBusy && now - lastThingTick >= THING_TICK_MS) {
    lastThingTick = now;
    thing.Handle();
  }
#endif

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    now = millis();
  }

  if (now - lastPost >= POST_INTERVAL_MS) {
    readSensors();
    postTelemetry();
    postCount++;
    lastPost = millis();
  }

#if THINGESP_ENABLED
  if (!telemetryBusy && now - lastWhatsApp >= WHATSAPP_INTERVAL_MS) {
    lastWhatsApp = now;
    thing.sendMsg(
      OWNER_PHONE_VALUE,
      "AgriSetu Report\nMoisture: " + String(soilMoisture, 1) +
      "%\nTemp: " + String(soilTemperature, 1) +
      " C\nWater: " + String(describeWaterLevel())
    );
  }
#endif

  yield();
  delay(10);
}
