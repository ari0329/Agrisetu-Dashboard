import os
import time
from datetime import datetime

import joblib
import pandas as pd
import serial
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import random


FEATURE_COLUMNS = [
    "Soil_Moisture_%",
    "Soil_Temperature_C",
    "Rainfall_ml",
    "Air_Temperature_C",
    "Humidity_%",
]


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def parse_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=0):
    parsed = parse_float(value, default)
    if parsed is None:
        return default
    return int(round(parsed))


def extract_key_value_payload(raw_line):
    payload = {}
    for item in raw_line.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        payload[key.strip().lower()] = value.strip()
    return payload


def build_sensor_payload(raw_line):
    values = [item.strip() for item in raw_line.split(",") if item.strip()]
    keyed = extract_key_value_payload(raw_line)

    if len(values) < 10 and not keyed:
        raise ValueError(f"Incomplete data received: {values}")

    soil_moisture = parse_float(keyed.get("soil_moisture"))
    if soil_moisture is None and len(values) > 5:
        soil_moisture = parse_float(values[5])

    soil_temperature = parse_float(keyed.get("soil_temp"))
    if soil_temperature is None:
        soil_temperature = parse_float(keyed.get("soil_temperature"))
    if soil_temperature is None and len(values) > 4:
        soil_temperature = parse_float(values[4])

    # MODIFIED: Air temperature is now a random number between 20 and 40
    air_temperature = round(random.uniform(20, 40), 2)

    # MODIFIED: Humidity is now a random number between 0 and 100
    humidity = round(random.uniform(0, 100), 2)

    l1 = parse_int(keyed.get("l1"), 0)
    l2 = parse_int(keyed.get("l2"), 0)
    l3 = parse_int(keyed.get("l3"), 0)
    l4 = parse_int(keyed.get("l4"), 0)

    if not keyed and len(values) > 9:
        l1 = parse_int(values[6], l1)
        l2 = parse_int(values[7], l2)
        l3 = parse_int(values[8], l3)
        l4 = parse_int(values[9], l4)

    if soil_moisture is None or soil_temperature is None:
        raise ValueError(
            "Unable to parse Soil_Moisture_% or Soil_Temperature_C from serial data."
        )

    # MODIFIED: Rainfall_ml is now a random number between 80 and 150
    rainfall = round(random.uniform(80, 150), 2)

    return {
        "Soil_Moisture_%": round(clamp(soil_moisture, 0, 100), 2),
        "Soil_Temperature_C": round(clamp(soil_temperature, -10, 70), 2),
        "Rainfall_ml": rainfall,
        "Air_Temperature_C": air_temperature,
        "Humidity_%": humidity,
    }


def load_models():
    crop_model = joblib.load("crop_model.pkl")
    label_encoder = joblib.load("label_encoder.pkl")
    month_model = joblib.load("month_model.pkl") if os.path.exists("month_model.pkl") else None
    month_lookup = (
        joblib.load("crop_month_lookup.pkl")
        if os.path.exists("crop_month_lookup.pkl")
        else {}
    )
    return crop_model, month_model, label_encoder, month_lookup


def predict_growth_months(crop_name, sample_input, month_lookup, month_model):
    if crop_name in month_lookup:
        return int(month_lookup[crop_name])

    if month_model is None:
        return 0

    predicted = month_model.predict(sample_input)[0]
    return max(1, int(round(predicted)))


try:
    crop_model, month_model, label_encoder, month_lookup = load_models()
except Exception as exc:
    print("Error loading models:", exc)
    raise SystemExit(1)

try:
    ser = serial.Serial("COM5", 9600, timeout=2)
    time.sleep(2)
except Exception as exc:
    print("Serial connection error:", exc)
    raise SystemExit(1)

print("Waiting for data from ESP8266...")

try:
    raw_line = ser.readline()
    if not raw_line:
        print("No data received from ESP8266.")
        raise SystemExit(1)

    line = raw_line.decode("utf-8", errors="ignore").strip()
    print("Raw Data:", line)
    sensor_payload = build_sensor_payload(line)
except Exception as exc:
    print("Serial data processing error:", exc)
    raise SystemExit(1)

sample_input = pd.DataFrame([sensor_payload], columns=FEATURE_COLUMNS)

try:
    predicted_label = crop_model.predict(sample_input)
    recommended_crop = label_encoder.inverse_transform(predicted_label)[0]
    growth_months = predict_growth_months(
        recommended_crop, sample_input, month_lookup, month_model
    )

    print("Recommended Crop:", recommended_crop)
    print("Growth Duration (Months):", growth_months)
except Exception as exc:
    print("Prediction error:", exc)
    raise SystemExit(1)

timestamp = datetime.now()
date_time_str = timestamp.strftime("%d_%m_%Y__%H_%M_%S")
display_time = timestamp.strftime("%d %b %Y | %H:%M:%S")
file_name = f"AgriSetu_{date_time_str}.pdf"

pdf = SimpleDocTemplate(
    file_name,
    pagesize=A4,
    rightMargin=40,
    leftMargin=40,
    topMargin=40,
    bottomMargin=40,
)

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "TitleStyle",
    parent=styles["Title"],
    alignment=1,
    textColor=colors.white,
    fontSize=20,
)
section_style = ParagraphStyle(
    "SectionStyle",
    parent=styles["Heading2"],
    textColor=colors.HexColor("#2E7D32"),
    spaceBefore=16,
    spaceAfter=8,
)
normal_style = ParagraphStyle(
    "NormalStyle",
    parent=styles["Normal"],
    fontSize=11,
    leading=15,
    spaceAfter=10,
)

content = []
header_table = Table(
    [[Paragraph("SMART CROP PREDICTION REPORT - AGRISETU", title_style)]],
    colWidths=[450],
)
header_table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2E7D32")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]
    )
)

content.append(header_table)
content.append(Spacer(1, 20))
content.append(Paragraph(f"<b>Generated On:</b> {display_time}", normal_style))
content.append(Paragraph("INPUT SENSOR DATA", section_style))

sensor_data = [["Parameter", "Value"]]
for col, val in sample_input.iloc[0].items():
    sensor_data.append([col.replace("_", " "), str(val)])

sensor_table = Table(sensor_data, colWidths=[260, 160])
sensor_table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#A5D6A7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]
    )
)
content.append(sensor_table)

content.append(Spacer(1, 18))
content.append(Paragraph("PREDICTION RESULT", section_style))

result_table = Table(
    [
        ["Recommended Crop", recommended_crop],
        ["Expected Growth Duration", f"{growth_months} Months"],
    ],
    colWidths=[260, 160],
)
result_table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F5E9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.green),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]
    )
)
content.append(result_table)
content.append(Spacer(1, 14))

prediction_paragraph = (
    f"Based on the latest sensor readings, the model recommends "
    f"<b>{recommended_crop}</b> as the most suitable crop under the current "
    f"conditions. The estimated growth duration is <b>{growth_months} months</b>."
)
content.append(Paragraph(prediction_paragraph, normal_style))

content.append(Spacer(1, 20))
content.append(
    Paragraph(
        "This report is generated by the AgriSetu Smart Agriculture System.",
        styles["Italic"],
    )
)

pdf.build(content)
print(f"\nPDF report successfully saved as '{file_name}'")