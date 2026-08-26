#pragma once

// Copy this file to arduino_secrets.h and fill it locally.
// Never commit arduino_secrets.h.
#define WIFI_SSID_VALUE "your-wifi-name"
#define WIFI_PASSWORD_VALUE "your-wifi-password"
#define ARDUINO_SECRET_VALUE "same-value-as-render-ARDUINO_SECRET"
#define DEVICE_ID_VALUE "unique-device-id-used-when-pairing-a-field"

// Dashboard telemetry works without ThingESP.
// Set to 1 only when ThingESP username/project/token are correct on thingesp.com.
// Wrong credentials block WiFi and stop continuous dashboard posts.
#define THINGESP_ENABLED 0

#define THINGESP_USERNAME_VALUE "your-thingesp-username"
#define THINGESP_PROJECT_VALUE "your-thingesp-project"
#define THINGESP_TOKEN_VALUE "your-thingesp-token"
#define OWNER_PHONE_VALUE "+country-code-and-number"
