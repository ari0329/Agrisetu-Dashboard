# AgriSetu — Smart Farming Assistant

Edge AI–powered field assistant for Indian farms: crop health, pests, nutrients, irrigation, and climate risk — with live IoT sensors and on-device (server-local) intelligence that works with intermittent connectivity.

---

## What it solves (problem statement mapping)

| Requirement | AgriSetu capability |
|---|---|
| Crop health monitoring | Leaf image scan (disease / chlorosis patterns) + ML crop recommendation |
| Pest detection & early warning | Camera-based edge heuristics + farmer alerts |
| Nutrient deficiencies | Leaf color + soil pH advisory |
| Smart irrigation | Moisture / rainfall / ET-proxy → irrigate now / delay / stop |
| Environmental risk | Drought, flood, heat stress, disease-climate scores + yield-risk % |
| Edge AI processing | Vision + advisory run locally (no cloud CV); Arduino → Flask |
| Farmer advisory | Clear actions: irrigate, disease, pest, heat, flood |
| Farm analytics dashboard | Historical moisture, yield-risk trend, disease/pest event counts |
| Scalable deployment | Multi-field selector (`field-1`…), Gunicorn / Render ready |

---

## Features

| Feature | Details |
|---|---|
| Live sensors | Soil moisture, soil temp, water level from Arduino; correlated estimates for others |
| ML crop prediction | Random Forest crop + growth months |
| Edge vision | Pillow color analysis of leaf photos (disease / pest / nutrient flags) |
| Advisory engine | Irrigation schedule hints + environmental risk bars |
| Authentication | Shared MongoDB users collection with bcrypt password verification |
| Dynamic fields | User-owned fields paired to an ESP8266 Device ID |
| Analytics | MongoDB-backed, user-isolated field history |
| PDF report | Downloadable agronomic report |
| UI | Dark biopunk dashboard, Chart.js, mobile-responsive |

---

## File structure

```
AGRISETU/
├── app.py                  # Flask API + dashboard routes
├── advisory.py             # Irrigation, env risk, farmer advisories
├── vision_analyzer.py      # Edge leaf image analysis
├── mongo_store.py          # Users, fields, telemetry, analytics
├── config.py
├── pdf_generator.py
├── thingesp_client.py      # Arduino / Redis sensor store
├── model.py                # ML training pipeline
├── templates/index.html
├── static/css/style.css
├── static/js/dashboard.js
├── models/                 # Trained .pkl files
├── data/                   # Analytics history (auto-created)
├── reports/
├── requirements.txt
└── Procfile
```

---

## Local setup

```bash
python -m venv myenv
# Windows:
myenv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Set MONGODB_URI, SECRET_KEY, DEVICE_ID_PEPPER, and ARDUINO_SECRET

# Train models if needed:
python model.py --data_path smart_agriculture_ml_dataset.xlsx

python app.py
# → http://localhost:10000  (or PORT from .env)
```

Use the same `MONGODB_URI`, database, and `users` collection as the existing
AgriSetu signup service. Passwords in that collection must be bcrypt hashes.
Unknown emails are redirected to `SIGNUP_URL`.

For the ESP8266, copy `arduino_secrets.example.h` to `arduino_secrets.h`,
configure the values, and upload `agrisetu_esp8266.ino`. Pair the exact same
Device ID when adding a field in the dashboard.

The sketch services ThingESP every 200 ms and POSTs telemetry every 5 seconds.
These are separate timers; posting to Render every 200 ms is intentionally
avoided.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard |
| `GET` | `/api/status` | Arduino connection |
| `GET` | `/api/sensor-data` | Live sensors (503 if offline) |
| `POST` | `/api/predict` | Crop ML + full advisory bundle |
| `GET/POST` | `/api/advisory` | Irrigation + env risk + alerts |
| `POST` | `/api/vision` | Leaf image or `demo_profile` |
| `GET` | `/api/analytics` | Field history + yield-risk summary |
| `POST` | `/api/report` | PDF report |
| `POST` | `/api/arduino-data` | Arduino ingest (`X-Arduino-Secret`) |
| `GET` | `/health` | Health check |

### Vision (multipart)
```
POST /api/vision
form-data: image=<file>, field_id=field-1, crop=tomato
```

### Vision demo (no camera)
```json
POST /api/vision
{ "demo_profile": "disease", "field_id": "field-1" }
```
Profiles: `healthy` | `disease` | `pest` | `nutrient`

---

## Notes

- Vision uses **edge color heuristics** (Pillow) so it runs without GPU/cloud. Swap in MobileNet/YOLO later without changing the API shape.
- Predictions / live advisory need Arduino online; vision demos work anytime.
- Install Pillow: included in `requirements.txt`.
- Do not commit secrets (`.env`, Arduino keys).
- `vision_analyzer.py` is independent of crop recommendation training. To enable
  `RandomForest ML`, run `model.py` against the training dataset and deploy the
  generated files from `models/`: `crop_model.pkl`, `label_encoder.pkl`,
  `scaler.pkl`, and optionally `month_model.pkl` and `crop_month_lookup.pkl`.
- Train models outside the Render web process. Validate them with
  `python model.py --demo_only`, then publish the artifacts with the deployment
  (or an artifact store). `/health` reports missing model files and load errors.
