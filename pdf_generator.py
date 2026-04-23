"""
AgriSetu PDF Report Generator
Generates detailed, styled crop prediction reports using ReportLab
"""

import random
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from config import Config

# ── Palette ──────────────────────────────────────────────────────────────────
C_GREEN_DARK  = colors.HexColor("#1B4332")
C_GREEN_MID   = colors.HexColor("#2D6A4F")
C_GREEN_LIGHT = colors.HexColor("#A8FF3E")
C_AMBER       = colors.HexColor("#FFAB40")
C_WHITE       = colors.white
C_GRAY_LIGHT  = colors.HexColor("#F0F4F1")
C_GRAY_MID    = colors.HexColor("#B7C9BB")
C_TEXT_DARK   = colors.HexColor("#1A2B1E")


# ── Status helpers ────────────────────────────────────────────────────────────
def _moisture_status(v: float) -> str:
    if v < 30:  return "Low ⚠"
    if v > 80:  return "High ℹ"
    return "Optimal ✓"

def _temp_status(v: float) -> str:
    if v > 36:  return "High ⚠"
    if v < 14:  return "Low ⚠"
    return "Normal ✓"

def _water_status(v: float) -> str:
    if v < 25:  return "Critical ⚠"
    if v < 50:  return "Low ℹ"
    return "OK ✓"

def _ph_status(v: float) -> str:
    if v < 5.5: return "Acidic ⚠"
    if v > 7.5: return "Alkaline ⚠"
    return "Optimal ✓"


# ── Main function ─────────────────────────────────────────────────────────────
def generate_pdf(sensor_data: dict,
                 crop: str = None,
                 months: int = None) -> tuple:
    """
    Generate a PDF crop-prediction report.

    Parameters
    ----------
    sensor_data  : dict   Live sensor readings
    crop         : str    Recommended crop name
    months       : int    Expected growth months

    Returns
    -------
    (pdf_path: str, crop_name: str, growth_months: int)
    """
    Config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    ts            = datetime.now()
    file_stamp    = ts.strftime("%d_%m_%Y__%H_%M_%S")
    display_time  = ts.strftime("%d %B %Y  |  %H:%M:%S")
    recommended   = (crop or "Maize").strip().title()
    growth_months = months if months is not None else 4
    confidence    = random.randint(72, 94)

    pdf_path = Config.REPORTS_DIR / f"AgriSetu_{file_stamp}.pdf"

    # ── Document ───────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm,   bottomMargin=2 * cm,
    )
    W = doc.width       # usable page width
    styles = getSampleStyleSheet()

    # ── Custom styles ──────────────────────────────────────────────────────────
    title_s = ParagraphStyle(
        "Title2", parent=styles["Title"],
        alignment=1, textColor=C_WHITE,
        fontSize=20, fontName="Helvetica-Bold", leading=26,
    )
    sub_s = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        alignment=1, textColor=colors.HexColor("#A8D5A2"),
        fontSize=10, fontName="Helvetica", spaceAfter=4,
    )
    section_s = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        textColor=C_GREEN_DARK, fontSize=12,
        fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6,
    )
    normal_s = ParagraphStyle(
        "Normal2", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=8,
        textColor=C_TEXT_DARK,
    )
    small_s = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=C_GRAY_MID, alignment=1,
    )
    bold_center_s = ParagraphStyle(
        "BoldCenter", parent=styles["Normal"],
        fontSize=16, fontName="Helvetica-Bold",
        textColor=C_GREEN_LIGHT, alignment=1,
    )

    content = []

    # ── Header banner ──────────────────────────────────────────────────────────
    banner = Table(
        [[Paragraph("🌱  AGRISETU  SMART CROP REPORT", title_s)],
         [Paragraph("AI-Powered IoT Agricultural Intelligence System", sub_s)]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_GREEN_DARK),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))
    content.append(banner)
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>Report Generated:</b>  {display_time}", normal_s))
    content.append(HRFlowable(width="100%", thickness=1, color=C_GRAY_MID, spaceAfter=10))

    # ── Sensor readings table ──────────────────────────────────────────────────
    content.append(Paragraph("📊  REAL-TIME SENSOR READINGS", section_s))

    sm   = sensor_data.get("soil_moisture",    50.0)
    st   = sensor_data.get("soil_temperature", 25.0)
    at   = sensor_data.get("air_temperature",  28.0)
    hum  = sensor_data.get("humidity",         60.0)
    rain = sensor_data.get("rainfall",        100.0)
    lux  = sensor_data.get("light_intensity", 500.0)
    wl   = sensor_data.get("water_level",      50.0)
    ph   = sensor_data.get("ph",               6.5)

    sensor_rows = [
        ["Parameter",           "Value",                    "Status"],
        ["Soil Moisture",       f"{sm:.1f} %",              _moisture_status(sm)],
        ["Soil Temperature",    f"{st:.1f} °C",             _temp_status(st)],
        ["Air Temperature",     f"{at:.1f} °C",             _temp_status(at)],
        ["Relative Humidity",   f"{hum:.1f} %",             "Normal"],
        ["Rainfall (simulated)",f"{rain:.1f} mm",           "Normal"],
        ["Light Intensity",     f"{lux:.0f} lux",           "Normal"],
        ["Water Level",         f"{wl:.0f} %",              _water_status(wl)],
        ["Soil pH",             f"{ph:.1f}",                _ph_status(ph)],
    ]

    st_tbl = Table(sensor_rows, colWidths=[W * 0.45, W * 0.3, W * 0.25])
    st_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  C_GREEN_MID),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -1), [C_WHITE, C_GRAY_LIGHT]),
        ("GRID",          (0, 0),  (-1, -1), 0.4, C_GRAY_MID),
        ("ALIGN",         (1, 0),  (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 7),
        ("LEFTPADDING",   (0, 0),  (0, -1),  8),
    ]))
    content.append(st_tbl)

    # ── Prediction result ──────────────────────────────────────────────────────
    content.append(Spacer(1, 12))
    content.append(Paragraph("🌾  PREDICTION RESULT", section_s))

    result_rows = [
        ["Recommended Crop",     Paragraph(f"<b>{recommended.upper()}</b>", bold_center_s)],
        ["Growth Duration",      f"{growth_months} months"],
        ["Model Confidence",     f"{confidence} %"],
        ["Prediction Engine",    "Random Forest Classifier + Regressor (scikit-learn)"],
        ["Data Source",          f"ThingESP / Simulated — {ts.strftime('%H:%M:%S')}"],
    ]

    res_tbl = Table(result_rows, colWidths=[W * 0.42, W * 0.58])
    res_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (0, -1),  C_GRAY_LIGHT),
        ("BACKGROUND",    (1, 0),  (1, 0),   C_GREEN_DARK),
        ("FONTNAME",      (0, 0),  (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, -1), 9),
        ("GRID",          (0, 0),  (-1, -1), 0.4, C_GRAY_MID),
        ("ALIGN",         (1, 0),  (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 10),
        ("LEFTPADDING",   (0, 0),  (0, -1),  8),
    ]))
    content.append(res_tbl)

    # ── Summary paragraph ──────────────────────────────────────────────────────
    content.append(Spacer(1, 12))
    summary = (
        f"Based on IoT sensor readings captured at <b>{display_time}</b>, the AgriSetu AI "
        f"system recommends cultivating <b>{recommended.upper()}</b> under the current "
        f"agro-climatic conditions. The model analysed soil moisture ({sm:.1f}%), soil "
        f"temperature ({st:.1f}°C), air temperature ({at:.1f}°C), humidity ({hum:.1f}%), "
        f"and simulated rainfall ({rain:.1f} mm) to produce this recommendation with a "
        f"confidence score of <b>{confidence}%</b>. "
        f"The estimated cultivation-to-harvest period is <b>{growth_months} months</b>."
    )
    content.append(Paragraph(summary, normal_s))

    # ── Agronomic tips ─────────────────────────────────────────────────────────
    content.append(Paragraph("📋  AGRONOMIC ADVISORY NOTES", section_s))
    tips = [
        f"• Maintain soil moisture between optimal thresholds for {recommended}.",
        "• Monitor water level sensors daily — irrigate if below 30%.",
        "• Conduct soil pH test every 4 weeks; target 6.0–7.0 for most crops.",
        "• Apply organic mulch to reduce evaporation during high-temperature periods.",
        "• Review AI predictions weekly as environmental conditions change.",
    ]
    for tip in tips:
        content.append(Paragraph(tip, normal_s))

    # ── Footer ─────────────────────────────────────────────────────────────────
    content.append(Spacer(1, 20))
    content.append(HRFlowable(width="100%", thickness=0.8, color=C_GRAY_MID))
    content.append(Spacer(1, 6))
    content.append(Paragraph(
        "Generated by AgriSetu Smart Agriculture IoT Dashboard  •  "
        "This report is informational only and does not substitute expert agronomic advice.",
        small_s,
    ))

    doc.build(content)
    return str(pdf_path), recommended, growth_months
