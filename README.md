# 🌱 AgriSetu — Smart Crop Intelligence Dashboard

A web-based IoT prediction dashboard powered by real-time sensor data and ML.  
No WhatsApp. No login. Just clean, fast, beautiful crop intelligence.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📡 Live Sensors | 8 metrics from ThingESP / ESP8266 (polls every 5 s) |
| 🌾 ML Prediction | Random Forest crop + growth-duration model |
| 📊 Live Charts | Soil moisture & temperature history (Chart.js) |
| 📄 PDF Report | Downloadable ReportLab-generated report |
| 🎨 UI | Dark biopunk, glassmorphism, animated confidence gauge |
| 📱 Responsive | Mobile + Desktop |

---

## 📁 File Structure

```
AGRISETU/
├── app.py                  # Flask REST API (no WhatsApp)
├── config.py               # Environment config
├── pdf_generator.py        # ReportLab PDF generation
├── thingesp_client.py      # IoT sensor fetcher + fallback
├── model.py                # ML training pipeline
├── live_agrisetu.py        # Original serial/local script (legacy)
│
├── templates/
│   └── index.html          # Beautiful dashboard (Jinja2)
│
├── static/
│   ├── css/style.css       # Dark biopunk styles
│   └── js/dashboard.js     # Frontend: polling, charts, predict
│
├── models/                 # Trained .pkl files (git-ignored)
│   ├── crop_model.pkl
│   ├── label_encoder.pkl
│   ├── month_model.pkl
│   ├── crop_month_lookup.pkl
│   └── scaler.pkl
│
├── reports/                # Generated PDFs (auto-created)
├── logs/                   # App logs (auto-created)
│
├── requirements.txt
├── Procfile                # Render / Heroku
├── .env.example
└── README.md
```

---

## 🚀 Local Deployment

### 1. Clone and set up environment

```bash
git clone <your-repo-url>
cd agrisetu

python -m venv myenv
# Windows:
myenv\Scripts\activate
# Mac/Linux:
source myenv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your ThingESP token
```

### 3. Add trained ML models

```bash
# Place your trained .pkl files in the models/ folder:
# crop_model.pkl, label_encoder.pkl, month_model.pkl,
# crop_month_lookup.pkl, scaler.pkl
#
# Or train from scratch:
python model.py --data_path smart_agriculture_ml_dataset.xlsx
```

### 4. Run the app

```bash
# Development
python app.py

# Production (gunicorn)
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

### 5. Open the dashboard

```
http://localhost:5000
```

---

## ☁️ Deploy to Render.com

1. Push to GitHub
2. Create a new **Web Service** on Render
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Add Environment Variables from `.env.example`
6. Upload your `models/*.pkl` files (or train on first run)

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard UI |
| `GET` | `/api/sensor-data` | Live sensor readings JSON |
| `POST` | `/api/predict` | Run crop prediction |
| `POST` | `/api/report` | Generate + return PDF URL |
| `GET` | `/reports/<filename>` | Download PDF |
| `GET` | `/health` | Health check |

### POST `/api/predict` body:
```json
{
  "crop": "wheat",
  "prediction_text": "Expecting dry weather next week",
  "sensor_data": { "soil_moisture": 45.2, "soil_temperature": 24.1, ... }
}
```

### POST `/api/report` body:
```json
{
  "sensor_data": { ... },
  "prediction": { "recommended_crop": "Wheat", "growth_months": 5 }
}
```

---

## 🧠 ML Models (model.py)

Trains two Random Forest models on `smart_agriculture_ml_dataset.xlsx`:

- **Crop Classifier** — 5 sensor features → best crop label
- **Growth Regressor** — same features → months to harvest

```bash
python model.py
# or
python model.py --data_path your_data.xlsx
# Demo without retraining:
python model.py --demo_only
```

---

## ⚠️ Notes

- If ML models are missing, the app auto-falls back to **rule-based prediction**.
- `THINGESP_TOKEN` not set → sensor data is **simulated** (still looks realistic).
- `pyserial` removed from requirements (no longer needed for web deployment).
