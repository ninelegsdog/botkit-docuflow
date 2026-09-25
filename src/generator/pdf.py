from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def render_pdf(text: str, output_path: str) -> str:
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    y = height - 2 * cm
    for line in text.split("\n"):
        if y < 2 * cm:
            c.showPage()
            y = height - 2 * cm
        c.drawString(2 * cm, y, line)
        y -= 0.5 * cm
    c.save()
    return output_path
