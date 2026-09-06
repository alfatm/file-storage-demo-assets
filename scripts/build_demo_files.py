#!/usr/bin/env python3
"""
Build the `demo/` sample filesystem used to showcase Cloud.

Idempotent: re-running rebuilds every folder it owns (Code, Design, Documents,
Photos, example, Archive, Resources, Shared) and the root demo files. Files in
`demo/` that this script does not know about are left alone.

Sources (cloned/downloaded into DEMO_SRC_DIR, default /tmp/cloud-demo-src):
  - https://github.com/RNKushwaha/sample-files       (binary fixtures)
  - https://github.com/GuglielmoCerri/test-assets    (binary fixtures)
  - https://picsum.photos                             (Unsplash photographs)

Python dependencies:  pip install pillow reportlab openpyxl python-docx

Usage:
  DEMO_SRC_DIR=/some/cache python3 scripts/build_demo_files.py [OUT_DIR]
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zipfile
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "demo"
SRC = Path(os.environ.get("DEMO_SRC_DIR", "/tmp/cloud-demo-src"))
SF = SRC / "sample-files"
TA = SRC / "test-assets"
PICSUM = SRC / "picsum"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

# Dates: root files are pinned to the screenshot, everything else is spread
# over June-July 2026 by a seeded RNG so rebuilds are byte-for-byte stable.
DATE_RANGE_START = date(2026, 6, 1)
DATE_RANGE_END = date(2026, 7, 31)
ROOT_DATES = {
    "README.md": date(2026, 7, 10),
    "mountains.jpg": date(2026, 7, 9),
    "app.ts": date(2026, 7, 8),
    "overview.pdf": date(2026, 7, 7),
    "beach.png": date(2026, 7, 6),
    "UI Design.fig": date(2026, 7, 5),
    "data.csv": date(2026, 7, 5),
    "demo.mp4": date(2026, 7, 3),
}

# Lorem Picsum ids (all Unsplash photos) -> name in Photos/. Formats are mixed
# on purpose so the grid shows jpg / png / webp side by side.
PHOTOS = [
    (1015, "fjord.jpg"), (1016, "canyon-sunset.jpg"), (1018, "highland-road.png"),
    (1019, "storm-clouds.jpg"), (1020, "bear.jpg"), (1021, "misty-forest.webp"),
    (1022, "northern-lights.jpg"), (1024, "eagle.jpg"), (1026, "railway-sunset.jpg"),
    (1028, "dead-trees.webp"), (1029, "central-park.jpg"), (1031, "glass-tower.png"),
    (1033, "subway-hall.jpg"), (1035, "waterfall-rainbow.jpg"), (1036, "snow.jpg"),
    (1037, "pine-ridge.webp"), (1039, "forest-waterfall.jpg"), (1040, "castle.jpg"),
    (1041, "wave.png"), (1043, "yosemite-valley.jpg"), (1044, "mountain-river.jpg"),
    (1045, "cloud-peaks.webp"), (1047, "brick-alley.jpg"), (1048, "skyscrapers.jpg"),
    (1049, "sea-stack.png"), (1050, "coast.jpg"), (1051, "lake.jpg"),
    (1052, "black-sand-beach.webp"), (1053, "ocean-foam.jpg"), (1054, "old-facade.jpg"),
    (1055, "beach-sunset.jpg"), (1056, "clouds.png"), (1057, "coast-road.jpg"),
    (1058, "stadium-aerial.jpg"), (1059, "workshop.webp"), (1060, "coffee-brew.jpg"),
    (1063, "tunnel-aerial.jpg"), (1064, "sea-of-clouds.jpg"), (1065, "old-street.png"),
    (1067, "city-skyline.jpg"), (1070, "vintage-car-interior.jpg"), (1071, "classic-car.jpg"),
    (1072, "rusty-truck.webp"), (1073, "paper-wall.jpg"), (1074, "lioness.jpg"),
    (1075, "cn-tower.jpg"), (1076, "architecture.jpg"), (1077, "cyclists.png"),
    (1078, "city-night.jpg"), (1079, "light-painting.jpg"), (1080, "strawberries.jpg"),
    (1081, "white-building.webp"), (1082, "piano.jpg"), (1083, "boat-aerial.jpg"),
    (1084, "walrus.jpg"),
]
BEACH_ID = 1061
ILLUSTRATION_ID = 1069  # jellyfish, used for Design/illustration.webp
ALL_PICSUM_IDS = [i for i, _ in PHOTOS] + [BEACH_ID, ILLUSTRATION_ID]

rng = random.Random(20260706)


# ---------------------------------------------------------------------------
# Source acquisition
# ---------------------------------------------------------------------------

def ensure_sources() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    for url, dest in (
        ("https://github.com/RNKushwaha/sample-files.git", SF),
        ("https://github.com/GuglielmoCerri/test-assets.git", TA),
    ):
        if not dest.exists():
            print(f"cloning {url}")
            subprocess.run(["git", "clone", "-q", "--depth=1", url, str(dest)], check=True)
    PICSUM.mkdir(exist_ok=True)
    for pid in ALL_PICSUM_IDS:
        dest = PICSUM / f"{pid}.jpg"
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print(f"downloading picsum {pid}")
        urllib.request.urlretrieve(f"https://picsum.photos/id/{pid}/1600/1000", dest)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def reset_dir(p: Path) -> Path:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p


def write_text(p: Path, text: str) -> None:
    p.write_text(text.strip("\n") + "\n", encoding="utf-8")


def copy(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copyfile(src, dst)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def random_date() -> date:
    span = (DATE_RANGE_END - DATE_RANGE_START).days
    return DATE_RANGE_START + timedelta(days=rng.randint(0, span))


def stamp(p: Path, d: date) -> None:
    ts = datetime(d.year, d.month, d.day, rng.randint(8, 18), rng.randint(0, 59)).timestamp()
    os.utime(p, (ts, ts))


# ---------------------------------------------------------------------------
# Document renderers (one content model -> PDF / DOCX / ODT / RTF / MD)
# ---------------------------------------------------------------------------

Section = tuple[str, list[str]]


def write_pdf(p: Path, title: str, subtitle: str, sections: list[Section], accent="#2563eb") -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=8)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor(accent), spaceBefore=6, spaceAfter=10)
    accent_color = colors.HexColor(accent)

    def cover(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(accent_color)
        canvas.rect(0, h - 95 * mm, w, 95 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 34)
        canvas.drawString(22 * mm, h - 55 * mm, title)
        canvas.setFont("Helvetica", 14)
        canvas.drawString(22 * mm, h - 68 * mm, subtitle)
        canvas.setFillColor(colors.HexColor("#111827"))
        canvas.setFont("Helvetica", 11)
        canvas.drawString(22 * mm, h - 115 * mm, "Cloud Demo Workspace")
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(22 * mm, h - 122 * mm, "Internal document · July 2026")
        for i, (heading, _) in enumerate(sections):
            canvas.setFillColor(accent_color)
            canvas.circle(24 * mm, h - (145 + i * 9) * mm + 1.3 * mm, 1.3 * mm, stroke=0, fill=1)
            canvas.setFillColor(colors.HexColor("#374151"))
            canvas.drawString(29 * mm, h - (145 + i * 9) * mm, heading)
        canvas.restoreState()

    def later(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(accent_color)
        canvas.rect(0, h - 6 * mm, w, 6 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#9ca3af"))
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(22 * mm, 12 * mm, f"{title} · Cloud Demo Workspace")
        canvas.drawRightString(w - 22 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(p), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=25 * mm, bottomMargin=22 * mm, title=title, author="Cloud Demo Workspace")
    story = [PageBreak()]
    for i, (heading, paras) in enumerate(sections):
        story.append(Paragraph(heading, h1))
        for para in paras:
            story.append(Paragraph(para, body))
        story.append(Spacer(1, 6 * mm))
        if i % 2 == 1 and i < len(sections) - 1:
            story.append(PageBreak())
    doc.build(story, onFirstPage=cover, onLaterPages=later)


def write_docx(p: Path, title: str, subtitle: str, sections: list[Section], table: list[list[str]] | None = None) -> None:
    import docx

    d = docx.Document()
    d.core_properties.title = title
    d.core_properties.author = "Cloud Demo Workspace"
    d.add_heading(title, 0)
    d.add_paragraph(subtitle).italic = True
    for heading, paras in sections:
        d.add_heading(heading, level=1)
        for para in paras:
            d.add_paragraph(para)
    if table:
        t = d.add_table(rows=len(table), cols=len(table[0]))
        t.style = "Light Grid Accent 1"
        for r, row in enumerate(table):
            for c, cell in enumerate(row):
                t.cell(r, c).text = cell
    d.save(str(p))


def write_odt(p: Path, title: str, sections: list[Section]) -> None:
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body = [f'<text:h text:outline-level="1">{esc(title)}</text:h>']
    for heading, paras in sections:
        body.append(f'<text:h text:outline-level="2">{esc(heading)}</text:h>')
        body.extend(f"<text:p>{esc(x)}</text:p>" for x in paras)
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
        "<office:body><office:text>" + "".join(body) + "</office:text></office:body></office:document-content>"
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        "</manifest:manifest>"
    )
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)


def write_rtf(p: Path, title: str, sections: list[Section]) -> None:
    def esc(s: str) -> str:
        return "".join(c if ord(c) < 128 and c not in "\\{}" else ("\\" + c if c in "\\{}" else f"\\u{ord(c)}?") for c in s)

    out = [r"{\rtf1\ansi\deff0{\fonttbl{\f0\fswiss Helvetica;}}\f0\fs22", r"\pard\qc\b\fs32 " + esc(title) + r"\b0\fs22\par\par"]
    for heading, paras in sections:
        out.append(r"\pard\ql\b\fs26 " + esc(heading) + r"\b0\fs22\par")
        out.extend(r"\pard\ql\sa160 " + esc(x) + r"\par" for x in paras)
    out.append("}")
    p.write_text("\n".join(out), encoding="ascii")


def write_md(p: Path, title: str, sections: list[Section], meta: dict | None = None) -> None:
    lines = [f"# {title}", ""]
    if meta:
        lines += [f"- **{k}:** {v}" for k, v in meta.items()] + [""]
    for heading, paras in sections:
        lines += [f"## {heading}", ""]
        for para in paras:
            lines += [para, ""]
    write_text(p, "\n".join(lines))


def write_html(p: Path, title: str, sections: list[Section]) -> None:
    parts = ["<!doctype html>", "<html lang=\"en\"><head><meta charset=\"utf-8\">", f"<title>{title}</title>",
             "<style>body{font:15px/1.6 system-ui,sans-serif;max-width:820px;margin:40px auto;color:#1f2937}h1{color:#2563eb}code,pre{background:#f3f4f6;padding:2px 6px;border-radius:4px}pre{padding:12px;overflow:auto}</style>",
             "</head><body>", f"<h1>{title}</h1>"]
    for heading, paras in sections:
        parts.append(f"<h2>{heading}</h2>")
        for para in paras:
            parts.append(f"<pre>{para[4:]}</pre>" if para.startswith("    ") else f"<p>{para}</p>")
    parts.append("</body></html>")
    write_text(p, "\n".join(parts))


# ---------------------------------------------------------------------------
# Image generators (UI mocks for Design/)
# ---------------------------------------------------------------------------

def draw_dashboard(p: Path) -> None:
    im = Image.new("RGB", (1600, 1000), "#f5f6fa")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 240, 1000], fill="#111827")
    d.text((28, 32), "Cloud", font=font(28, True), fill="white")
    for i, item in enumerate(["Dashboard", "Files", "Shared", "Search", "Users", "Settings"]):
        y = 110 + i * 48
        if i == 0:
            d.rounded_rectangle([14, y - 10, 226, y + 28], 8, fill="#2563eb")
        d.text((36, y), item, font=font(17), fill="white")
    d.text((280, 36), "Storage overview", font=font(30, True), fill="#111827")
    d.text((280, 80), "Last 30 days · all buckets", font=font(15), fill="#6b7280")
    stats = [("Files stored", "184,203"), ("Storage used", "2.7 TB"), ("Shared links", "1,092"), ("Active users", "318")]
    for i, (label, value) in enumerate(stats):
        x = 280 + i * 320
        d.rounded_rectangle([x, 130, x + 290, 250], 14, fill="white", outline="#e5e7eb")
        d.text((x + 24, 150), label, font=font(15), fill="#6b7280")
        d.text((x + 24, 185), value, font=font(34, True), fill="#111827")
    d.rounded_rectangle([280, 290, 1180, 720], 14, fill="white", outline="#e5e7eb")
    d.text((304, 310), "Uploads per day", font=font(18, True), fill="#111827")
    bars = [rng.randint(30, 100) for _ in range(30)]
    for i, h in enumerate(bars):
        x = 320 + i * 28
        d.rounded_rectangle([x, 690 - h * 3.2, x + 18, 690], 4, fill="#2563eb" if i != 22 else "#f59e0b")
    d.rounded_rectangle([1210, 290, 1560, 720], 14, fill="white", outline="#e5e7eb")
    d.text((1234, 310), "By type", font=font(18, True), fill="#111827")
    pie = [("Images", 42, "#2563eb"), ("Documents", 27, "#10b981"), ("Video", 18, "#f59e0b"), ("Other", 13, "#9ca3af")]
    start = -90
    for label, pct, col in pie:
        d.pieslice([1265, 350, 1505, 590], start, start + pct * 3.6, fill=col)
        start += pct * 3.6
    d.ellipse([1325, 410, 1445, 530], fill="white")
    for i, (label, pct, col) in enumerate(pie):
        d.rectangle([1240, 620 + i * 24, 1254, 634 + i * 24], fill=col)
        d.text((1264, 617 + i * 24), f"{label}  {pct}%", font=font(14), fill="#374151")
    d.rounded_rectangle([280, 750, 1560, 960], 14, fill="white", outline="#e5e7eb")
    d.text((304, 770), "Recent activity", font=font(18, True), fill="#111827")
    rows = ["anna.k uploaded Q3 Roadmap.docx", "team-design shared Brand Guidelines.pdf", "m.rossi created folder Photos/2026-07", "backup job completed (2.1 GB)"]
    for i, r in enumerate(rows):
        d.text((304, 810 + i * 34), r, font=font(15), fill="#374151")
    im.save(p, optimize=True)


def draw_file_browser(p: Path) -> None:
    im = Image.new("RGB", (1600, 1000), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1600, 64], fill="#f9fafb")
    d.line([0, 64, 1600, 64], fill="#e5e7eb")
    d.text((32, 20), "Home  /  Photos  /  2026-07", font=font(17), fill="#374151")
    d.rounded_rectangle([1200, 14, 1560, 50], 8, fill="white", outline="#d1d5db")
    d.text((1216, 22), "Search files…", font=font(15), fill="#9ca3af")
    files = [f for _, f in PHOTOS]
    for i in range(24):
        x, y = 40 + (i % 6) * 255, 100 + (i // 6) * 215
        d.rounded_rectangle([x, y, x + 230, y + 190], 12, fill="#f3f4f6", outline="#e5e7eb")
        thumb = Image.open(PICSUM / f"{PHOTOS[i][0]}.jpg").resize((214, 134))
        im.paste(thumb, (x + 8, y + 8))
        d.text((x + 12, y + 152), files[i], font=font(14), fill="#111827")
    im.save(p, quality=88, optimize=True)


def draw_wireframe(p: Path) -> None:
    im = Image.new("RGB", (1400, 1000), "white")
    d = ImageDraw.Draw(im)
    g = "#9ca3af"
    d.rectangle([40, 40, 1360, 110], outline=g, width=3)
    d.text((60, 62), "LOGO", font=font(22, True), fill=g)
    for i in range(3):
        d.rectangle([1000 + i * 110, 60, 1090 + i * 110, 90], outline=g, width=2)
    d.rectangle([40, 140, 300, 960], outline=g, width=3)
    for i in range(7):
        d.line([70, 190 + i * 60, 270, 190 + i * 60], fill=g, width=3)
    d.rectangle([330, 140, 1360, 220], outline=g, width=3)
    d.text((350, 165), "Breadcrumb  /  search", font=font(20), fill=g)
    for i in range(12):
        x, y = 330 + (i % 4) * 262, 250 + (i // 4) * 240
        d.rectangle([x, y, x + 240, y + 210], outline=g, width=3)
        d.line([x, y, x + 240, y + 150], fill=g, width=2)
        d.line([x + 240, y, x, y + 150], fill=g, width=2)
        d.line([x + 20, y + 180, x + 180, y + 180], fill=g, width=3)
    d.text((40, 975), "Wireframe v3 · file grid · Cloud", font=font(14), fill=g)
    im.save(p, optimize=True)


def draw_thumbnail(size=(400, 300)) -> bytes:
    im = Image.new("RGB", size, "#1e293b")
    d = ImageDraw.Draw(im)
    for i in range(6):
        d.rounded_rectangle([20 + (i % 3) * 125, 30 + (i // 3) * 130, 130 + (i % 3) * 125, 140 + (i // 3) * 130], 10, fill=["#2563eb", "#10b981", "#f59e0b"][i % 3])
    d.text((20, 268), "UI Design · Cloud", font=font(14), fill="white")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def write_fig(p: Path) -> None:
    # Figma's .fig container is a ZIP with a kiwi-encoded canvas.fig, a
    # meta.json and a thumbnail. The canvas payload here is a stand-in with the
    # real "fig-kiwi" magic so type sniffers recognise it; Figma itself will
    # not open it.
    canvas = b"fig-kiwi" + (0).to_bytes(4, "little") + (20).to_bytes(4, "little")
    canvas += zlib.compress(b"cloud-demo-schema" * 40) + zlib.compress(b"UI Design canvas placeholder " * 400)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("canvas.fig", canvas)
        z.writestr("meta.json", json.dumps({"client_meta": {"background_color": {"r": 0.96, "g": 0.96, "b": 0.96, "a": 1}, "thumbnail_size": {"width": 400, "height": 300}}, "file_name": "UI Design", "version": 3}))
        z.writestr("thumbnail.png", draw_thumbnail())


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FIRST = ["Anna", "Marco", "Elena", "Tom", "Sofia", "Lucas", "Mia", "Noah", "Ivan", "Chloe", "Liam", "Zara", "Omar", "Nina", "Felix", "Ava", "Jonas", "Lea", "Hugo", "Emma", "Andrei", "Maya", "Diego", "Sara", "Kai", "Iris", "Milan", "Julia", "Arjun", "Petra"]
LAST = ["Kowalski", "Rossi", "Petrova", "Schmidt", "Andersen", "Costa", "Nakamura", "Novak", "Fischer", "Georgiou", "Silva", "Dubois", "Hansen", "Ivanov", "Moreau", "Larsen", "Weber", "Christou", "Berg", "Popescu", "Martin", "Okafor", "Lindqvist", "Ferrari", "Horvat", "Baker", "Meyer", "Nilsson", "Papadopoulos", "Kim"]
COMPANIES = ["Northwind Labs", "Acme Cloud", "Brightline Media", "Helios Analytics", "Kestrel Logistics", "Orbit Studio", "Pinecone Health", "Quartz Financial", "Redwood Robotics", "Solstice Energy", "Tidewater Shipping", "Vanta Security", "Willow Learning", "Zephyr Travel", "Lumen Retail"]
DEPARTMENTS = ["Engineering", "Design", "Marketing", "Sales", "Finance", "Support", "Operations", "Legal", "HR", "Product"]
COUNTRIES = ["Germany", "Cyprus", "Netherlands", "Poland", "Italy", "Spain", "France", "Sweden", "Portugal", "Greece", "United Kingdom", "Ireland", "Austria", "Czechia", "Denmark", "Norway", "Finland", "Estonia", "Latvia", "Lithuania", "United States", "Canada", "Japan", "Australia", "Brazil"]
STATUSES = ["active", "active", "active", "active", "invited", "suspended", "inactive"]


def fake_person(i: int) -> dict:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    company = rng.choice(COMPANIES)
    domain = company.lower().replace(" ", "") + ".example"
    created = date(2024, 1, 1) + timedelta(days=rng.randint(0, 900))
    last_login = created + timedelta(days=rng.randint(0, max(1, (date(2026, 7, 10) - created).days)))
    return {
        "id": i, "name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}{i % 97 if i % 5 == 0 else ''}@{domain}",
        "company": company, "department": rng.choice(DEPARTMENTS), "country": rng.choice(COUNTRIES),
        "status": rng.choice(STATUSES), "created_at": created.isoformat(),
        "storage_used": rng.randint(1_000_000, 90_000_000_000), "last_login": last_login.isoformat(),
    }


def write_users_csv(p: Path, n: int) -> None:
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "email", "company", "department", "country", "status", "created_at", "storage_used", "last_login"])
        w.writeheader()
        for i in range(1, n + 1):
            w.writerow(fake_person(i))


def write_xlsx(p: Path, sheets: dict[str, list[list]]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2563EB")
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(12, min(40, max(len(str(c.value or "")) for c in col) + 2))
    wb.save(str(p))


def write_sqlite(p: Path) -> None:
    if p.exists():
        p.unlink()
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, country TEXT, status TEXT, created_at TEXT);
        CREATE TABLE folders (id INTEGER PRIMARY KEY, owner_id INTEGER REFERENCES users(id), path TEXT NOT NULL);
        CREATE TABLE files (id INTEGER PRIMARY KEY, folder_id INTEGER REFERENCES folders(id), name TEXT NOT NULL, size INTEGER, mime TEXT, modified_at TEXT);
        CREATE TABLE shares (id INTEGER PRIMARY KEY, file_id INTEGER REFERENCES files(id), token TEXT UNIQUE, expires_at TEXT, downloads INTEGER DEFAULT 0);
        CREATE INDEX files_name ON files(name);
    """)
    people = [fake_person(i) for i in range(1, 121)]
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", [(x["id"], x["name"], x["email"], x["country"], x["status"], x["created_at"]) for x in people])
    folders = [(i, rng.randint(1, 120), rng.choice(["/Documents", "/Photos", "/Design", "/Code", "/Shared", "/Archive"]) + (f"/{rng.randint(2024, 2026)}" if i % 3 == 0 else "")) for i in range(1, 201)]
    con.executemany("INSERT INTO folders VALUES (?,?,?)", folders)
    mimes = [("jpg", "image/jpeg"), ("png", "image/png"), ("pdf", "application/pdf"), ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), ("md", "text/markdown"), ("zip", "application/zip"), ("mp4", "video/mp4")]
    words = ["report", "invoice", "roadmap", "photo", "backup", "notes", "design", "spec", "budget", "summary"]
    files = []
    for i in range(1, 1501):
        ext, mime = rng.choice(mimes)
        files.append((i, rng.randint(1, 200), f"{rng.choice(words)}-{rng.randint(1, 999):03d}.{ext}", rng.randint(2_000, 50_000_000), mime, random_date().isoformat()))
    con.executemany("INSERT INTO files VALUES (?,?,?,?,?,?)", files)
    con.executemany("INSERT INTO shares VALUES (?,?,?,?,?)", [(i, rng.randint(1, 1500), f"{rng.getrandbits(64):016x}", (date(2026, 7, 1) + timedelta(days=rng.randint(1, 120))).isoformat(), rng.randint(0, 250)) for i in range(1, 301)])
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Text fixtures (documents, code)
# ---------------------------------------------------------------------------

def para_block(*sentences: str) -> str:
    return " ".join(sentences)


DOCS: dict[str, dict] = {
    "Storage Architecture": {
        "subtitle": "How Cloud persists, replicates and serves files",
        "sections": [
            ("Overview", [
                "This storage architecture document describes the layered design behind the Cloud file service. Files are addressed by a stable content identifier, metadata lives in a relational store, and the bytes themselves are written to one or more pluggable backends.",
                "The design goal is that any backend can be swapped without changing the API surface. The same request path handles a local disk on a laptop, an S3 bucket in production and a WebDAV mount in a customer data centre.",
            ]),
            ("Backends", [
                "The primary production backend is S3-compatible object storage. Uploads are chunked into 8 MiB parts and committed with a multipart completion call, which lets interrupted uploads resume from the last confirmed part.",
                "The WebDAV backend exists for customers with existing NAS infrastructure. It maps folder operations one-to-one onto PROPFIND, MKCOL and MOVE requests and caches directory listings for thirty seconds.",
                "Local filesystem storage is used for development and for small single-node installations. Paths are canonicalised before every operation so that symlinks cannot escape the configured root.",
            ]),
            ("Metadata", [
                "Every file has a row in the files table that records its size, checksum, MIME type and the backend key where the bytes live. Folder hierarchy is a materialised path column, which keeps listing a folder to a single indexed range scan.",
                "Thumbnails and text extractions are stored as derived artefacts next to the original object under a derived/ prefix and are regenerated when the source checksum changes.",
            ]),
            ("Replication and durability", [
                "Objects written to S3 rely on the provider's cross-zone replication. Local and WebDAV installations run a nightly rsync job that mirrors the storage root to a secondary volume and verifies checksums for a random one percent sample.",
                "Deletes are soft for fourteen days. A background sweeper removes the underlying object once the retention window has passed and no share link still references the file.",
            ]),
        ],
    },
    "Security Review": {
        "subtitle": "Findings from the July 2026 internal review",
        "sections": [
            ("Scope", [
                "The review covered authentication, authorisation, share-link handling and the upload pipeline of the Cloud web application and its HTTP API. Infrastructure hardening of the hosting provider was out of scope.",
            ]),
            ("Authentication", [
                "Interactive sessions use HTTP-only cookies rotated on every privilege change. Password authentication enforces a minimum of twelve characters and checks candidates against a breached-password list before accepting them.",
                "Programmatic access uses long-lived API tokens scoped to a folder prefix. Tokens are stored hashed, shown to the user only once, and can be revoked from the account page. We recommend adding an expiry date to every new token by default.",
                "Two-factor authentication via TOTP is available but not enforced for administrators. Enforcing it for the admin role is the highest-priority recommendation of this review.",
            ]),
            ("Share links", [
                "Share links carry a 128-bit random token and can be protected with a PIN, an expiry and a maximum download count. Brute-force attempts against the PIN are rate limited per link and per source address.",
            ]),
            ("Uploads", [
                "Uploaded files are stored with the declared name but served with a MIME type derived from content sniffing, and HTML uploads are always delivered as attachments. SVG previews are rendered inside a sandboxed iframe with scripts disabled.",
            ]),
            ("Recommendations", [
                "Enforce two-factor authentication for administrators, default API tokens to a ninety-day expiry, and add an audit log entry for every share-link creation. All three items are tracked in the Q3 roadmap.",
            ]),
        ],
    },
    "Engineering Handbook": {
        "subtitle": "How the Cloud team builds and ships software",
        "sections": [
            ("Working agreements", ["We ship small changes behind feature flags, review every pull request within one working day and keep the main branch releasable at all times. Incidents are blameless and every one of them ends with a written report."]),
            ("Code review", ["Reviews focus on correctness, clarity and test coverage, in that order. Style is enforced by tooling so that humans do not spend review time on formatting. A reviewer who requests changes owns the follow-up conversation."]),
            ("Releases", ["Releases are cut every two weeks from main. Release notes are written by the engineers who shipped the work and are published to the Documents folder together with the migration checklist."]),
            ("On-call", ["The on-call rotation is weekly. The primary responder acknowledges pages within fifteen minutes and escalates after thirty. Every page must map to a runbook, and every runbook lives in the Shared folder."]),
        ],
    },
    "Quarterly Report Q2 2026": {
        "subtitle": "Financial and operational summary for April to June 2026",
        "sections": [
            ("Highlights", ["Quarterly revenue grew 18 percent quarter over quarter to 4.2 million, cloudn by the enterprise tier and the new Cyprus and Netherlands regions. Net retention stayed above 115 percent for the third consecutive quarter."]),
            ("Revenue", ["Subscription revenue accounted for 91 percent of the total. Professional services contributed the remainder, mostly from migration projects moving customers off legacy WebDAV shares onto managed S3 storage."]),
            ("Costs", ["Storage costs per terabyte fell 9 percent after the move to tiered object storage. Headcount grew by six, mostly in support and solutions engineering."]),
            ("Outlook", ["We expect quarterly revenue to reach 4.8 million in Q3 on the back of the sharing features and the Cyprus office opening. Risks include currency exposure and slower enterprise procurement over the summer."]),
        ],
    },
    "Onboarding Guide": {
        "subtitle": "Your first two weeks at Cloud",
        "sections": [
            ("Day one", ["Collect your laptop, join the team channels and read the Engineering Handbook. Your onboarding buddy will walk you through the local development setup and the demo workspace."]),
            ("Week one", ["Pick a starter issue from the board, ship it behind a feature flag and write a short note about what surprised you. Sit in on at least one customer call with the support team."]),
            ("Week two", ["Join the on-call shadow rotation and read the last three incident reports. Meet with product to review the project roadmap and understand which epics you will be contributing to."]),
        ],
    },
    "Vendor Agreement": {
        "subtitle": "Master services agreement with Northwind Labs",
        "sections": [
            ("Parties", ["This agreement is made between Cloud Demo Workspace and Northwind Labs, a provider of object storage and content delivery services."]),
            ("Services", ["The vendor provides S3-compatible object storage in the eu-central and eu-south regions, with a 99.95 percent monthly availability commitment and eleven nines of durability."]),
            ("Fees", ["Fees are invoiced monthly in arrears. Each invoice is due within thirty days and disputes must be raised within fifteen days of receipt."]),
            ("Term", ["The initial term is twenty-four months starting 1 August 2026 and renews automatically for twelve-month periods unless either party gives ninety days notice."]),
        ],
    },
    "Product Requirements": {
        "subtitle": "Cloud 2.0 sharing and collaboration",
        "sections": [
            ("Problem", ["Customers share files by downloading them and attaching them to email. This loses version history and bypasses access controls. We need first-class sharing inside Cloud."]),
            ("Goals", ["Share any file or folder with a link, an internal user or a group. Control expiry, PIN and download limits. Show who accessed a shared file and when."]),
            ("Non-goals", ["Real-time co-editing of documents is out of scope for this release. Public commenting on shared files is deferred to a later milestone."]),
            ("Requirements", ["Links must be revocable instantly. Shared folders must respect the permissions of the sharer. Every access must be recorded in the audit log with source address and user agent."]),
            ("Success metrics", ["Forty percent of active workspaces create at least one share link per week within two months of launch. Support tickets about email attachments drop by half."]),
        ],
    },
    "Q3 Roadmap": {
        "subtitle": "Project roadmap for July to September 2026",
        "sections": [
            ("Themes", ["The Q3 project roadmap has three themes: sharing, search and security. Each theme has an owner, a target release and a measurable outcome."]),
            ("Sharing", ["Ship share links with PIN and expiry in July, group sharing in August and access reports in September."]),
            ("Search", ["Roll out full-text content search for PDF, DOCX and Markdown, then extend it to spreadsheets. Index rebuilds must finish within one hour for a workspace of one million files."]),
            ("Security", ["Enforce two-factor authentication for administrators, expire API tokens by default and finish the recommendations from the July security review."]),
        ],
        "table": [["Milestone", "Owner", "Target"], ["Share links", "Anna Kowalski", "2026-07-24"], ["Content search", "Marco Rossi", "2026-08-21"], ["2FA enforcement", "Elena Petrova", "2026-09-11"], ["Access reports", "Tom Schmidt", "2026-09-25"]],
    },
    "Migration Plan": {
        "subtitle": "Moving legacy WebDAV shares to managed object storage",
        "sections": [
            ("Summary", ["This migration plan moves the remaining 38 customer workspaces from self-hosted WebDAV shares to managed S3 storage without downtime for end users."]),
            ("Phases", ["Phase one inventories every share and estimates transfer time. Phase two runs a read-only mirror to S3 and verifies checksums. Phase three flips the workspace backend and keeps the WebDAV share as a fallback for two weeks."]),
            ("Risks", ["Large workspaces above ten terabytes may need a physical transfer appliance. Files with names that are invalid object keys are renamed and the mapping is stored in the migration log."]),
            ("Rollback", ["Because the WebDAV share stays untouched during phase two and three, rollback is a configuration change that points the workspace back at the original backend."]),
        ],
        "table": [["Phase", "Start", "End"], ["Inventory", "2026-07-06", "2026-07-17"], ["Mirror", "2026-07-20", "2026-08-14"], ["Cutover", "2026-08-17", "2026-08-28"]],
    },
    "User Research": {
        "subtitle": "Interviews with twelve workspace administrators",
        "sections": [
            ("Method", ["We ran twelve remote interviews of forty-five minutes each with administrators of workspaces between fifty and two thousand users."]),
            ("Findings", ["Administrators want to see storage per department, not per user. Search is used mostly to find a file whose name they have forgotten, so content search matters more than filename search. Share links are created mostly from mobile devices."]),
            ("Quotes", ["\"I do not care about folders, I care about finding the invoice from last March.\" \"If I could see who opened the link I would stop asking people to confirm by email.\""]),
            ("Next steps", ["Prototype a department storage report and test the mobile share flow with five of the interviewed administrators."]),
        ],
    },
    "Project Proposal": {
        "subtitle": "Desktop sync client for Cloud",
        "sections": [
            ("Proposal", ["Build a lightweight desktop client that keeps a local folder in sync with a Cloud workspace, using the existing multipart upload API and a change feed."]),
            ("Scope", ["Windows, macOS and Linux. Selective sync per folder. Conflict resolution keeps both versions and marks the newer one."]),
            ("Estimate", ["Two engineers for one quarter for a beta, plus one engineer ongoing for maintenance. Infrastructure cost is dominated by the change feed, estimated at 400 per month at current scale."]),
        ],
    },
    "Cyprus Office Expansion": {
        "subtitle": "Opening the Limassol engineering hub",
        "sections": [
            ("Background", ["Cloud is opening an engineering office in Limassol, Cyprus, in September 2026. The office will host the search and storage teams and act as the base for customers in Greece, Cyprus and the Middle East."]),
            ("Plan", ["Lease a 300 square metre office in the Limassol marina district, hire eight engineers in the first year and relocate two team leads from Berlin. Cyprus company registration completes in August."]),
            ("Budget", ["Fit-out and first-year lease are estimated at 260 thousand. Salaries and relocation add 780 thousand in the first year. The Cyprus IP box regime is expected to offset part of the cost."]),
        ],
    },
    "Invoice INV-2026-0142": {
        "subtitle": "Invoice for professional services, June 2026",
        "sections": [
            ("Invoice details", ["Invoice number INV-2026-0142 issued on 30 June 2026 to Helios Analytics for migration services performed in June 2026. Payment is due within thirty days by bank transfer."]),
            ("Line items", ["Migration assessment, 16 hours at 150 per hour. Data transfer and verification of 4.2 terabytes at 45 per terabyte. Post-migration support retainer, one month."]),
            ("Totals", ["Subtotal 3,789.00, VAT at 19 percent 719.91, total due 4,508.91. Please quote the invoice number on your payment."]),
        ],
        "table": [["Item", "Qty", "Unit", "Amount"], ["Migration assessment", "16", "150.00", "2,400.00"], ["Data transfer", "4.2 TB", "45.00", "189.00"], ["Support retainer", "1", "1,200.00", "1,200.00"], ["Total (incl. VAT)", "", "", "4,508.91"]],
    },
    "Data Retention Policy": {
        "subtitle": "Retention and deletion rules for workspace data",
        "sections": [
            ("Purpose", ["This policy defines how long Cloud keeps files, metadata, audit logs and backups, and how deletion requests are honoured."]),
            ("Retention periods", ["Deleted files are recoverable for fourteen days. Audit logs are kept for one year. Backups are rotated after ninety days. Share-link access records are anonymised after six months."]),
            ("Deletion requests", ["Workspace administrators can request full deletion. All objects, derived artefacts and backups are removed within thirty days and a deletion certificate is issued."]),
        ],
    },
    "Board Minutes": {
        "subtitle": "Minutes of the board meeting held on 2 July 2026",
        "sections": [
            ("Attendance", ["All five board members attended. The chief financial officer presented the Q2 quarterly revenue figures and the Cyprus expansion budget."]),
            ("Decisions", ["The board approved the Limassol office lease and the vendor agreement with Northwind Labs. The desktop sync client proposal was deferred to the September meeting."]),
            ("Actions", ["Finance to finalise the Cyprus budget by 15 July. Engineering to present the security review follow-up in September."]),
        ],
    },
    "Legal Notice": {
        "subtitle": "Terms applying to the Cloud demo workspace",
        "sections": [
            ("Notice", ["The files in this workspace are sample data created for product demonstration. Names, companies and email addresses are fictional and any resemblance to real persons is coincidental."]),
            ("Licensing", ["Photographs are sourced from Unsplash via Lorem Picsum under the Unsplash licence. Binary fixtures come from openly licensed sample-file repositories."]),
            ("Contact", ["Questions about this material can be sent to the workspace administrator."]),
        ],
    },
    "Project Plan": {
        "subtitle": "Content search rollout, July to September 2026",
        "sections": [
            ("Objective", ["Deliver full-text content search across PDF, DOCX, Markdown and spreadsheet files for every workspace, following the project roadmap agreed in June."]),
            ("Workstreams", ["Extraction pipeline, index service, query API and the search UI. Each workstream has a named owner and a weekly checkpoint in the Team Notes."]),
            ("Timeline", ["Extraction in July, indexing in early August, UI and beta in late August, general availability in September."]),
            ("Risks", ["Large PDF scans without a text layer need OCR, which is out of scope for the first release. Index size for image-heavy workspaces is still being measured."]),
        ],
    },
    "Brand Guidelines": {
        "subtitle": "Cloud design system, colour, type and logo usage",
        "sections": [
            ("Design system", ["The Cloud design system is built around a compact eight-point spacing grid, a single sans-serif typeface and a restrained palette. Every component in the web application is derived from these tokens."]),
            ("Colour", ["Primary blue 2563EB is used for actions and selection. Green 10B981 signals success, amber F59E0B warnings, and the neutral scale from F9FAFB to 111827 carries all text and surfaces."]),
            ("Typography", ["Headings use the bold weight at 24, 18 and 15 pixels. Body text is 14 pixels with a 1.5 line height. Monospace is reserved for code previews and file paths."]),
            ("Logo", ["The logo is a folded-corner square with a bold F. Keep clear space equal to the height of the F on all sides and never place it on a busy photograph without the white container."]),
        ],
    },
    "Product Overview": {
        "subtitle": "A file manager for teams that live in the browser",
        "sections": [
            ("Product Overview", ["Cloud is a self-hosted file manager that gives teams a fast, familiar way to browse, preview, search and share files from any storage backend. It runs as a single service and embeds into existing web applications as a component."]),
            ("File Storage", ["Connect local disks, S3-compatible object storage or WebDAV shares and present them as one workspace. Uploads are resumable and large files are streamed without buffering on the server."]),
            ("Search", ["Find files by name, type, date or content. Text is extracted from PDF, Office and Markdown documents and indexed incrementally, so results reflect changes within seconds."]),
            ("Sharing", ["Create share links with a PIN, an expiry date and a download limit. See who opened a link and revoke it in one click. Internal sharing respects the permissions of the person who shared."]),
            ("Security", ["Sessions, API tokens and share links are all scoped and revocable. Two-factor authentication, audit logging and content sniffing protect the workspace against the most common threats."]),
            ("Integrations", ["Embed the file browser as a web component, a React component or a Vue component. Automate with the HTTP API, or mount a workspace over WebDAV from any operating system."]),
        ],
    },
}


README_ROOT = """
# Cloud Demo Workspace

This workspace is a realistic, self-contained sample filesystem for showing off
a cloud file manager: browsing, previews, thumbnails, content search and
sharing. Every file is a real, decodable file of its type.

## What is inside

| Folder        | Contents                                                     |
|---------------|--------------------------------------------------------------|
| `Code/`       | A small TypeScript / Python / Go service with its config      |
| `Design/`     | Mockups, a logo, an illustration, a PSD source and brand PDF  |
| `Documents/`  | PDF, DOCX, ODT, RTF, HTML, Markdown and text documents        |
| `Photos/`     | 56 photographs in JPG, PNG and WebP                           |
| `example/`    | The three tiny files used in the quick-start tutorial         |
| `Archive/`    | ZIP, TAR, 7z, gzip, bzip2, xz and other archive formats       |
| `Resources/`  | Spreadsheets, JSON, YAML, XML, SQLite, vCard and iCalendar    |
| `Shared/`     | Files shared with the whole team                              |

The root also holds a few files that make a nice first screen: a mountain
photo, a beach photo, a short video, a product overview PDF, a Figma file,
a CSV with a few thousand fake users and this README.

## Things to try

- **Grid view.** Open `Photos/` and switch to the grid. Thumbnails are
  generated on first view and cached next to the original object.
- **Previews.** Click `overview.pdf`, `app.ts`, `demo.mp4` or `data.csv`.
  Each one opens in a preview that matches the file type.
- **Content search.** Search for `storage architecture`, `authentication`,
  `S3`, `WebDAV`, `API token`, `migration plan`, `project roadmap`, `invoice`,
  `design system`, `Cyprus` or `quarterly revenue`. Each term lives in a
  different document, so results should point at different files.
- **Sharing.** Right-click `Shared/Project Plan.pdf` and create a share link
  with a PIN and an expiry date.
- **Archives.** Open `Archive/project-backup.zip` to browse it in place.

## Data

All people, companies, invoices and figures are fictional. Photographs come
from Unsplash via Lorem Picsum. Binary fixtures for exotic formats come from
the open `sample-files` and `test-assets` repositories on GitHub.

## Rebuilding

The dataset is generated by `scripts/build_demo_files.py`. Rebuilding is
deterministic: the same script produces the same names, contents and dates.

```bash
pip install pillow reportlab openpyxl python-docx
python3 scripts/build_demo_files.py
```

## Usage

Mount or copy this directory into the storage root of a demo file manager.
"""

APP_TS = """
/**
 * Minimal client for the Cloud HTTP API.
 * Handles authentication, folder listing, uploads, downloads and search.
 */

export interface FileEntry {
  path: string;
  name: string;
  size: number;
  isDir: boolean;
  modifiedAt: string;
  mime?: string;
}

export interface SearchOptions {
  path?: string;
  type?: "file" | "folder";
  limit?: number;
  content?: boolean;
}

export interface UploadOptions {
  overwrite?: boolean;
  onProgress?: (sent: number, total: number) => void;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly path?: string) {
    super(message);
    this.name = "ApiError";
  }
}

export class StorageClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string, private readonly token: string) {
    this.baseUrl = baseUrl.replace(/\\/+$/, "");
  }

  async listFolder(path = "/"): Promise<FileEntry[]> {
    const data = await this.request<{ entries: FileEntry[] }>("GET", `/files?path=${encodeURIComponent(path)}`);
    return data.entries;
  }

  async createFolder(path: string): Promise<FileEntry> {
    return this.request<FileEntry>("POST", "/folders", { path });
  }

  async uploadFile(path: string, file: Blob, options: UploadOptions = {}): Promise<FileEntry> {
    const form = new FormData();
    form.append("path", path);
    form.append("overwrite", String(options.overwrite ?? false));
    form.append("file", file);
    options.onProgress?.(0, file.size);
    const entry = await this.request<FileEntry>("POST", "/upload", form);
    options.onProgress?.(file.size, file.size);
    return entry;
  }

  async downloadFile(path: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/download?path=${encodeURIComponent(path)}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    if (!res.ok) throw new ApiError(res.status, `download failed: ${res.statusText}`, path);
    return res.blob();
  }

  async searchFiles(query: string, options: SearchOptions = {}): Promise<FileEntry[]> {
    const params = new URLSearchParams({ q: query, limit: String(options.limit ?? 50) });
    if (options.path) params.set("path", options.path);
    if (options.type) params.set("type", options.type);
    if (options.content) params.set("content", "1");
    const data = await this.request<{ results: FileEntry[] }>("GET", `/search?${params}`);
    return data.results;
  }

  async deleteFile(path: string): Promise<void> {
    await this.request<void>("DELETE", `/files?path=${encodeURIComponent(path)}`);
  }

  private async request<T>(method: string, url: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Authorization: `Bearer ${this.token}` };
    let payload: BodyInit | undefined;
    if (body instanceof FormData) {
      payload = body;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    const res = await fetch(this.baseUrl + url, { method, headers, body: payload });
    if (res.status === 204) return undefined as T;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, data.error ?? res.statusText, data.path);
    return data as T;
  }
}

export function formatSize(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
"""

CODE_FILES: dict[str, str] = {
    "api.ts": """
import { Router } from "express";
import { authenticate } from "./auth";
import { config } from "./config";
import { searchIndex } from "./search";
import { storage } from "./storage";

export const api = Router();

api.use(authenticate);

api.get("/files", async (req, res) => {
  const path = String(req.query.path ?? "/");
  const entries = await storage.list(path);
  res.json({ entries });
});

api.post("/folders", async (req, res) => {
  const entry = await storage.mkdir(String(req.body.path));
  res.status(201).json(entry);
});

api.post("/upload", async (req, res) => {
  const { path, overwrite } = req.body;
  if (req.file.size > config.maxUploadBytes) {
    return res.status(413).json({ error: "file too large", path });
  }
  const entry = await storage.write(path, req.file.stream, { overwrite: overwrite === "true" });
  await searchIndex.enqueue(entry);
  res.status(201).json(entry);
});

api.get("/download", async (req, res) => {
  const path = String(req.query.path);
  const { stream, size, mime } = await storage.read(path);
  res.setHeader("Content-Length", size);
  res.setHeader("Content-Type", mime);
  stream.pipe(res);
});

api.get("/search", async (req, res) => {
  const results = await searchIndex.query(String(req.query.q), {
    path: req.query.path ? String(req.query.path) : undefined,
    content: req.query.content === "1",
    limit: Number(req.query.limit ?? 50),
  });
  res.json({ results });
});

api.delete("/files", async (req, res) => {
  await storage.remove(String(req.query.path));
  res.status(204).end();
});
""",
    "storage.ts": """
import { createReadStream, createWriteStream, promises as fs } from "node:fs";
import { join, resolve } from "node:path";
import { S3Client, GetObjectCommand, PutObjectCommand } from "@aws-sdk/client-s3";
import { config } from "./config";

export interface Backend {
  list(path: string): Promise<Entry[]>;
  read(path: string): Promise<{ stream: NodeJS.ReadableStream; size: number; mime: string }>;
  write(path: string, stream: NodeJS.ReadableStream, opts: { overwrite: boolean }): Promise<Entry>;
  mkdir(path: string): Promise<Entry>;
  remove(path: string): Promise<void>;
}

export interface Entry {
  path: string;
  name: string;
  size: number;
  isDir: boolean;
  modifiedAt: string;
}

/** Local disk backend. Paths are resolved inside the root so they cannot escape it. */
export class LocalBackend implements Backend {
  constructor(private readonly root: string) {}

  private abs(path: string): string {
    const full = resolve(this.root, "." + path);
    if (!full.startsWith(resolve(this.root))) throw new Error("path escapes storage root");
    return full;
  }

  async list(path: string): Promise<Entry[]> {
    const names = await fs.readdir(this.abs(path));
    return Promise.all(names.map(async (name) => {
      const st = await fs.stat(join(this.abs(path), name));
      return { path: join(path, name), name, size: st.size, isDir: st.isDirectory(), modifiedAt: st.mtime.toISOString() };
    }));
  }

  async read(path: string) {
    const st = await fs.stat(this.abs(path));
    return { stream: createReadStream(this.abs(path)), size: st.size, mime: "application/octet-stream" };
  }

  async write(path: string, stream: NodeJS.ReadableStream, opts: { overwrite: boolean }): Promise<Entry> {
    if (!opts.overwrite) await fs.access(this.abs(path)).then(() => { throw new Error("exists"); }, () => undefined);
    await new Promise((ok, fail) => stream.pipe(createWriteStream(this.abs(path))).on("finish", ok).on("error", fail));
    const st = await fs.stat(this.abs(path));
    return { path, name: path.split("/").pop()!, size: st.size, isDir: false, modifiedAt: st.mtime.toISOString() };
  }

  async mkdir(path: string): Promise<Entry> {
    await fs.mkdir(this.abs(path), { recursive: true });
    return { path, name: path.split("/").pop()!, size: 0, isDir: true, modifiedAt: new Date().toISOString() };
  }

  async remove(path: string): Promise<void> {
    await fs.rm(this.abs(path), { recursive: true });
  }
}

/** S3-compatible backend. Folders are prefixes; uploads use multipart for anything over 8 MiB. */
export class S3Backend implements Backend {
  private readonly client = new S3Client({ region: config.s3.region, endpoint: config.s3.endpoint });
  constructor(private readonly bucket: string) {}

  async list(path: string): Promise<Entry[]> { /* ListObjectsV2 with Delimiter "/" */ return []; }
  async read(path: string) {
    const out = await this.client.send(new GetObjectCommand({ Bucket: this.bucket, Key: path.slice(1) }));
    return { stream: out.Body as NodeJS.ReadableStream, size: out.ContentLength ?? 0, mime: out.ContentType ?? "application/octet-stream" };
  }
  async write(path: string, stream: NodeJS.ReadableStream): Promise<Entry> {
    await this.client.send(new PutObjectCommand({ Bucket: this.bucket, Key: path.slice(1), Body: stream }));
    return { path, name: path.split("/").pop()!, size: 0, isDir: false, modifiedAt: new Date().toISOString() };
  }
  async mkdir(path: string): Promise<Entry> { return this.write(path + "/", Buffer.alloc(0) as never); }
  async remove(path: string): Promise<void> { /* DeleteObjects on prefix */ }
}

/** WebDAV backend for customers with an existing NAS. Maps list/mkdir onto PROPFIND and MKCOL. */
export class WebDAVBackend implements Backend {
  constructor(private readonly baseUrl: string, private readonly auth: string) {}
  async list(path: string): Promise<Entry[]> { return this.propfind(path); }
  async read(path: string) { const r = await fetch(this.baseUrl + path, { headers: { Authorization: this.auth } }); return { stream: r.body as never, size: Number(r.headers.get("content-length")), mime: r.headers.get("content-type") ?? "" }; }
  async write(path: string, stream: NodeJS.ReadableStream): Promise<Entry> { await fetch(this.baseUrl + path, { method: "PUT", body: stream as never, headers: { Authorization: this.auth } }); return { path, name: path.split("/").pop()!, size: 0, isDir: false, modifiedAt: new Date().toISOString() }; }
  async mkdir(path: string): Promise<Entry> { await fetch(this.baseUrl + path, { method: "MKCOL", headers: { Authorization: this.auth } }); return { path, name: path.split("/").pop()!, size: 0, isDir: true, modifiedAt: new Date().toISOString() }; }
  async remove(path: string): Promise<void> { await fetch(this.baseUrl + path, { method: "DELETE", headers: { Authorization: this.auth } }); }
  private async propfind(path: string): Promise<Entry[]> { return []; }
}

export const storage: Backend =
  config.backend === "s3" ? new S3Backend(config.s3.bucket)
  : config.backend === "webdav" ? new WebDAVBackend(config.webdav.url, config.webdav.auth)
  : new LocalBackend(config.localRoot);
""",
    "search.ts": """
import { Entry } from "./storage";

export interface QueryOptions {
  path?: string;
  content?: boolean;
  limit: number;
}

interface IndexedDoc {
  entry: Entry;
  tokens: Set<string>;
  text?: string;
}

const TOKEN = /[\\p{L}\\p{N}]{2,}/gu;

export function tokenize(text: string): Set<string> {
  return new Set((text.toLowerCase().match(TOKEN) ?? []));
}

/** In-memory inverted index. The production build swaps this for the SQLite FTS5 index. */
class SearchIndex {
  private readonly docs = new Map<string, IndexedDoc>();
  private readonly queue: Entry[] = [];

  async enqueue(entry: Entry): Promise<void> {
    this.queue.push(entry);
    if (this.queue.length === 1) setImmediate(() => this.drain());
  }

  async query(q: string, opts: QueryOptions): Promise<Entry[]> {
    const terms = [...tokenize(q)];
    const hits: Array<{ entry: Entry; score: number }> = [];
    for (const doc of this.docs.values()) {
      if (opts.path && !doc.entry.path.startsWith(opts.path)) continue;
      let score = 0;
      for (const t of terms) {
        if (doc.entry.name.toLowerCase().includes(t)) score += 3;
        if (doc.tokens.has(t)) score += 1;
        if (opts.content && doc.text?.includes(t)) score += 2;
      }
      if (score > 0) hits.push({ entry: doc.entry, score });
    }
    return hits.sort((a, b) => b.score - a.score).slice(0, opts.limit).map((h) => h.entry);
  }

  private async drain(): Promise<void> {
    while (this.queue.length) {
      const entry = this.queue.shift()!;
      const text = await extractText(entry);
      this.docs.set(entry.path, { entry, tokens: tokenize(entry.name + " " + (text ?? "")), text: text?.toLowerCase() });
    }
  }
}

async function extractText(entry: Entry): Promise<string | undefined> {
  if (entry.isDir) return undefined;
  if (/\\.(md|txt|csv|json|ya?ml|html?|ts|py|go)$/i.test(entry.name)) return undefined; // read directly by worker
  return undefined; // PDF / DOCX extraction is handled by worker.py
}

export const searchIndex = new SearchIndex();
""",
    "auth.ts": """
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import type { NextFunction, Request, Response } from "express";
import { config } from "./config";

export interface Principal {
  userId: string;
  scope: string;
  kind: "session" | "token";
}

interface StoredToken {
  hash: string;
  userId: string;
  scope: string;
  expiresAt?: number;
}

const tokens = new Map<string, StoredToken>();

/** Create a long-lived API token. The plain value is returned once and only its hash is stored. */
export function issueApiToken(userId: string, scope = "/", ttlDays = config.tokenTtlDays): string {
  const plain = "fx_" + randomBytes(24).toString("base64url");
  const id = plain.slice(3, 11);
  tokens.set(id, { hash: sha256(plain), userId, scope, expiresAt: ttlDays ? Date.now() + ttlDays * 86_400_000 : undefined });
  return plain;
}

export function revokeApiToken(plain: string): boolean {
  return tokens.delete(plain.slice(3, 11));
}

function verifyApiToken(plain: string): Principal | undefined {
  const stored = tokens.get(plain.slice(3, 11));
  if (!stored) return undefined;
  if (stored.expiresAt && stored.expiresAt < Date.now()) return undefined;
  const a = Buffer.from(sha256(plain));
  const b = Buffer.from(stored.hash);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return undefined;
  return { userId: stored.userId, scope: stored.scope, kind: "token" };
}

/** Express middleware: accepts a session cookie or a bearer API token. */
export function authenticate(req: Request, res: Response, next: NextFunction): void {
  const header = req.headers.authorization ?? "";
  if (header.startsWith("Bearer ")) {
    const principal = verifyApiToken(header.slice(7));
    if (!principal) {
      res.status(401).json({ error: "invalid or expired API token" });
      return;
    }
    (req as Request & { principal: Principal }).principal = principal;
    return next();
  }
  const session = req.cookies?.[config.sessionCookie];
  if (!session) {
    res.status(401).json({ error: "authentication required" });
    return;
  }
  (req as Request & { principal: Principal }).principal = { userId: session, scope: "/", kind: "session" };
  next();
}

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}
""",
    "config.ts": """
const env = process.env;

export const config = {
  port: Number(env.PORT ?? 5212),
  backend: (env.CLOUD_BACKEND ?? "local") as "local" | "s3" | "webdav",
  localRoot: env.CLOUD_ROOT ?? "./demo",
  maxUploadBytes: Number(env.CLOUD_MAX_UPLOAD ?? 5 * 1024 ** 3),
  sessionCookie: "cloud_session",
  tokenTtlDays: Number(env.CLOUD_TOKEN_TTL_DAYS ?? 90),
  s3: {
    bucket: env.CLOUD_S3_BUCKET ?? "cloud-demo",
    region: env.CLOUD_S3_REGION ?? "eu-central-1",
    endpoint: env.CLOUD_S3_ENDPOINT,
  },
  webdav: {
    url: env.CLOUD_WEBDAV_URL ?? "https://nas.internal/dav",
    auth: env.CLOUD_WEBDAV_AUTH ?? "",
  },
  thumbnails: {
    sizes: [128, 256, 512],
    quality: 82,
  },
} as const;

export type Config = typeof config;
""",
    "index.ts": """
import express from "express";
import cookieParser from "cookie-parser";
import { api } from "./api";
import { config } from "./config";

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(cookieParser());
app.use("/api", api);
app.use(express.static("public"));

app.get("/healthz", (_req, res) => res.json({ ok: true, backend: config.backend }));

app.listen(config.port, () => {
  console.log(`cloud listening on :${config.port} (backend=${config.backend})`);
});
""",
    "worker.py": '''
"""Background worker: extracts text from uploaded documents for content search."""

import json
import logging
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger("worker")
QUEUE = Path("./queue")
INDEX = Path("./index")
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    return " ".join(t.text or "" for t in root.iter(WORD_NS + "t"))


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html"}:
        return path.read_text(encoding="utf-8", errors="replace")
    log.info("no extractor for %s", suffix)
    return ""


def process(job: Path) -> None:
    payload = json.loads(job.read_text())
    source = Path(payload["path"])
    text = extract_text(source)
    out = INDEX / (source.name + ".txt")
    out.write_text(text[:200_000], encoding="utf-8")
    job.unlink()
    log.info("indexed %s (%d chars)", source, len(text))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    QUEUE.mkdir(exist_ok=True)
    INDEX.mkdir(exist_ok=True)
    while True:
        jobs = sorted(QUEUE.glob("*.json"))
        if not jobs:
            time.sleep(1)
            continue
        for job in jobs:
            try:
                process(job)
            except Exception:
                log.exception("job %s failed", job.name)
                job.rename(job.with_suffix(".failed"))


if __name__ == "__main__":
    sys.exit(main())
''',
    "thumbnail.go": """
// Command thumbnail renders resized previews for images stored in a Cloud workspace.
package main

import (
	"flag"
	"fmt"
	"image"
	"image/jpeg"
	_ "image/png"
	"log"
	"os"
	"path/filepath"

	"golang.org/x/image/draw"
)

var sizes = []int{128, 256, 512}

func main() {
	src := flag.String("src", "", "source image")
	out := flag.String("out", "derived", "output directory")
	quality := flag.Int("quality", 82, "JPEG quality")
	flag.Parse()
	if *src == "" {
		log.Fatal("-src is required")
	}
	if err := render(*src, *out, *quality); err != nil {
		log.Fatal(err)
	}
}

func render(src, out string, quality int) error {
	f, err := os.Open(src)
	if err != nil {
		return err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return fmt.Errorf("decode %s: %w", src, err)
	}
	if err := os.MkdirAll(out, 0o755); err != nil {
		return err
	}
	base := filepath.Base(src)
	for _, size := range sizes {
		dst := image.NewRGBA(fit(img.Bounds(), size))
		draw.CatmullRom.Scale(dst, dst.Bounds(), img, img.Bounds(), draw.Over, nil)
		name := filepath.Join(out, fmt.Sprintf("%s.%d.jpg", base, size))
		w, err := os.Create(name)
		if err != nil {
			return err
		}
		if err := jpeg.Encode(w, dst, &jpeg.Options{Quality: quality}); err != nil {
			w.Close()
			return err
		}
		w.Close()
	}
	return nil
}

// fit returns a rectangle whose longest side is max, preserving aspect ratio.
func fit(b image.Rectangle, max int) image.Rectangle {
	w, h := b.Dx(), b.Dy()
	if w >= h {
		return image.Rect(0, 0, max, h*max/w)
	}
	return image.Rect(0, 0, w*max/h, max)
}
""",
    "styles.css": """
:root {
  --fx-primary: #2563eb;
  --fx-success: #10b981;
  --fx-warning: #f59e0b;
  --fx-bg: #f9fafb;
  --fx-surface: #ffffff;
  --fx-border: #e5e7eb;
  --fx-text: #111827;
  --fx-muted: #6b7280;
  --fx-radius: 10px;
}

body {
  margin: 0;
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--fx-text);
  background: var(--fx-bg);
}

.fx-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

.fx-sidebar {
  background: #111827;
  color: #fff;
  padding: 24px 16px;
}

.fx-sidebar a {
  display: block;
  padding: 8px 12px;
  border-radius: 8px;
  color: inherit;
  text-decoration: none;
}

.fx-sidebar a.active {
  background: var(--fx-primary);
}

.fx-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  padding: 24px;
}

.fx-tile {
  background: var(--fx-surface);
  border: 1px solid var(--fx-border);
  border-radius: var(--fx-radius);
  overflow: hidden;
  transition: box-shadow 120ms ease;
}

.fx-tile:hover {
  box-shadow: 0 4px 16px rgba(17, 24, 39, 0.08);
}

.fx-tile img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.fx-tile .name {
  padding: 8px 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fx-tile .meta {
  padding: 0 12px 10px;
  color: var(--fx-muted);
  font-size: 12px;
}

@media (max-width: 720px) {
  .fx-layout { grid-template-columns: 1fr; }
  .fx-sidebar { display: none; }
}
""",
    "package.json": json.dumps({
        "name": "cloud-demo-service",
        "version": "2.0.0",
        "private": True,
        "description": "Demo file storage service used by the Cloud sample workspace",
        "type": "module",
        "main": "dist/index.js",
        "scripts": {"dev": "tsx watch index.ts", "build": "tsc -p .", "start": "node dist/index.js", "test": "vitest run", "lint": "eslint ."},
        "dependencies": {"@aws-sdk/client-s3": "^3.620.0", "cookie-parser": "^1.4.6", "express": "^4.19.2"},
        "devDependencies": {"@types/express": "^4.17.21", "@types/node": "^22.0.0", "eslint": "^9.8.0", "tsx": "^4.16.0", "typescript": "^5.5.4", "vitest": "^2.0.4"},
        "engines": {"node": ">=20"},
    }, indent=2),
    "Dockerfile": """
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev --no-audit
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=5212 CLOUD_BACKEND=local CLOUD_ROOT=/data
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
VOLUME ["/data"]
EXPOSE 5212
HEALTHCHECK --interval=30s CMD wget -qO- http://localhost:5212/healthz || exit 1
CMD ["node", "dist/index.js"]
""",
    "README.md": """
# cloud-demo-service

A deliberately small file storage service that backs the Cloud demo workspace.
It is not the real Cloud backend; it exists so the `Code/` folder has something
coherent to browse and preview.

## Layout

- `index.ts` — Express entry point
- `api.ts` — HTTP routes: list, upload, download, search, delete
- `storage.ts` — storage architecture: local disk, S3 and WebDAV backends behind one interface
- `search.ts` — in-memory inverted index used for name and content search
- `auth.ts` — session cookies and scoped API tokens
- `config.ts` — configuration from environment variables
- `worker.py` — text extraction worker for DOCX and plain-text documents
- `thumbnail.go` — image thumbnail renderer
- `styles.css` — design tokens and the file grid

## Running

```bash
npm install
npm run dev
```

Set `CLOUD_BACKEND=s3` with `CLOUD_S3_BUCKET` and `CLOUD_S3_REGION` to use
object storage, or `CLOUD_BACKEND=webdav` with `CLOUD_WEBDAV_URL` for a NAS.
""",
}


def meeting_notes() -> str:
    return """
# Meeting Notes

- **Date:** 2026-07-07
- **Attendees:** Anna Kowalski, Marco Rossi, Elena Petrova, Tom Schmidt
- **Topic:** Sharing launch readiness

## Agenda

1. Share links with PIN and expiry
2. Content search index size
3. Security review follow-ups
4. Cyprus office hiring

## Discussion

Share links are feature complete. Anna demoed revocation and the access report.
Marco raised that the content search index for image-heavy workspaces is larger
than expected because EXIF text is being indexed; he will strip it.

Elena summarised the security review: enforce two-factor authentication for
administrators before launch, and expire API tokens after ninety days by default.

Tom shared the hiring plan for the Limassol office: two senior engineers in
September, then four more in Q4.

## Decisions

- Launch share links on 24 July behind a per-workspace flag.
- Two-factor enforcement for administrators ships in the same release.

## Action items

- [ ] Marco: strip EXIF text from the index (2026-07-10)
- [ ] Elena: write the 2FA enforcement migration (2026-07-14)
- [ ] Anna: update the project roadmap page (2026-07-08)
- [ ] Tom: post the Cyprus job descriptions (2026-07-15)
"""


def release_notes() -> str:
    return """
# Release Notes

## 2.0.0 — 2026-07-24

### Added
- Share links with PIN, expiry date and download limits
- Access report for every shared file
- Content search for PDF, DOCX and Markdown documents
- WebDAV backend for existing NAS shares

### Changed
- Thumbnails are now generated at 128, 256 and 512 pixels
- API tokens expire after ninety days by default
- Two-factor authentication is enforced for administrators

### Fixed
- Uploads over 5 GB failed to resume after a network interruption
- Folder rename lost the modification date of nested files
- Search results ignored the selected folder filter

## 1.9.2 — 2026-06-19

### Fixed
- Preview of RTF documents rendered raw control words
- Grid view flickered when thumbnails finished loading out of order

## 1.9.1 — 2026-06-05

### Fixed
- Session cookies were not rotated after a password change
"""


def adr_notes() -> str:
    return """
# Architecture Decision Records

## ADR-007: Use SQLite FTS5 for content search

- **Status:** accepted
- **Date:** 2026-06-24

We evaluated Elasticsearch, Meilisearch and SQLite FTS5 for content search.
FTS5 keeps the deployment a single process, indexes one million documents in
under an hour on a laptop, and query latency stays below 30 ms at that size.
We accept that ranking is simpler than in a dedicated engine.

## ADR-008: Multipart uploads with 8 MiB parts

- **Status:** accepted
- **Date:** 2026-06-30

Uploads are split into 8 MiB parts so that a dropped connection costs at most
one part. Smaller parts increased request overhead on S3; larger parts made
progress reporting too coarse on slow links.

## ADR-009: Soft delete with a fourteen day window

- **Status:** accepted
- **Date:** 2026-07-02

Deleted files are kept for fourteen days. This matches the data retention
policy and gives support enough time to restore accidental deletions.
"""


def retro_notes() -> str:
    return """
# Sprint Retrospective

- **Sprint:** 2026-S14 (2026-06-22 to 2026-07-03)
- **Facilitator:** Elena Petrova

## What went well

- Share link backend landed a week early
- Zero incidents during the sprint
- New starters shipped their first change in week one

## What could be better

- Too many review requests landed on Friday afternoon
- The migration plan document was updated in three places at once

## Actions

- Reviews are requested before Thursday noon for the same-sprint merge
- The migration plan lives only in Documents/ and is linked from Team Notes
"""


INCIDENT_TXT = """
INCIDENT REPORT INC-2026-031
============================

Title:        Thumbnail generation backlog after bulk photo import
Severity:     S3 (degraded)
Started:      2026-06-27 09:14 UTC
Resolved:     2026-06-27 11:52 UTC
Owner:        Marco Rossi

SUMMARY
-------
A customer imported 140,000 photographs over WebDAV in one batch. The
thumbnail worker processed them sequentially and fell 2.5 hours behind,
so newly uploaded files showed generic icons in the grid view.

TIMELINE
--------
09:14  Import starts; queue depth alert fires at 20,000 jobs
09:31  On-call acknowledges, confirms no data loss
10:05  Worker concurrency raised from 2 to 8 on the production host
11:20  Queue depth below 5,000
11:52  Queue drained; incident closed

ROOT CAUSE
----------
Worker concurrency was sized for interactive uploads, not bulk imports.
No backpressure existed between the WebDAV endpoint and the worker queue.

ACTIONS
-------
- Autoscale thumbnail workers on queue depth (done 2026-07-01)
- Prioritise thumbnails for folders a user is currently viewing (in progress)
- Document bulk import guidance in the Engineering Handbook
"""

SUPPORT_TXT = """
Support transcript #48213
Customer: Quartz Financial (workspace qf-eu)
Agent: Nina Larsen
Date: 2026-07-02

[10:02] Customer: Hi, our finance team cannot find the invoice PDFs from
        March. Searching "invoice" returns nothing.
[10:03] Agent: Thanks for reaching out. Was content search enabled for the
        workspace? It is off by default on the Team plan.
[10:05] Customer: I do not think so. Where do I enable it?
[10:05] Agent: Settings > Search > Index file contents. The initial index
        for your workspace should take about twenty minutes.
[10:31] Customer: Enabled. Searching "invoice" now shows 212 files. Thanks!
[10:32] Agent: Great. You can also filter by type PDF and date range March
        2026 to narrow it down. Anything else I can help with?
[10:33] Customer: No, that is all. Have a good day.

Resolution: content search was disabled; enabled by customer admin.
Tags: search, onboarding, invoices
"""

API_SPEC_SECTIONS: list[Section] = [
    ("Authentication", [
        "Every request must carry an API token in the Authorization header. Tokens are created on the account page, start with the prefix fx_ and are shown only once. A token is scoped to a folder prefix and expires after ninety days unless configured otherwise.",
        "    Authorization: Bearer fx_9K2mV…",
        "Requests without a valid API token receive 401 with a JSON body containing an error field.",
    ]),
    ("List a folder", [
        "    GET /api/files?path=/Documents",
        "Returns an entries array. Each entry has path, name, size, isDir, modifiedAt and, for files, mime.",
    ]),
    ("Upload", [
        "    POST /api/upload  (multipart/form-data: path, file, overwrite)",
        "Files larger than 8 MiB should use the multipart endpoints /api/upload/init, /api/upload/part and /api/upload/complete so interrupted transfers can resume.",
    ]),
    ("Download", [
        "    GET /api/download?path=/Photos/fjord.jpg",
        "Streams the file with the sniffed content type. Range requests are supported for video and audio previews.",
    ]),
    ("Search", [
        "    GET /api/search?q=roadmap&path=/Documents&content=1&limit=20",
        "Matches file names and, when content=1, extracted document text. Results are ordered by score and limited to the requested count.",
    ]),
    ("Errors", [
        "Errors use conventional status codes: 400 for invalid input, 401 for missing authentication, 403 for a token outside its scope, 404 for unknown paths, 409 for an existing file without overwrite, 413 for files above the upload limit.",
    ]),
]

LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <!-- Cloud logo: folded-corner document with a bold F. Part of the Cloud design system. -->
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#3b82f6"/>
      <stop offset="1" stop-color="#1d4ed8"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="224" height="224" rx="40" fill="url(#g)"/>
  <path d="M84 56h88l36 36v108a12 12 0 0 1-12 12H84a12 12 0 0 1-12-12V68a12 12 0 0 1 12-12z" fill="#fff" opacity="0.95"/>
  <path d="M172 56v36h36z" fill="#bfdbfe"/>
  <path d="M104 96h60v16h-42v20h36v16h-36v36h-18z" fill="#1d4ed8"/>
</svg>
"""

HELLO_TXT = """
Hello from Cloud!

This is a plain text file. Open it to see the text preview, or use the
search box to find it by content: try searching for "quick start".

Quick start:
  1. Drag a file onto the grid to upload it.
  2. Right-click a file to rename, move, share or delete it.
  3. Press Ctrl+F to search the current folder.
"""

CONFIG_YAML = """
# Cloud demo configuration
server:
  listen: 0.0.0.0:5212
  base_url: https://files.example.com
  trust_proxy_headers: true

storage:
  default: photos
  backends:
    photos:
      type: s3
      bucket: cloud-demo-photos
      region: eu-central-1
      endpoint: https://s3.eu-central-1.amazonaws.com
      multipart_part_size: 8MiB
    documents:
      type: local
      root: /srv/cloud/documents
    nas:
      type: webdav
      url: https://nas.internal/dav
      username: cloud
      password_env: CLOUD_WEBDAV_PASSWORD

search:
  content_indexing: true
  extractors: [pdf, docx, md, txt, html, xlsx]
  max_document_bytes: 50MiB

thumbnails:
  sizes: [128, 256, 512]
  quality: 82
  workers: 8

sharing:
  default_expiry_days: 30
  require_pin: false
  max_downloads: 1000

auth:
  session_ttl_hours: 72
  api_token_ttl_days: 90
  require_2fa_for_admins: true
"""


def countries_json() -> str:
    data = [
        {"code": "CY", "name": "Cyprus", "capital": "Nicosia", "region": "Europe", "currency": "EUR", "population": 1260000, "office": "Limassol"},
        {"code": "DE", "name": "Germany", "capital": "Berlin", "region": "Europe", "currency": "EUR", "population": 84500000, "office": "Berlin"},
        {"code": "NL", "name": "Netherlands", "capital": "Amsterdam", "region": "Europe", "currency": "EUR", "population": 17900000, "office": None},
        {"code": "PL", "name": "Poland", "capital": "Warsaw", "region": "Europe", "currency": "PLN", "population": 37600000, "office": "Warsaw"},
        {"code": "IT", "name": "Italy", "capital": "Rome", "region": "Europe", "currency": "EUR", "population": 58900000, "office": None},
        {"code": "ES", "name": "Spain", "capital": "Madrid", "region": "Europe", "currency": "EUR", "population": 48300000, "office": None},
        {"code": "FR", "name": "France", "capital": "Paris", "region": "Europe", "currency": "EUR", "population": 68200000, "office": None},
        {"code": "SE", "name": "Sweden", "capital": "Stockholm", "region": "Europe", "currency": "SEK", "population": 10500000, "office": None},
        {"code": "PT", "name": "Portugal", "capital": "Lisbon", "region": "Europe", "currency": "EUR", "population": 10400000, "office": None},
        {"code": "GR", "name": "Greece", "capital": "Athens", "region": "Europe", "currency": "EUR", "population": 10400000, "office": None},
        {"code": "GB", "name": "United Kingdom", "capital": "London", "region": "Europe", "currency": "GBP", "population": 67600000, "office": "London"},
        {"code": "IE", "name": "Ireland", "capital": "Dublin", "region": "Europe", "currency": "EUR", "population": 5200000, "office": None},
        {"code": "US", "name": "United States", "capital": "Washington", "region": "Americas", "currency": "USD", "population": 335000000, "office": "Austin"},
        {"code": "CA", "name": "Canada", "capital": "Ottawa", "region": "Americas", "currency": "CAD", "population": 40100000, "office": None},
        {"code": "JP", "name": "Japan", "capital": "Tokyo", "region": "Asia", "currency": "JPY", "population": 124000000, "office": None},
        {"code": "AU", "name": "Australia", "capital": "Canberra", "region": "Oceania", "currency": "AUD", "population": 26600000, "office": None},
        {"code": "BR", "name": "Brazil", "capital": "Brasília", "region": "Americas", "currency": "BRL", "population": 216000000, "office": None},
    ]
    return json.dumps({"generated": "2026-07-01", "count": len(data), "countries": data}, indent=2, ensure_ascii=False)


def feed_xml() -> str:
    items = [
        ("Cloud 2.0 released with sharing and content search", "2026-07-24", "Share links with PIN and expiry, full-text search for PDF and DOCX, and a WebDAV backend."),
        ("Opening our Cyprus engineering hub", "2026-07-15", "The search and storage teams are moving to a new office in Limassol this September."),
        ("Migration plan for legacy WebDAV shares", "2026-07-06", "How we are moving 38 workspaces to managed S3 storage without downtime."),
        ("Q2 2026 quarterly report", "2026-07-01", "Quarterly revenue up 18 percent, storage costs per terabyte down 9 percent."),
        ("Security review: what we found and what we changed", "2026-06-20", "Two-factor enforcement for administrators and API token expiry by default."),
    ]
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>', "<title>Cloud Blog</title>", "<link>https://files.example.com/blog</link>", "<description>Product news from the Cloud team</description>", "<language>en</language>"]
    for title, d, desc in items:
        out.append(f"<item><title>{title}</title><link>https://files.example.com/blog/{d}</link><pubDate>{datetime.fromisoformat(d).strftime('%a, %d %b %Y 09:00:00 +0000')}</pubDate><description>{desc}</description></item>")
    out.append("</channel></rss>")
    return "\n".join(out)


def contacts_vcf(people: list[dict]) -> str:
    cards = []
    for x in people:
        first, last = x["name"].split(" ", 1)
        cards.append("\r\n".join(["BEGIN:VCARD", "VERSION:3.0", f"N:{last};{first};;;", f"FN:{x['name']}", f"ORG:{x['company']}", f"TITLE:{x['department']}", f"EMAIL;TYPE=WORK:{x['email']}", f"TEL;TYPE=WORK:+{rng.randint(30, 49)} {rng.randint(100, 999)} {rng.randint(100000, 999999)}", f"ADR;TYPE=WORK:;;;{x['country']}", "END:VCARD"]))
    return "\r\n".join(cards) + "\r\n"


def calendar_ics() -> str:
    events = [
        ("Sharing launch go/no-go", date(2026, 7, 22), "Review launch checklist for share links"),
        ("Cloud 2.0 release", date(2026, 7, 24), "Cut release 2.0.0 from main"),
        ("Migration cutover window", date(2026, 8, 17), "Phase three of the migration plan"),
        ("Board meeting", date(2026, 9, 3), "Quarterly revenue and Cyprus office update"),
        ("Limassol office opening", date(2026, 9, 14), "First day at the Cyprus engineering hub"),
        ("Q3 roadmap review", date(2026, 9, 28), "Close out the Q3 project roadmap"),
    ]
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cloud Demo Workspace//EN", "CALSCALE:GREGORIAN"]
    for i, (summary, d, desc) in enumerate(events):
        out += ["BEGIN:VEVENT", f"UID:evt-{i:03d}@files.example.com", f"DTSTAMP:20260701T090000Z", f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}", f"SUMMARY:{summary}", f"DESCRIPTION:{desc}", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def team_notes() -> str:
    return """
# Team Notes

Shared scratchpad for the Cloud team. Anyone can edit; keep it short.

## This week (2026-07-06)

- Sharing launch is on track for 24 July. Checklist is in Project Plan.pdf.
- Content search beta is enabled for six workspaces; index sizes look fine
  after stripping EXIF text.
- The project roadmap for Q3 is final. Milestones live in roadmap.xlsx.

## Runbooks

- Thumbnail backlog: raise worker concurrency, see INC-2026-031.
- Stuck multipart upload: abort with the upload id from the audit log.
- Expired API token complaints: tokens expire after ninety days by default;
  the account page shows the expiry date.

## Useful contacts

See contacts.csv for the current on-call and escalation list.
"""


def analytics_rows() -> list[list]:
    rows = [["date", "workspace", "uploads", "downloads", "searches", "shares_created", "active_users", "storage_gb"]]
    d = date(2026, 6, 1)
    while d <= date(2026, 7, 31):
        for ws in ["qf-eu", "helios", "northwind", "kestrel", "orbit"]:
            rows.append([d.isoformat(), ws, rng.randint(20, 900), rng.randint(50, 3000), rng.randint(10, 600), rng.randint(0, 40), rng.randint(5, 180), round(rng.uniform(40, 2600), 1)])
        d += timedelta(days=1)
    return rows


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_root() -> None:
    write_text(OUT / "README.md", README_ROOT)
    copy(SF / "mountain.jpeg", OUT / "mountains.jpg")
    write_text(OUT / "app.ts", APP_TS)
    ov = DOCS["Product Overview"]
    write_pdf(OUT / "overview.pdf", "Product Overview", ov["subtitle"], ov["sections"])
    Image.open(PICSUM / f"{BEACH_ID}.jpg").save(OUT / "beach.png", optimize=True)
    write_fig(OUT / "UI Design.fig")
    write_users_csv(OUT / "data.csv", 6000)
    copy(SF / "SampleVideo_1280x720_5mb.mp4", OUT / "demo.mp4")
    for name, d in ROOT_DATES.items():
        stamp(OUT / name, d)


def build_code() -> None:
    d = reset_dir(OUT / "Code")
    for name, text in CODE_FILES.items():
        write_text(d / name, text)


def build_design() -> None:
    d = reset_dir(OUT / "Design")
    draw_dashboard(d / "dashboard.png")
    draw_file_browser(d / "file-browser.jpg")
    write_text(d / "logo.svg", LOGO_SVG)
    Image.open(PICSUM / f"{ILLUSTRATION_ID}.jpg").save(d / "illustration.webp", quality=88)
    copy(SF / "FelineActualBassethound-small.gif", d / "animation.gif")
    draw_wireframe(d / "wireframe.png")
    bg = DOCS["Brand Guidelines"]
    write_pdf(d / "Brand Guidelines.pdf", "Brand Guidelines", bg["subtitle"], bg["sections"], accent="#7c3aed")
    copy(SF / "SamplePSDFile_1.9mbmb.psd", d / "source-design.psd")


def build_documents() -> None:
    d = reset_dir(OUT / "Documents")
    accents = {"Storage Architecture": "#2563eb", "Security Review": "#dc2626", "Engineering Handbook": "#0f766e", "Quarterly Report Q2 2026": "#b45309", "Onboarding Guide": "#7c3aed", "Vendor Agreement": "#374151"}
    for title, accent in accents.items():
        doc = DOCS[title]
        write_pdf(d / f"{title}.pdf", title, doc["subtitle"], doc["sections"], accent)
    for title in ["Product Requirements", "Q3 Roadmap", "Migration Plan", "User Research", "Project Proposal", "Cyprus Office Expansion", "Invoice INV-2026-0142", "Data Retention Policy"]:
        doc = DOCS[title]
        write_docx(d / f"{title}.docx", title, doc["subtitle"], doc["sections"], doc.get("table"))
    write_odt(d / "Board Minutes.odt", "Board Minutes", DOCS["Board Minutes"]["sections"])
    write_rtf(d / "Legal Notice.rtf", "Legal Notice", DOCS["Legal Notice"]["sections"])
    write_html(d / "API Specification.html", "Cloud API Specification", API_SPEC_SECTIONS)
    write_text(d / "Meeting Notes.md", meeting_notes())
    write_text(d / "Release Notes.md", release_notes())
    write_text(d / "Architecture Decision Records.md", adr_notes())
    write_text(d / "Sprint Retrospective.md", retro_notes())
    write_text(d / "Incident Report.txt", INCIDENT_TXT)
    write_text(d / "Support Transcript.txt", SUPPORT_TXT)
    copy(SF / "git-cheat-sheet-education.pdf", d / "Git Cheat Sheet.pdf")


def build_photos() -> None:
    d = reset_dir(OUT / "Photos")
    for pid, name in PHOTOS:
        src = PICSUM / f"{pid}.jpg"
        if name.endswith(".jpg"):
            copy(src, d / name)
        elif name.endswith(".png"):
            Image.open(src).resize((1280, 800), Image.LANCZOS).save(d / name, optimize=True)
        else:
            Image.open(src).save(d / name, quality=85)
    # One real alpine photo from the sample-files repo, mildly sharpened so it
    # is not byte-identical to the root mountains.jpg.
    Image.open(SF / "mountain.jpeg").filter(ImageFilter.SHARPEN).save(d / "mountain-alps.jpg", quality=90)


def build_example() -> None:
    d = reset_dir(OUT / "example")
    write_text(d / "hello.txt", HELLO_TXT)
    copy(TA / "data" / "sample.json", d / "example.json")
    copy(TA / "data" / "sample.csv", d / "sample.csv")


def build_archive() -> None:
    d = reset_dir(OUT / "Archive")
    with zipfile.ZipFile(d / "project-backup.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((OUT / "Code").iterdir()):
            z.write(f, f"cloud-demo-service/{f.name}")
    with zipfile.ZipFile(d / "documents.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((OUT / "Documents").glob("*.md")) + sorted((OUT / "Documents").glob("*.txt")):
            z.write(f, f"documents/{f.name}")
    fixtures = {
        "source.tar": SF / "sample.tar",
        "logs.tar.gz": SF / "sample.tar.gz",
        "assets.tar.xz": SF / "sample.tar.xz",
        "backup-2026-06.tar.bz2": SF / "sample.tar.bz2",
        "archive.7z": SF / "sample.7z",
        "database.sql.gz": SF / "mysqlsampledatabase.sql.gz",
        "config.xml.bz2": SF / "phpunit.xml.bz2",
        "plugin.jar": SF / "sample.jar",
        "comics.cbz": SF / "sample.cbz",
        "legacy.tar.Z": SF / "sample.tar.Z",
        "rootfs.cpio": SF / "sample.cpio",
        "installer.iso": SF / "sample.iso",
        "snapshot.tar.lz": SF / "sample.tar.lz",
        "release.tar.lzma": SF / "sample.tar.lzma",
        "fixtures.zip": TA / "archives" / "sample.zip",
    }
    for name, src in fixtures.items():
        copy(src, d / name)


def build_resources() -> None:
    d = reset_dir(OUT / "Resources")
    people = [fake_person(i) for i in range(1, 201)]
    write_xlsx(d / "users.xlsx", {"Users": [["ID", "Name", "Email", "Company", "Department", "Country", "Status", "Created", "Storage (bytes)", "Last login"]] + [[x["id"], x["name"], x["email"], x["company"], x["department"], x["country"], x["status"], x["created_at"], x["storage_used"], x["last_login"]] for x in people]})
    items = ["Laptop 14\"", "Laptop 16\"", "Monitor 27\"", "Dock", "Keyboard", "Mouse", "Headset", "Webcam", "Desk", "Chair", "NAS 4-bay", "Switch 24-port", "Access point", "UPS 1500VA", "Label printer"]
    inventory = [["SKU", "Item", "Location", "Quantity", "Unit cost", "Total", "Last audit"]]
    for i, item in enumerate(items):
        for loc in ["Berlin", "Limassol", "Warsaw"]:
            qty, cost = rng.randint(1, 40), round(rng.uniform(25, 2400), 2)
            inventory.append([f"SKU-{1000 + i}", item, loc, qty, cost, round(qty * cost, 2), random_date().isoformat()])
    summary = [["Location", "Items", "Value"]] + [[loc, sum(1 for r in inventory[1:] if r[2] == loc), round(sum(r[5] for r in inventory[1:] if r[2] == loc), 2)] for loc in ["Berlin", "Limassol", "Warsaw"]]
    write_xlsx(d / "inventory.xlsx", {"Inventory": inventory, "Summary": summary})
    with (d / "analytics.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(analytics_rows())
    write_text(d / "countries.json", countries_json())
    write_text(d / "configuration.yaml", CONFIG_YAML)
    write_text(d / "feed.xml", feed_xml())
    write_sqlite(d / "database.sqlite")
    (d / "contacts.vcf").write_text(contacts_vcf(people[:40]), encoding="utf-8")
    (d / "calendar.ics").write_text(calendar_ics(), encoding="utf-8")


def build_shared() -> None:
    d = reset_dir(OUT / "Shared")
    write_text(d / "Team Notes.md", team_notes())
    pp = DOCS["Project Plan"]
    write_pdf(d / "Project Plan.pdf", "Project Plan", pp["subtitle"], pp["sections"], accent="#0f766e")
    with (d / "contacts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "role", "email", "phone", "location", "on_call"])
        roles = ["Engineering lead", "Storage engineer", "Search engineer", "Security engineer", "Support lead", "Product manager", "Designer", "Solutions engineer", "Finance", "Office manager"]
        for i, role in enumerate(roles):
            x = fake_person(500 + i)
            w.writerow([x["name"], role, x["email"].split("@")[0] + "@files.example.com", f"+49 30 {rng.randint(1000000, 9999999)}", rng.choice(["Berlin", "Limassol", "Warsaw", "Remote"]), "yes" if i < 4 else "no"])
    copy(SF / "New-York.jpg", d / "shared-photo.jpg")
    roadmap = [["Quarter", "Theme", "Milestone", "Owner", "Status", "Target"]]
    for q, theme, ms, owner, status, target in [
        ("Q3 2026", "Sharing", "Share links with PIN and expiry", "Anna Kowalski", "In progress", "2026-07-24"),
        ("Q3 2026", "Sharing", "Group sharing", "Anna Kowalski", "Planned", "2026-08-21"),
        ("Q3 2026", "Search", "Content search GA", "Marco Rossi", "In progress", "2026-09-11"),
        ("Q3 2026", "Security", "2FA enforcement for admins", "Elena Petrova", "In progress", "2026-07-24"),
        ("Q3 2026", "Security", "API token expiry by default", "Elena Petrova", "Done", "2026-07-10"),
        ("Q4 2026", "Platform", "Desktop sync client beta", "Tom Schmidt", "Proposed", "2026-12-04"),
        ("Q4 2026", "Storage", "Tiered object storage", "Marco Rossi", "Planned", "2026-11-13"),
        ("Q4 2026", "Company", "Limassol office fully staffed", "Tom Schmidt", "Planned", "2026-12-18"),
    ]:
        roadmap.append([q, theme, ms, owner, status, target])
    write_xlsx(d / "roadmap.xlsx", {"Project roadmap": roadmap})


def stamp_folders() -> None:
    for folder in ["Code", "Design", "Documents", "Photos", "example", "Archive", "Resources", "Shared"]:
        for f in sorted((OUT / folder).iterdir()):
            stamp(f, random_date())
        stamp(OUT / folder, random_date())


def main() -> None:
    ensure_sources()
    OUT.mkdir(parents=True, exist_ok=True)
    build_code()
    build_design()
    build_documents()
    build_photos()
    build_example()
    build_archive()
    build_resources()
    build_shared()
    build_root()
    stamp_folders()
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built {OUT}: {sum(1 for f in OUT.rglob('*') if f.is_file())} files, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
