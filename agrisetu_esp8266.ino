/*
 * AgriSetu ESP8266
 * - POSTs telemetry to the dashboard every 5 seconds
 * - Optional ThingESP WhatsApp (disable if credentials fail — it blocks WiFi)
 * - Pairs telemetry using DEVICE_ID_VALUE from arduino_secrets.h
 *
 * REQUIRED LIBRARIES (Arduino Library Manager):
 *   RTClib | OneWire | DallasTemperature | ESP8266WiFi | ESP8266HTTPClient
 *
 * ═══════════════════════════════════════════════════════════════════════════
 *  WIRING DIAGRAM — NodeMCU ESP8266
 * ═══════════════════════════════════════════════════════════════════════════
 *
 *  SOIL MOISTURE (analog)
 *    Signal  →  A0
 *    VCC     →  3V
 *    GND     →  G
 *
 *  AIR TEMP — 2-WIRE waterproof probe (stainless steel, brown + black wires)
 *    This probe has only 2 wires. Inside it is usually a DS18B20 chip.
 *
 *      3V ---- 4.7 kΩ resistor ---- D3 ---- one probe wire (brown)
 *      G  ----------------------------- other probe wire (black)
 *
 *    You only need ONE extra part: a 4.7 kΩ resistor between D3 and 3V.
 *    This value goes to the dashboard "Air Temp" card.
 *
 *  SOIL TEMP — from RTC DS3231 chip (internal sensor, for Soil Temp card)
 *    SDA  →  D2
 *    SCL  →  D1
 *    VCC  →  3V
 *    GND  →  G
 *
 *  WATER LEVEL PROBE — connect probe wires directly, NO driver board
 *    Green (common)  →  G
 *    Blue   (L1)     →  D5
 *    Purple (L2)     →  D6
 *    Grey   (L3)     →  D7
 *    White  (L4)     →  D0
 *
 *  Water logic: green (common) → G. Each level pin uses pull-up.
 *  At boot the probe must be DRY for 3 seconds (auto-calibration).
 *  If levels stay 0 in water, move green from G to 3V and set
 *  WATER_COMMON_TO_GND to 0 (needs 10 kΩ from each level pin to G).
 *
 *  Open Serial Monitor at 115200 to see live sensor values.
 * ═══════════════════════════════════════════════════════════════════════════
 */

#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
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

#define SOIL_PIN         A0
#define AIR_TEMP_PIN     D3   // 2-wire probe data line (GPIO0)

#define LEVEL1 D5
#define LEVEL2 D6
#define LEVEL3 D7
#define LEVEL4 D0   // GPIO16 — matches white wire; do NOT use D8

// 1 = skip real water sensor, send random 30-50% to dashboard
#define USE_SIMULATED_WATER_LEVEL 1

// 1 = green common wire on G  |  0 = green common wire on 3V (needs 10k pulldown per level pin)
#define WATER_COMMON_TO_GND 1

#define LEVEL_DEBOUNCE_SAMPLES   9
#define LEVEL_DEBOUNCE_THRESHOLD 5

const int LEVEL_PINS[4] = {LEVEL1, LEVEL2, LEVEL3, LEVEL4};
unsigned long levelDryRiseUs[4] = {50, 50, 50, 50};
unsigned long levelLastRiseUs[4] = {0, 0, 0, 0};
bool waterCalibrated = false;

// Wet = pin takes longer to rise after discharge (water connects strip to GND)
const unsigned long WET_RISE_MARGIN_US = 180;

OneWire oneWire(AIR_TEMP_PIN);
DallasTemperature airTempSensor(&oneWire);

bool rtcAvailable = false;
bool airTempAvailable = false;
bool telemetryBusy = false;
float soilMoisture = 0.0;
float soilTemperature = 25.0;
float airTemperature = 25.0;
int level1 = 0, level2 = 0, level3 = 0, level4 = 0;
int waterLevelPercent = 0;
char waterStatusText[24] = "Simulated";
char sensorTimestamp[20] = "N/A";

unsigned long lastPost = 0;
unsigned long lastWhatsApp = 0;
unsigned long lastThingTick = 0;
unsigned long lastDebugPrint = 0;
unsigned long postCount = 0;

const unsigned long POST_INTERVAL_MS = 5000UL;
const unsigned long WHATSAPP_INTERVAL_MS = 300000UL;
const unsigned long THING_TICK_MS = 200UL;
const unsigned long DEBUG_INTERVAL_MS = 2000UL;

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
  long total = 0;
  for (int i = 0; i < 5; i++) {
    total += analogRead(SOIL_PIN);
    delay(2);
    yield();
  }
  int avg = (int)(total / 5);
  return constrain((float)map(avg, 0, 1023, 100, 0), 0, 100);
}

void initLevelPin(int pin) {
  if (pin == D0) {
    // GPIO16 has no internal pull-up — enable it manually
    pinMode(D0, INPUT);
    digitalWrite(D0, HIGH);
  } else {
#if WATER_COMMON_TO_GND
    pinMode(pin, INPUT_PULLUP);
#else
    pinMode(pin, INPUT);
#endif
  }
}

void initWaterLevelPins() {
  initLevelPin(LEVEL1);
  initLevelPin(LEVEL2);
  initLevelPin(LEVEL3);
  initLevelPin(LEVEL4);
}

void dischargeLevelPin(int pin) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
}

void enableLevelPullUp(int pin) {
  if (pin == D0) {
    pinMode(D0, INPUT);
    digitalWrite(D0, HIGH);
  } else {
    pinMode(pin, INPUT_PULLUP);
  }
}

unsigned long measureLevelRiseUs(int pin) {
  dischargeLevelPin(pin);
  delayMicroseconds(400);
  enableLevelPullUp(pin);

  unsigned long start = micros();
  while (digitalRead(pin) == LOW) {
    if (micros() - start > 4000) break;
    yield();
  }
  return micros() - start;
}

unsigned long readLevelRiseUs(int pin) {
  unsigned long total = 0;
  for (int i = 0; i < 3; i++) {
    total += measureLevelRiseUs(pin);
    delayMicroseconds(200);
    yield();
  }
  return total / 3;
}

int readRawLevelPin(int pin) {
  enableLevelPullUp(pin);
  return digitalRead(pin);
}

bool isPinWet(int pin, unsigned long dryRiseUs) {
  int wetReads = 0;
  for (int i = 0; i < LEVEL_DEBOUNCE_SAMPLES; i++) {
    unsigned long rise = measureLevelRiseUs(pin);
    if (rise > dryRiseUs + WET_RISE_MARGIN_US) wetReads++;
    delay(3);
    yield();
  }
  return wetReads >= LEVEL_DEBOUNCE_THRESHOLD;
}

int readLevelPin(int index) {
  if (!waterCalibrated) return 0;
  int pin = LEVEL_PINS[index];
  levelLastRiseUs[index] = readLevelRiseUs(pin);
  return isPinWet(pin, levelDryRiseUs[index]) ? 1 : 0;
}

void calibrateWaterSensorDry() {
  Serial.println();
  Serial.println("=== WATER CALIBRATION ===");
  Serial.println("Keep probe completely DRY and out of water for 3 seconds...");
  delay(3000);

  initWaterLevelPins();
  delay(50);

  for (int i = 0; i < 4; i++) {
    levelDryRiseUs[i] = readLevelRiseUs(LEVEL_PINS[i]);
    levelLastRiseUs[i] = levelDryRiseUs[i];
  }

  waterCalibrated = true;
  Serial.printf(
    "Dry rise-time (us): L1=%lu L2=%lu L3=%lu L4=%lu\n",
    levelDryRiseUs[0], levelDryRiseUs[1], levelDryRiseUs[2], levelDryRiseUs[3]
  );
  Serial.println("In water, rise-time should INCREASE on wet levels.");
  Serial.println("Touch green+blue wires -> L1 rise-time should jump up.");
  Serial.println("=========================");
  Serial.println();
}

void normalizeWaterLevels() {
  if (level4) {
    level3 = 1;
    level2 = 1;
    level1 = 1;
  } else if (level3) {
    level2 = 1;
    level1 = 1;
  } else if (level2) {
    level1 = 1;
  }
}

int calculateWaterLevelPercent() {
  if (level4) return 100;
  if (level3) return 75;
  if (level2) return 50;
  if (level1) return 25;
  return 0;
}

void readSimulatedWaterLevel() {
  waterLevelPercent = random(30, 51);
  level1 = 0;
  level2 = (waterLevelPercent >= 40) ? 1 : 0;
  level3 = 0;
  level4 = 0;
  snprintf(waterStatusText, sizeof(waterStatusText), "%d%%", waterLevelPercent);
}

const char* describeWaterLevel() {
#if USE_SIMULATED_WATER_LEVEL
  return waterStatusText;
#else
  if (level4) return "Full (100%)";
  if (level3) return "High (75%)";
  if (level2) return "Mid (50%)";
  if (level1) return "Low (25%)";
  return "Empty (0%)";
#endif
}

float readAirTemperature() {
  if (!airTempAvailable) return airTemperature;

  airTempSensor.requestTemperatures();
  float c = airTempSensor.getTempCByIndex(0);
  if (c == DEVICE_DISCONNECTED_C || c < -40.0f || c > 85.0f) {
    Serial.println("Air temp read failed — check D3 + 4.7k pull-up to 3V");
    return airTemperature;
  }
  return c;
}

float readSoilTemperature() {
  if (rtcAvailable) return rtc.getTemperature();
  return soilTemperature;
}

void readSensors() {
  soilMoisture = readMoisturePercent();
  soilTemperature = readSoilTemperature();
  airTemperature = readAirTemperature();

  if (rtcAvailable) {
    DateTime now = rtc.now();
    snprintf(
      sensorTimestamp, sizeof(sensorTimestamp), "%04d-%02d-%02d %02d:%02d:%02d",
      now.year(), now.month(), now.day(),
      now.hour(), now.minute(), now.second()
    );
  }

#if USE_SIMULATED_WATER_LEVEL
  readSimulatedWaterLevel();
#else
  level1 = readLevelPin(0);
  level2 = readLevelPin(1);
  level3 = readLevelPin(2);
  level4 = readLevelPin(3);
  normalizeWaterLevels();
  waterLevelPercent = calculateWaterLevelPercent();
#endif
}

void printSensorDebug() {
  Serial.printf(
    "Sensors | moisture=%.1f%% | soilT=%.1fC airT=%.1fC (%s) | water=%d%% (%s)%s\n",
    soilMoisture,
    soilTemperature,
    airTemperature,
    airTempAvailable ? "2-wire probe on D3" : "probe not found",
    waterLevelPercent,
    describeWaterLevel(),
#if USE_SIMULATED_WATER_LEVEL
    " [simulated]"
#else
    ""
#endif
  );
}

bool postTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return false;

  telemetryBusy = true;

  char payload[420];
  if (airTempAvailable) {
    snprintf(
      payload, sizeof(payload),
      "{"
      "\"soil_moisture\":%.1f,"
      "\"soil_temperature\":%.1f,"
      "\"air_temperature\":%.1f,"
      "\"L1\":%d,"
      "\"L2\":%d,"
      "\"L3\":%d,"
      "\"L4\":%d,"
      "\"water_level\":%d,"
      "\"water_status\":\"%s\","
      "\"timestamp\":\"%s\","
      "\"device_id\":\"" DEVICE_ID_VALUE "\""
      "}",
      soilMoisture,
      soilTemperature,
      airTemperature,
      level1, level2, level3, level4,
      waterLevelPercent,
      describeWaterLevel(),
      sensorTimestamp
    );
  } else {
    snprintf(
      payload, sizeof(payload),
      "{"
      "\"soil_moisture\":%.1f,"
      "\"soil_temperature\":%.1f,"
      "\"L1\":%d,"
      "\"L2\":%d,"
      "\"L3\":%d,"
      "\"L4\":%d,"
      "\"water_level\":%d,"
      "\"water_status\":\"%s\","
      "\"timestamp\":\"%s\","
      "\"device_id\":\"" DEVICE_ID_VALUE "\""
      "}",
      soilMoisture,
      soilTemperature,
      level1, level2, level3, level4,
      waterLevelPercent,
      describeWaterLevel(),
      sensorTimestamp
    );
  }

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
    return "Air Temp: " + String(airTemperature, 1) + " C";
  if (query == "water" || query == "level")
    return String("Water: ") + describeWaterLevel();
  if (query == "all" || query == "status" || query == "report") {
    readSensors();
    return "AgriSetu\nMoisture: " + String(soilMoisture, 1) +
      "%\nAir: " + String(airTemperature, 1) +
      " C\nSoil: " + String(soilTemperature, 1) +
      " C\nWater: " + String(waterLevelPercent) + "% (" +
      String(describeWaterLevel()) + ")\nTime: " + sensorTimestamp;
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
  Serial.println(rtcAvailable ? "RTC DS3231 OK (soil temp + clock)" : "RTC not found");

  airTempSensor.begin();
  int deviceCount = airTempSensor.getDeviceCount();
  airTempAvailable = (deviceCount > 0);
  if (airTempAvailable) {
    airTempSensor.setResolution(12);
    Serial.printf("Air temp probe OK on D3 (%d sensor(s))\n", deviceCount);
  } else {
    Serial.println("Air temp probe not found — wire 2-wire probe to D3 + 4.7k to 3V");
  }

  randomSeed(micros());
#if USE_SIMULATED_WATER_LEVEL
  Serial.println("Water level: SIMULATED random 30-50%");
#else
  initWaterLevelPins();
  calibrateWaterSensorDry();
  Serial.println("Water level: L1=D5 L2=D6 L3=D7 L4=D0 | common=G");
#endif

#if THINGESP_ENABLED
  thing.initDevice();
  thing.setCallback(&handleResponse);
  Serial.println("ThingESP enabled for WhatsApp commands.");
#else
  Serial.println("ThingESP disabled — dashboard telemetry only.");
#endif

  readSensors();
  printSensorDebug();
  postTelemetry();
  postCount++;
  lastPost = millis();
  lastWhatsApp = millis();
  lastThingTick = millis();
  lastDebugPrint = millis();

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
    printSensorDebug();
    postTelemetry();
    postCount++;
    lastPost = millis();
  } else if (now - lastDebugPrint >= DEBUG_INTERVAL_MS) {
    readSensors();
    printSensorDebug();
    lastDebugPrint = now;
  }

#if THINGESP_ENABLED
  if (!telemetryBusy && now - lastWhatsApp >= WHATSAPP_INTERVAL_MS) {
    lastWhatsApp = now;
    thing.sendMsg(
      OWNER_PHONE_VALUE,
      "AgriSetu Report\nMoisture: " + String(soilMoisture, 1) +
      "%\nAir: " + String(airTemperature, 1) +
      " C\nWater: " + String(waterLevelPercent) + "% (" +
      String(describeWaterLevel()) + ")"
    );
  }
#endif

  yield();
  delay(10);
}
