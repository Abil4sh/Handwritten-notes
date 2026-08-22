"""Render a specimen sheet of every installed handwriting font.

This is our Step 1 acceptance check: if this produces a readable PDF,
every font is present, loadable by ReportLab, and embeddable in a PDF.

Run from the backend/ directory:   python scripts/font_specimen.py
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS_DIR = Path(__file__).resolve().parent.parent / "app" / "handwriting" / "fonts"
OUT = Path(__file__).resolve().parent.parent / "out" / "font_specimen.pdf"

SAMPLES = [
    "Binary search works on sorted arrays.",
    "The quick brown fox jumps over the lazy dog",
    "0123456789   O(log n)   n/2   x < y   {a, b}   50% -> 25%",
]


def main() -> None:
    manifest = json.loads((FONTS_DIR / "fonts.json").read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(OUT), pagesize=A4)
    page_width, page_height = A4
    y = page_height - 25 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Handwriting font specimen")
    y -= 12 * mm

    for font in manifest["fonts"]:
        # Registering under our stable id decouples our code from the filename.
        pdfmetrics.registerFont(TTFont(font["id"], FONTS_DIR / "files" / font["file"]))

        c.setFont("Helvetica", 8)
        c.setFillGray(0.45)
        c.drawString(20 * mm, y, f'{font["family"]}  ·  id={font["id"]}  ·  {font["script_type"]}')
        y -= 7 * mm

        c.setFillGray(0)
        for sample in SAMPLES:
            c.setFont(font["id"], 15)
            c.drawString(20 * mm, y, sample)
            # Measure with the real font. This is the call the layout engine
            # will depend on for line breaking in Step 3.
            width = pdfmetrics.stringWidth(sample, font["id"], 15)
            c.setFont("Helvetica", 6)
            c.setFillGray(0.7)
            c.drawRightString(page_width - 20 * mm, y, f"{width:.0f}pt")
            c.setFillGray(0)
            y -= 8 * mm

        y -= 6 * mm

    c.save()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
