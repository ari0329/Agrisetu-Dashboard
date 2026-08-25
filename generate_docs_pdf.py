"""
AgriSetu visual documentation PDF.
Explains workflows, technology, fields, and why leaf photos are uploaded
(until a field camera is added) using diagrams.

Usage: python generate_docs_pdf.py
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent / "reports"
OUT_DIR.mkdir(exist_ok=True)
OUT_PATH = OUT_DIR / "AgriSetu_Visual_Documentation.pdf"

# Palette
C_GREEN = colors.HexColor("#1B4332")
C_ACCENT = colors.HexColor("#2D6A4F")
C_LIME = colors.HexColor("#A8FF3E")
C_AMBER = colors.HexColor("#E08A1A")
C_SKY = colors.HexColor("#1A7AA8")
C_CORAL = colors.HexColor("#C44B4B")
C_TEXT = colors.HexColor("#1A2B1E")
C_MUTED = colors.HexColor("#4A6350")
C_BG = colors.HexColor("#F3F8F4")
C_BOX = colors.HexColor("#E8F2EA")
C_WHITE = colors.white
C_LINE = colors.HexColor("#2D6A4F")


def build_styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle(
            "Cover", parent=base["Title"], fontSize=26, textColor=C_GREEN,
            alignment=TA_CENTER, spaceAfter=8, fontName="Helvetica-Bold", leading=32,
        ),
        "subtitle": ParagraphStyle(
            "Sub", parent=base["Normal"], fontSize=11, textColor=C_MUTED,
            alignment=TA_CENTER, spaceAfter=10, leading=15,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontSize=16, textColor=C_GREEN,
            spaceBefore=12, spaceAfter=8, fontName="Helvetica-Bold",
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=12.5, textColor=C_ACCENT,
            spaceBefore=10, spaceAfter=5, fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontSize=10, textColor=C_TEXT,
            leading=14, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "caption": ParagraphStyle(
            "Cap", parent=base["Normal"], fontSize=8.5, textColor=C_MUTED,
            alignment=TA_CENTER, spaceBefore=3, spaceAfter=10, fontName="Helvetica-Oblique",
        ),
        "bullet": ParagraphStyle(
            "Bul", parent=base["Normal"], fontSize=10, textColor=C_TEXT,
            leading=13.5, leftIndent=16, bulletIndent=4, spaceAfter=3,
        ),
        "callout": ParagraphStyle(
            "Call", parent=base["Normal"], fontSize=10, textColor=C_GREEN,
            leading=13.5, leftIndent=8, rightIndent=8, spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "Ft", parent=base["Normal"], fontSize=8, textColor=C_MUTED, alignment=TA_CENTER,
        ),
    }


class BoxFlow(Flowable):
    """Horizontal row of rounded boxes with arrows between them."""

    def __init__(self, labels, fills=None, height=42, width=None):
        super().__init__()
        self.labels = labels
        self.fills = fills or [C_BOX] * len(labels)
        self.box_h = height
        self._w = width
        self._h = height + 8

    def wrap(self, availWidth, availHeight):
        self.width = self._w or availWidth
        self.height = self._h
        return self.width, self.height

    def draw(self):
        n = len(self.labels)
        gap = 18
        box_w = (self.width - gap * (n - 1)) / n
        c = self.canv
        y = 4
        for i, (label, fill) in enumerate(zip(self.labels, self.fills)):
            x = i * (box_w + gap)
            c.setFillColor(fill)
            c.setStrokeColor(C_LINE)
            c.setLineWidth(1)
            c.roundRect(x, y, box_w, self.box_h, 6, fill=1, stroke=1)
            c.setFillColor(C_TEXT)
            c.setFont("Helvetica-Bold", 8)
            # wrap label
            words = label.split()
            lines, cur = [], ""
            for w in words:
                test = (cur + " " + w).strip()
                if c.stringWidth(test, "Helvetica-Bold", 8) < box_w - 10:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            start_y = y + self.box_h / 2 + 4 * (len(lines) - 1)
            for li, line in enumerate(lines[:3]):
                c.drawCentredString(x + box_w / 2, start_y - li * 10, line)
            if i < n - 1:
                ax0 = x + box_w + 2
                ax1 = x + box_w + gap - 2
                mid = y + self.box_h / 2
                c.setStrokeColor(C_ACCENT)
                c.setFillColor(C_ACCENT)
                c.setLineWidth(1.4)
                c.line(ax0, mid, ax1 - 5, mid)
                path = c.beginPath()
                path.moveTo(ax1, mid)
                path.lineTo(ax1 - 6, mid + 3.5)
                path.lineTo(ax1 - 6, mid - 3.5)
                path.close()
                c.drawPath(path, fill=1, stroke=0)


class FarmFieldsDiagram(Flowable):
    """Three farm plots + dashboard field dropdown."""

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 168
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Title strip
        c.setFillColor(C_GREEN)
        c.roundRect(0, h - 22, w, 22, 4, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w / 2, h - 15, "WHY THREE FIELDS?  —  One farm can have many plots")

        plots = [
            ("Field 1", "Rice / paddy", "Wetter soil", C_SKY),
            ("Field 2", "Wheat / maize", "Drier soil", C_AMBER),
            ("Field 3", "Vegetables", "Mixed crop", C_ACCENT),
        ]
        pw = (w - 28) / 3
        for i, (name, crop, note, col) in enumerate(plots):
            x = i * (pw + 14)
            y = 58
            c.setFillColor(colors.HexColor("#DCEFDD"))
            c.setStrokeColor(col)
            c.setLineWidth(2)
            c.roundRect(x, y, pw, 78, 8, fill=1, stroke=1)
            # soil strip
            c.setFillColor(col)
            c.rect(x + 6, y + 6, pw - 12, 10, fill=1, stroke=0)
            c.setFillColor(C_GREEN)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x + pw / 2, y + 52, name)
            c.setFont("Helvetica", 8)
            c.setFillColor(C_TEXT)
            c.drawCentredString(x + pw / 2, y + 38, crop)
            c.setFillColor(C_MUTED)
            c.drawCentredString(x + pw / 2, y + 24, note)

        # Dropdown
        c.setFillColor(C_WHITE)
        c.setStrokeColor(C_GREEN)
        c.setLineWidth(1.2)
        c.roundRect(w * 0.22, 8, w * 0.56, 38, 6, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(w / 2, 32, "Dashboard header  →  Field dropdown")
        c.setFont("Helvetica", 8)
        c.setFillColor(C_TEXT)
        c.drawCentredString(w / 2, 16, "Select Field 1 / 2 / 3  →  advice & analytics switch to that plot")

        # arrows from plots to dropdown
        c.setStrokeColor(C_ACCENT)
        c.setLineWidth(1)
        for i in range(3):
            x = i * (pw + 14) + pw / 2
            c.line(x, 58, w / 2, 46)


class CameraNowLater(Flowable):
    """Now: phone upload. Later: field camera."""

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 210
        return self.width, self.height

    def _card(self, x, y, w, h, title, fill, lines):
        c = self.canv
        c.setFillColor(fill)
        c.setStrokeColor(C_LINE)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(x + w / 2, y + h - 16, title)
        c.setFont("Helvetica", 8)
        c.setFillColor(C_TEXT)
        ty = y + h - 32
        for line in lines:
            c.drawCentredString(x + w / 2, ty, line)
            ty -= 12

    def draw(self):
        c = self.canv
        w = self.width
        # header
        c.setFillColor(C_GREEN)
        c.roundRect(0, 188, w, 22, 4, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w / 2, 195, "LEAF VISION  —  Why you upload a photo today")

        cw = (w - 24) / 2
        self._card(
            0, 78, cw, 100, "TODAY  (no camera on the farm)",
            colors.HexColor("#FFF6E5"),
            [
                "Arduino has soil / water sensors only",
                "No leaf camera is connected yet",
                "Farmer takes a photo on the phone",
                "Upload  OR  use Demo buttons",
                "AI still runs on the server (edge-style)",
            ],
        )
        self._card(
            cw + 24, 78, cw, 100, "LATER  (field camera planned)",
            colors.HexColor("#E5F4FF"),
            [
                "Add ESP32-CAM / USB camera on pole",
                "Device captures leaf / canopy photos",
                "POST image to /api/vision automatically",
                "Upload box can stay as backup",
                "Same AI — only the input source changes",
            ],
        )

        # bottom pipeline
        c.setFillColor(C_BOX)
        c.setStrokeColor(C_LINE)
        c.roundRect(0, 6, w, 62, 6, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(w / 2, 52, "Same analysis path either way")
        c.setFont("Helvetica", 8)
        c.setFillColor(C_TEXT)
        steps = ["Photo in", "→", "Color / pattern AI", "→", "Disease · Pest · Nutrient flags", "→", "Farmer advice"]
        c.drawCentredString(w / 2, 28, "   ".join(steps))
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString(w / 2, 14, "Demo buttons work even without Arduino or a real photo")


class SystemArch(Flowable):
    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 195
        return self.width, self.height

    def box(self, x, y, w, h, title, sub, fill):
        c = self.canv
        c.setFillColor(fill)
        c.setStrokeColor(C_LINE)
        c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + w / 2, y + h - 14, title)
        c.setFont("Helvetica", 7)
        c.setFillColor(C_TEXT)
        c.drawCentredString(x + w / 2, y + 10, sub)

    def arrow(self, x0, y0, x1, y1):
        c = self.canv
        c.setStrokeColor(C_ACCENT)
        c.setFillColor(C_ACCENT)
        c.setLineWidth(1.3)
        c.line(x0, y0, x1, y1)

    def draw(self):
        c = self.canv
        w = self.width
        c.setFillColor(C_GREEN)
        c.roundRect(0, 173, w, 22, 4, fill=1, stroke=0)
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w / 2, 180, "SYSTEM MAP  —  From farm to farmer screen")

        bw = (w - 36) / 4
        self.box(0, 95, bw, 68, "1. FIELD", "Arduino + soil probes", colors.HexColor("#E5F4FF"))
        self.box(bw + 12, 95, bw, 68, "2. SERVER", "Flask + AI modules", colors.HexColor("#E8F2EA"))
        self.box(2 * (bw + 12), 95, bw, 68, "3. DASHBOARD", "Browser on phone/PC", colors.HexColor("#FFF6E5"))
        self.box(3 * (bw + 12), 95, bw, 68, "4. FARMER", "Alerts & actions", colors.HexColor("#FDECEC"))

        for i in range(3):
            x0 = (i + 1) * bw + i * 12 - 2
            x1 = (i + 1) * (bw + 12) + 2
            self.arrow(x0, 129, x1, 129)

        # bottom notes
        notes = [
            (0, "Moisture, soil temp,\nwater level (L1–L4)"),
            (bw + 12, "Predict · Advisory\nVision · Analytics"),
            (2 * (bw + 12), "Polls every 5s\nCharts + cards"),
            (3 * (bw + 12), "Irrigate now\nDisease / heat / flood"),
        ]
        c.setFont("Helvetica", 7.5)
        c.setFillColor(C_MUTED)
        for x, text in notes:
            for i, line in enumerate(text.split("\n")):
                c.drawCentredString(x + bw / 2, 72 - i * 11, line)

        c.setFillColor(C_BOX)
        c.setStrokeColor(C_LINE)
        c.roundRect(0, 8, w, 42, 6, fill=1, stroke=1)
        c.setFillColor(C_TEXT)
        c.setFont("Helvetica", 8)
        c.drawCentredString(w / 2, 32, "Phone photo (today)  +  Arduino sensors  →  same Flask server")
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString(w / 2, 16, "Field camera can later replace the photo upload without changing the rest of the system")


class SensorSplit(Flowable):
    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 118
        return self.width, self.height

    def draw(self):
        c = self.canv
        w = self.width
        hw = (w - 16) / 2
        # real
        c.setFillColor(colors.HexColor("#E8F2EA"))
        c.setStrokeColor(C_ACCENT)
        c.roundRect(0, 0, hw, 118, 8, fill=1, stroke=1)
        c.setFillColor(C_GREEN)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(hw / 2, 100, "ON THE ARDUINO  (real)")
        c.setFont("Helvetica", 8)
        c.setFillColor(C_TEXT)
        for i, t in enumerate(["Soil moisture  %", "Soil temperature  °C", "Water level  L1–L4 probes"]):
            c.drawCentredString(hw / 2, 78 - i * 16, t)
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString(hw / 2, 18, "Predict / Advice need these live")

        # estimated
        c.setFillColor(colors.HexColor("#FFF6E5"))
        c.setStrokeColor(C_AMBER)
        c.roundRect(hw + 16, 0, hw, 118, 8, fill=1, stroke=1)
        c.setFillColor(C_AMBER)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(hw + 16 + hw / 2, 100, "NOT ON DEVICE  (estimated)")
        c.setFont("Helvetica", 8)
        c.setFillColor(C_TEXT)
        cx = hw + 16 + hw / 2
        for i, t in enumerate(["Air temp · Humidity", "Rainfall · Light", "Soil pH"]):
            c.drawCentredString(cx, 78 - i * 16, t)
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString(cx, 18, "Filled from soil temp + time of day")


class AdvisoryFlow(Flowable):
    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 125
        return self.width, self.height

    def draw(self):
        c = self.canv
        w = self.width
        items = [
            ("Moisture\n& weather", C_SKY),
            ("Irrigation\nrule engine", C_ACCENT),
            ("Risk scores\ndrought/flood/heat", C_AMBER),
            ("Farmer cards\nIrrigate now…", C_CORAL),
        ]
        n = len(items)
        gap = 14
        bw = (w - gap * (n - 1)) / n
        for i, (label, col) in enumerate(items):
            x = i * (bw + gap)
            c.setFillColor(C_WHITE)
            c.setStrokeColor(col)
            c.setLineWidth(2)
            c.roundRect(x, 28, bw, 90, 8, fill=1, stroke=1)
            c.setFillColor(col)
            c.circle(x + bw / 2, 100, 8, fill=1, stroke=0)
            c.setFillColor(C_WHITE)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(x + bw / 2, 97, str(i + 1))
            c.setFillColor(C_TEXT)
            c.setFont("Helvetica", 8)
            lines = label.split("\n")
            for li, line in enumerate(lines):
                c.drawCentredString(x + bw / 2, 70 - li * 12, line)
            if i < n - 1:
                c.setStrokeColor(C_ACCENT)
                c.setFillColor(C_ACCENT)
                c.setLineWidth(1.3)
                x0, x1 = x + bw + 2, x + bw + gap - 2
                mid = 73
                c.line(x0, mid, x1 - 5, mid)
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(w / 2, 8, "Also uses leaf-scan flags when a photo or demo is run")


class HowToUse(Flowable):
    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        self.height = 150
        return self.width, self.height

    def draw(self):
        c = self.canv
        w = self.width
        steps = [
            ("1", "Open dashboard", "Browser → localhost:5000"),
            ("2", "Pick a Field", "Top-right dropdown"),
            ("3", "Wait for Arduino", "Green banner = live"),
            ("4", "Scan a leaf", "Upload or Demo buttons"),
            ("5", "Read advice", "Irrigate / disease / heat"),
            ("6", "Predict crop", "Then download PDF"),
        ]
        cols = 3
        bw = (w - 20) / cols
        bh = 62
        for i, (num, title, sub) in enumerate(steps):
            col, row = i % cols, i // cols
            x = col * (bw + 10)
            y = 78 - row * (bh + 10)
            c.setFillColor(C_BG)
            c.setStrokeColor(C_LINE)
            c.roundRect(x, y, bw, bh, 7, fill=1, stroke=1)
            c.setFillColor(C_GREEN)
            c.circle(x + 14, y + bh - 16, 9, fill=1, stroke=0)
            c.setFillColor(C_WHITE)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + 14, y + bh - 19, num)
            c.setFillColor(C_GREEN)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(x + 28, y + bh - 20, title)
            c.setFillColor(C_MUTED)
            c.setFont("Helvetica", 7.5)
            c.drawString(x + 28, y + 16, sub)


def table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BG]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8DEC9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_TEXT),
    ]))
    return t


def footer_page(canv, doc):
    canv.saveState()
    canv.setFillColor(C_MUTED)
    canv.setFont("Helvetica", 8)
    canv.drawString(1.8 * cm, 1.1 * cm, "AgriSetu Smart Farming Assistant")
    canv.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"Page {doc.page}")
    canv.setStrokeColor(C_ACCENT)
    canv.setLineWidth(0.6)
    canv.line(1.8 * cm, 1.35 * cm, A4[0] - 1.8 * cm, 1.35 * cm)
    canv.restoreState()


def main():
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUT_PATH), pagesize=A4,
        rightMargin=1.7 * cm, leftMargin=1.7 * cm,
        topMargin=1.6 * cm, bottomMargin=1.8 * cm,
        title="AgriSetu Visual Documentation",
        author="AgriSetu",
    )
    W = doc.width
    story = []

    # COVER
    story.append(Spacer(1, 2.2 * cm))
    story.append(Paragraph("AgriSetu", styles["cover"]))
    story.append(Paragraph("Smart Farming Assistant", styles["cover"]))
    story.append(Paragraph(
        "Visual documentation  ·  Workflows · Technology · Fields · Leaf photos · How to use",
        styles["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=2.2, color=C_ACCENT, spaceAfter=12))
    story.append(Paragraph(
        "A field-deployable assistant for Indian farms: detect crop disease, pests, nutrient stress "
        "and irrigation need early; warn on drought, flood and heat; work with live Arduino sensors "
        "and on-device (server-local) AI even when internet is weak.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(SystemArch())
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%d %B %Y')}  ·  For demo, judges, and team onboarding",
        styles["caption"],
    ))

    # WHAT THE PRODUCT DOES
    story.append(PageBreak())
    story.append(Paragraph("1. What the product does", styles["h1"]))
    story.append(Paragraph(
        "AgriSetu is one dashboard that watches the field and tells the farmer what to do next — "
        "in simple language, not lab reports. Sensors watch soil and water. A leaf photo (today uploaded "
        "from a phone) watches the plant. Rules and ML turn both into actions.",
        styles["body"],
    ))
    story.append(table([
        ["Need on the farm", "What AgriSetu shows"],
        ["Is the crop sick?", "Leaf scan → Possible disease detected"],
        ["Are insects starting?", "Leaf scan → Pest activity increasing"],
        ["Is fertilizer needed?", "Leaf color + soil pH → nutrient flag"],
        ["Should I irrigate?", "Irrigate now / delay / stop + litres hint"],
        ["Weather danger?", "Heat-stress, flood-risk, drought scores"],
        ["Which crop fits this soil?", "Random Forest recommendation + months"],
        ["How is this plot doing over time?", "Analytics chart per Field 1 / 2 / 3"],
    ], [7.5 * cm, W - 7.5 * cm]))

    story.append(Paragraph("2. Technology (simple picture)", styles["h1"]))
    story.append(BoxFlow(
        ["Arduino\nESP8266", "Flask\nPython", "ML +\nRules", "Pillow\nleaf AI", "Chart.js\nUI"],
        [colors.HexColor("#E5F4FF"), C_BOX, colors.HexColor("#FFF6E5"),
         colors.HexColor("#FDECEC"), colors.HexColor("#E8F2EA")],
    ))
    story.append(Paragraph("Data and intelligence stay on your server — no cloud vision API.", styles["caption"]))
    story.append(table([
        ["Layer", "Tools", "Why we use it"],
        ["Language", "Python 3.11", "One language for web, ML, and IoT"],
        ["Web server", "Flask + Gunicorn", "Simple APIs; easy to deploy on Render"],
        ["Screen", "HTML / CSS / JS + Chart.js", "Works on phone browser; no extra app install"],
        ["Crop ML", "scikit-learn Random Forest", "Works on small Excel farm datasets"],
        ["Leaf AI", "Pillow color heuristics", "Runs without GPU or internet to a cloud model"],
        ["Sensors", "Arduino HTTP POST", "Works on farm Wi-Fi / GSM to the PC/server"],
        ["Memory", "Redis or local file + JSON", "Survives restarts; stores field history"],
        ["PDF", "ReportLab", "Farmer can share a printed report"],
    ], [3.2 * cm, 5.2 * cm, W - 8.4 * cm]))

    # FIELDS
    story.append(PageBreak())
    story.append(Paragraph("3. Why there are different Fields — and how to use them", styles["h1"]))
    story.append(Paragraph(
        "A smallholder often has more than one plot: paddy in a low patch, vegetables near the house, "
        "wheat on drier land. Moisture, pests and irrigation advice must not be mixed. AgriSetu stores "
        "history under a field_id: field-1, field-2, field-3. The dropdown in the header is how you switch.",
        styles["body"],
    ))
    story.append(FarmFieldsDiagram())
    story.append(Paragraph(
        "Each plot keeps its own moisture trend, yield-risk, disease and pest event counts.",
        styles["caption"],
    ))
    story.append(Paragraph("How to access a field", styles["h2"]))
    bullets = [
        "Open the dashboard in a browser.",
        "Top-right: Field dropdown — choose Field 1, Field 2 or Field 3.",
        "Leaf scan, Predict, Refresh Advice and analytics all save against that field.",
        "Switch field → charts and event counts reload for the other plot.",
        "You can add more IDs later (cooperatives / more plots) without redesigning the UI.",
    ]
    for b in bullets:
        story.append(Paragraph(f"• {b}", styles["bullet"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        "Today one Arduino feed is shared (the live soil numbers). The field ID still matters so that "
        "leaf photos, predictions and history are not dumped into one mixed list. When you deploy extra "
        "sensor kits, each kit can POST with its own field_id.",
        styles["body"],
    ))

    # LEAF VISION / CAMERA
    story.append(Paragraph("4. Crop Health · Pest · Nutrient — why a picture input?", styles["h1"]))
    story.append(Paragraph(
        "Arduino today measures soil and water. It cannot see a yellow leaf, brown spots, or insect holes. "
        "Disease, pest and nutrient signs are visual. Until a camera module is mounted in the field, "
        "the farmer (or demo user) must give a picture — or tap a Demo button.",
        styles["body"],
    ))
    story.append(CameraNowLater())
    story.append(Paragraph("How to use this section today", styles["h2"]))
    for b in [
        "Option A — Upload: choose a leaf / plant photo from the phone gallery (or take one with the phone camera, then select the file). Click Scan Leaf.",
        "Option B — Demo: Demo Disease / Pest / Nutrient — no photo needed. Use this for presentations when you have no plant in hand.",
        "Results: field health score, three flags (disease, pest, nutrient), and short farmer advice.",
        "If Arduino is online, those flags also merge into the advisory cards (e.g. Possible disease detected).",
    ]:
        story.append(Paragraph(f"• {b}", styles["bullet"]))
    story.append(Paragraph("When the camera sensor is added", styles["h2"]))
    story.append(Paragraph(
        "Plan: ESP32-CAM or similar takes a close-up on a schedule, POSTs to the same /api/vision "
        "endpoint. The upload box stays as a backup for cloudy days, failed cameras, or a farmer "
        "who wants to scan a leaf in the hand. The AI code does not need to be rewritten — only the "
        "source of the image changes.",
        styles["body"],
    ))

    # SENSORS + WORKFLOWS
    story.append(PageBreak())
    story.append(Paragraph("5. Sensors: what is real vs estimated", styles["h1"]))
    story.append(Paragraph(
        "The dashboard shows eight cards. Only three come from the current hardware. The rest are "
        "labelled so nobody thinks a pH probe exists when it does not.",
        styles["body"],
    ))
    story.append(SensorSplit())
    story.append(Paragraph(
        "Live Predict and Refresh Advice stay locked until Arduino posts data (last packet younger than ~3 minutes).",
        styles["caption"],
    ))

    story.append(Paragraph("6. Main workflows (drawn)", styles["h1"]))
    story.append(Paragraph("6.1 Live monitoring", styles["h2"]))
    story.append(BoxFlow(
        ["Arduino POST", "Store Redis/file", "Browser poll 5s", "Sensor cards"],
        [colors.HexColor("#E5F4FF"), C_BOX, colors.HexColor("#FFF6E5"), colors.HexColor("#E8F2EA")],
    ))
    story.append(Paragraph("6.2 Smart irrigation & climate risk", styles["h2"]))
    story.append(AdvisoryFlow())
    story.append(Paragraph("6.3 Crop prediction", styles["h2"]))
    story.append(BoxFlow(
        ["Live sensors", "Random Forest\nor rules", "Crop + months", "PDF report"],
        [C_BOX, colors.HexColor("#FFF6E5"), colors.HexColor("#E8F2EA"), colors.HexColor("#FDECEC")],
    ))
    story.append(Paragraph(
        "If models/*.pkl are missing, AgriSetu still recommends a crop using moisture/temperature rules.",
        styles["caption"],
    ))

    story.append(Paragraph("7. How to use the dashboard (step by step)", styles["h1"]))
    story.append(HowToUse())
    story.append(Paragraph(
        "Vision demos work with Arduino offline. Predict, live advice and PDF need the Arduino online.",
        styles["caption"],
    ))

    # RUN + API
    story.append(PageBreak())
    story.append(Paragraph("8. How to run the project", styles["h1"]))
    story.append(Paragraph(
        "Windows PowerShell, from the AgriSetu Dashboard folder:",
        styles["body"],
    ))
    for b in [
        "python -m venv myenv   then   myenv\\Scripts\\activate",
        "pip install -r requirements.txt",
        "copy .env.example .env   (PORT=5000 is fine)",
        "python app.py",
        "Open http://localhost:5000  (or port 10000 if you skip .env)",
        "Optional: python model.py --data_path smart_agriculture_ml_dataset.xlsx",
    ]:
        story.append(Paragraph(f"• {b}", styles["bullet"]))

    story.append(Paragraph("9. Important APIs (for hardware team)", styles["h1"]))
    story.append(table([
        ["Who", "Call", "Notes"],
        ["Arduino", "POST /api/arduino-data", "Header X-Arduino-Secret; body soil_moisture, soil_temperature, L1–L4"],
        ["Phone upload", "POST /api/vision", "multipart image + field_id"],
        ["Future camera", "POST /api/vision", "Same API — image bytes from ESP32-CAM"],
        ["Demo / judges", "POST /api/vision JSON", '{"demo_profile":"disease"}  etc.'],
        ["Dashboard", "GET /api/sensor-data", "Every 5s; 503 if Arduino silent"],
        ["Dashboard", "GET /api/analytics?field_id=", "History for the selected field"],
    ], [2.8 * cm, 4.2 * cm, W - 7 * cm]))

    story.append(Paragraph("10. Files in one glance", styles["h1"]))
    story.append(table([
        ["File", "Job"],
        ["app.py", "All routes; glues sensors, ML, vision, PDF"],
        ["advisory.py", "Irrigate / delay / heat / flood / nutrient cards"],
        ["vision_analyzer.py", "Leaf photo → disease / pest / nutrient flags"],
        ["farm_store.py", "Per-field history JSON"],
        ["thingesp_client.py", "Arduino store + estimated extra sensors"],
        ["model.py", "Train crop Random Forest (offline)"],
        ["pdf_generator.py", "Farmer crop report PDF"],
        ["templates/index.html", "Screen layout including Field dropdown and photo box"],
        ["static/js/dashboard.js", "Polling, scan, predict, charts"],
        ["live_agrisetu.py", "Old serial COM script — not the web app"],
    ], [4.2 * cm, W - 4.2 * cm]))

    story.append(Paragraph("11. What is ready vs planned", styles["h1"]))
    story.append(table([
        ["Ready now", "Planned / next hardware"],
        ["Soil moisture, soil temp, water level", "Air DHT, rain gauge, pH, NPK probes"],
        ["Phone photo + Demo leaf scan", "ESP32-CAM / Pi camera auto-capture"],
        ["Three logical fields in the UI", "One Arduino kit per physical plot"],
        ["Local Flask AI (no cloud vision)", "Optional SMS when GSM is available"],
        ["Yield-risk trend chart", "Valve / pump auto-irrigation"],
    ], [W / 2, W / 2]))

    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=8))
    story.append(Paragraph(
        "Remember: Fields keep plots separate. Photos exist because the farm camera is not fitted yet — "
        "the Scan Leaf box is the stand-in. Same vision API will serve the camera later.",
        styles["body"],
    ))
    story.append(Paragraph("AgriSetu — End of visual documentation", styles["subtitle"]))

    doc.build(story, onFirstPage=footer_page, onLaterPages=footer_page)
    print(f"PDF saved: {OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
