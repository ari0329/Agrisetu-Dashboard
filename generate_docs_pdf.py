"""
Generate AgriSetu full project documentation as PDF.
Usage: python generate_docs_pdf.py
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent / "reports"
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "AgriSetu_Full_Documentation.pdf"

C_GREEN = colors.HexColor("#1B4332")
C_ACCENT = colors.HexColor("#2D6A4F")
C_TEXT = colors.HexColor("#1A2B1E")
C_MUTED = colors.HexColor("#4A6350")


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle", parent=base["Title"],
            fontSize=22, textColor=C_GREEN, alignment=TA_CENTER,
            spaceAfter=6, fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "DocSub", parent=base["Normal"],
            fontSize=11, textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=20,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontSize=16, textColor=C_GREEN, spaceBefore=14, spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontSize=13, textColor=C_ACCENT, spaceBefore=10, spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=10, textColor=C_TEXT, leading=14, spaceAfter=6,
        ),
        "mono": ParagraphStyle(
            "Mono", parent=base["Code"],
            fontSize=9, textColor=C_TEXT, leading=12, spaceAfter=6,
            fontName="Courier", leftIndent=12,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["Normal"],
            fontSize=10, textColor=C_TEXT, leading=13,
            leftIndent=18, bulletIndent=6, spaceAfter=3,
        ),
    }


def table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8F5")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8DEC9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def bullets(story, items, style):
    for item in items:
        story.append(Paragraph(f"• {item}", style))


def main():
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUT_PATH), pagesize=A4,
        rightMargin=1.8 * cm, leftMargin=1.8 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    W = doc.width
    story = []

    # ── Cover ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("AgriSetu Smart Farming Assistant", styles["title"]))
    story.append(Paragraph(
        f"Full Project Documentation · Generated {datetime.now().strftime('%d %B %Y')}",
        styles["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "Edge AI-powered field assistant for Indian farms: crop health, pests, nutrients, "
        "irrigation, environmental risk monitoring, and farm analytics — with live IoT sensors "
        "and on-device intelligence suitable for intermittent connectivity.",
        styles["body"],
    ))
    story.append(PageBreak())

    # ── 1. Overview ────────────────────────────────────────────────────────
    story.append(Paragraph("1. Project Overview", styles["h1"]))
    story.append(Paragraph(
        "AgriSetu is a Flask web application that combines live Arduino sensor data, "
        "Random Forest crop recommendation, edge leaf vision analysis, farmer advisories, "
        "and persisted field analytics into a single responsive dashboard.",
        styles["body"],
    ))
    story.append(Paragraph("Tech Stack", styles["h2"]))
    story.append(table([
        ["Layer", "Technology"],
        ["Backend", "Python 3.11, Flask 3, Gunicorn"],
        ["Frontend", "HTML, CSS, Vanilla JavaScript, Chart.js"],
        ["ML", "scikit-learn Random Forest, joblib, pandas"],
        ["Vision", "Pillow (edge color heuristics)"],
        ["Reports", "ReportLab PDF"],
        ["IoT", "Arduino HTTP POST → /api/arduino-data"],
        ["Storage", "Upstash Redis (optional) or local file; JSON analytics"],
        ["Deploy", "Render / Heroku via Procfile"],
    ], [4 * cm, W - 4 * cm]))

    # ── 2. Architecture ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("2. System Architecture", styles["h1"]))
    story.append(Paragraph(
        "Data flows from field devices to Flask, through processing modules, to the browser dashboard.",
        styles["body"],
    ))
    story.append(Paragraph("Architecture Flow", styles["h2"]))
    bullets(story, [
        "Arduino/ESP8266 POSTs sensor JSON to /api/arduino-data with X-Arduino-Secret header.",
        "thingesp_client.py stores data in Redis (cloud) or /tmp/arduino_data.json (local).",
        "Browser polls /api/status and /api/sensor-data every 5 seconds.",
        "Predict, advisory, and vision APIs combine sensor + ML + edge analysis.",
        "farm_store.py persists analytics snapshots to data/farm_history.json.",
        "pdf_generator.py creates downloadable crop reports.",
    ], styles["bullet"])

    # ── 3. Workflows ───────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("3. Workflows", styles["h1"]))

    story.append(Paragraph("3.1 Live Sensor Monitoring", styles["h2"]))
    bullets(story, [
        "Arduino sends soil_moisture, soil_temperature, water level (L1–L4) every 30–60s.",
        "app.py validates secret, normalizes payload, calls arduino_store.update().",
        "Absent sensors (air temp, humidity, rainfall, light, pH) are estimated from soil data.",
        "If no data for 180 seconds → Arduino marked offline; predict/advisory return 503.",
    ], styles["bullet"])

    story.append(Paragraph("3.2 Crop Prediction + Advisory", styles["h2"]))
    bullets(story, [
        "User clicks Predict → POST /api/predict with sensor_data and optional crop preference.",
        "ML models (if loaded) or rule_predict() fallback recommend crop + growth months.",
        "advisory.py builds irrigation, environmental risk, nutrient, and alert bundle.",
        "Result rendered as confidence gauge + alert cards; snapshot saved to analytics.",
    ], styles["bullet"])

    story.append(Paragraph("3.3 Leaf Vision (Disease / Pest / Nutrient)", styles["h2"]))
    bullets(story, [
        "User uploads leaf photo or clicks Demo (disease/pest/nutrient).",
        "POST /api/vision → vision_analyzer.py runs local Pillow color heuristics.",
        "Returns field health score, disease/pest/nutrient flags, recommendations.",
        "If Arduino online, merged with sensor advisory; works offline via demo profiles.",
    ], styles["bullet"])

    story.append(Paragraph("3.4 Farm Analytics", styles["h2"]))
    bullets(story, [
        "Triggered on predict, advisory refresh, or vision scan.",
        "append_snapshot() saves moisture, yield risk, irrigation action, disease/pest flags.",
        "GET /api/analytics returns averages, event counts, and 24-point trend for charts.",
        "Multi-field support via field_id (field-1, field-2, field-3).",
    ], styles["bullet"])

    story.append(Paragraph("3.5 PDF Report", styles["h2"]))
    bullets(story, [
        "User runs Predict, then clicks Download Report.",
        "POST /api/report → pdf_generator.py creates styled PDF in reports/.",
        "Browser downloads from /reports/<filename>.",
    ], styles["bullet"])

    # ── 4. File reference ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("4. File Reference — Every File Explained", styles["h1"]))

    story.append(Paragraph("4.1 Backend (Python)", styles["h2"]))
    story.append(table([
        ["File", "Purpose"],
        ["app.py", "Main Flask app: all API routes, ML loading, Arduino ingest, orchestration."],
        ["config.py", "Environment config, paths, directory creation from .env."],
        ["thingesp_client.py", "Arduino data store (Redis/file), sensor simulation, connection status."],
        ["advisory.py", "Irrigation, env risk, nutrient advice, farmer alert bundles."],
        ["vision_analyzer.py", "Edge leaf image analysis (disease/pest/nutrient heuristics)."],
        ["farm_store.py", "Analytics persistence in data/farm_history.json."],
        ["pdf_generator.py", "ReportLab crop prediction PDF reports."],
        ["model.py", "Offline ML training pipeline (Random Forest on Excel dataset)."],
        ["live_agrisetu.py", "Legacy serial Arduino script — not part of web dashboard."],
        ["generate_docs_pdf.py", "Generates this documentation PDF."],
    ], [4.2 * cm, W - 4.2 * cm]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("4.2 Frontend", styles["h2"]))
    story.append(table([
        ["File", "Purpose"],
        ["templates/index.html", "Single-page dashboard: sensors, advisory, vision, predict, analytics."],
        ["static/js/dashboard.js", "Polling, charts, predict, vision, advisory, analytics, toasts."],
        ["static/css/style.css", "Dark biopunk UI, responsive layout, component styles."],
    ], [4.2 * cm, W - 4.2 * cm]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("4.3 Config, Data & Deploy", styles["h2"]))
    story.append(table([
        ["File / Folder", "Purpose"],
        ["requirements.txt", "Python dependencies."],
        [".env.example", "Environment variable template."],
        [".env", "Local secrets (gitignored)."],
        [".gitignore", "Ignores venv, models, logs, reports, analytics JSON."],
        [".python-version", "Python 3.11.11 pin."],
        ["Procfile", "Gunicorn start command for Render/Heroku."],
        ["README.md", "Project overview and setup guide."],
        ["models/", "Trained .pkl ML artifacts (gitignored)."],
        ["data/", "Runtime analytics; farm_history.json auto-created."],
        ["reports/", "Generated PDF reports."],
        ["logs/", "Daily app logs agrisetu_YYYYMMDD.log."],
        ["uploads/", "Reserved for future file uploads."],
    ], [4.2 * cm, W - 4.2 * cm]))

    # ── 5. API Reference ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("5. API Reference", styles["h1"]))
    story.append(table([
        ["Route", "Method", "Description"],
        ["/", "GET", "Dashboard UI"],
        ["/api/status", "GET", "Arduino connection status"],
        ["/api/sensor-data", "GET", "Live sensors (503 if offline)"],
        ["/api/predict", "POST", "Crop ML + advisory bundle"],
        ["/api/advisory", "GET/POST", "Irrigation + env risk + alerts"],
        ["/api/vision", "POST", "Leaf image or demo_profile analysis"],
        ["/api/analytics", "GET", "Field history + yield-risk summary"],
        ["/api/report", "POST", "Generate PDF report"],
        ["/reports/<file>", "GET", "Download PDF"],
        ["/api/arduino-data", "POST", "Arduino ingest (X-Arduino-Secret)"],
        ["/health", "GET", "Health check + modules status"],
    ], [3.5 * cm, 2 * cm, W - 5.5 * cm]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Arduino POST Example", styles["h2"]))
    story.append(Paragraph("POST /api/arduino-data", styles["mono"]))
    story.append(Paragraph('Header: X-Arduino-Secret: agrisetu-secret-key-2024', styles["mono"]))
    story.append(Paragraph(
        'Body: {"soil_moisture": 45.2, "soil_temperature": 28.1, "L1":1, "L2":1, "L3":1, "L4":0}',
        styles["mono"],
    ))

    story.append(Paragraph("Vision Demo Example", styles["h2"]))
    story.append(Paragraph('POST /api/vision  {"demo_profile": "disease", "field_id": "field-1"}', styles["mono"]))
    story.append(Paragraph("Profiles: healthy | disease | pest | nutrient", styles["body"]))

    # ── 6. Module details ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("6. Module Details", styles["h1"]))

    story.append(Paragraph("advisory.py Functions", styles["h2"]))
    story.append(table([
        ["Function", "Output"],
        ["assess_irrigation()", "irrigate_now / delay / stop / monitor + urgency"],
        ["assess_environmental_risks()", "Drought, flood, heat, disease-climate scores"],
        ["assess_nutrient_from_ph()", "pH-based nutrient imbalance advice"],
        ["build_farmer_advisories()", "Farmer-facing action cards"],
        ["full_advisory_bundle()", "Complete JSON for APIs"],
    ], [5 * cm, W - 5 * cm]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("dashboard.js Polling", styles["h2"]))
    story.append(table([
        ["Interval", "Action"],
        ["5 seconds", "Connection status + sensor data"],
        ["30 seconds", "Farmer advisory refresh"],
        ["60 seconds", "Farm analytics refresh"],
    ], [3 * cm, W - 3 * cm]))

    # ── 7. Environment variables ───────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("7. Environment Variables", styles["h1"]))
    story.append(table([
        ["Variable", "Default", "Purpose"],
        ["FLASK_ENV", "production", "development enables Flask debug"],
        ["PORT", "10000", "Server port (.env.example uses 5000)"],
        ["SECRET_KEY", "dev default", "Flask session secret"],
        ["ARDUINO_SECRET", "agrisetu-secret-key-2024", "Arduino auth header"],
        ["UPSTASH_REDIS_REST_URL", "—", "Redis for cloud persistence"],
        ["UPSTASH_REDIS_REST_TOKEN", "—", "Redis auth token"],
        ["LOG_LEVEL", "INFO", "Logging verbosity"],
    ], [4.5 * cm, 3.5 * cm, W - 8 * cm]))

    # ── 8. How to run ──────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("8. How to Run", styles["h1"]))
    story.append(Paragraph("Local Setup (Windows PowerShell)", styles["h2"]))
    bullets(story, [
        'cd "C:\\Users\\USER\\OneDrive\\Documents\\Agrisetu Dashboard"',
        "python -m venv myenv",
        "myenv\\Scripts\\activate",
        "pip install -r requirements.txt",
        "copy .env.example .env",
        "python app.py",
        "Open http://localhost:5000 (with .env) or http://localhost:10000 (without .env)",
    ], styles["bullet"])

    story.append(Paragraph("Optional: Train ML Models", styles["h2"]))
    story.append(Paragraph(
        "python model.py --data_path smart_agriculture_ml_dataset.xlsx",
        styles["mono"],
    ))

    story.append(Paragraph("Production (Render/Heroku)", styles["h2"]))
    story.append(Paragraph(
        "gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
        styles["mono"],
    ))

    story.append(Paragraph("What Works Without Arduino", styles["h2"]))
    bullets(story, [
        "Dashboard UI and vision demo buttons (Disease / Pest / Nutrient).",
        "Leaf image upload and edge vision scan.",
        "Analytics (after any prior snapshots exist).",
    ], styles["bullet"])

    story.append(Paragraph("What Requires Arduino", styles["h2"]))
    bullets(story, [
        "Live sensor cards and connection banner (online state).",
        "Predict crop button and Download Report.",
        "Refresh Advice with live irrigation and risk data.",
    ], styles["bullet"])

    # ── 9. Problem statement mapping ───────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("9. Problem Statement Mapping", styles["h1"]))
    story.append(table([
        ["Requirement", "Implementation"],
        ["Crop disease detection", "vision_analyzer.py + /api/vision"],
        ["Pest detection", "vision_analyzer.py + advisory alerts"],
        ["Nutrient deficiency", "Leaf color + pH advisory"],
        ["Smart irrigation", "advisory.py assess_irrigation()"],
        ["Environmental risk", "Drought/flood/heat/disease-climate scores"],
        ["Edge AI", "Local vision + advisory (no cloud CV)"],
        ["Farmer advisory", "Action cards: irrigate, heat, flood, disease"],
        ["Farm analytics", "farm_store.py + /api/analytics"],
        ["IoT sensors", "thingesp_client.py + /api/arduino-data"],
        ["Crop recommendation", "model.py + app.py predict"],
        ["PDF reports", "pdf_generator.py"],
        ["Multi-field scale", "field_id in APIs + UI selector"],
    ], [5.5 * cm, W - 5.5 * cm]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("10. Known Limitations", styles["h1"]))
    bullets(story, [
        "Vision uses color heuristics, not trained CNN — swap for MobileNet/YOLO for production.",
        "No SMS, WhatsApp, or native mobile app — web dashboard only.",
        "No user authentication or multi-tenant database.",
        "PDF confidence in pdf_generator.py is randomized, not from ML model.",
        "live_agrisetu.py is legacy serial script, separate from web app.",
    ], styles["bullet"])

    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_ACCENT))
    story.append(Paragraph(
        "AgriSetu Smart Farming Assistant — End of Documentation",
        styles["subtitle"],
    ))

    doc.build(story)
    print(f"PDF saved: {OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
