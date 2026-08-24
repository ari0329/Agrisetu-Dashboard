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
| Analytics | Persisted field history (`data/farm_history.json`) |
| PDF report | Downloadable agronomic report |
| UI | Dark biopunk dashboard, Chart.js, mobile-responsive |

---

## File structure

```
AGRISETU/
├── app.py                  # Flask API + dashboard routes
├── advisory.py             # Irrigation, env risk, farmer advisories
├── vision_analyzer.py      # Edge leaf image analysis
├── farm_store.py           # Field analytics history
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
# Set ARDUINO_SECRET (and optional UPSTASH Redis for Render)

# Train models if needed:
python model.py --data_path smart_agriculture_ml_dataset.xlsx

python app.py
# → http://localhost:10000  (or PORT from .env)
```

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
