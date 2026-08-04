from __future__ import annotations

import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _register_fonts() -> tuple[str, str]:
    """
    Prefer monospace for code blocks + readable font for text.
    Falls back to built-in fonts if system fonts aren't available.
    """
    normal = "Helvetica"
    mono = "Courier"

    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", "SegoeUI"),
        (r"C:\Windows\Fonts\consola.ttf", "Consolas"),
        (r"C:\Windows\Fonts\cour.ttf", "CourierNew"),
    ]

    for font_path, font_name in candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                if "consola" in font_path.lower() or "cour" in font_path.lower():
                    mono = font_name
                else:
                    normal = font_name
            except Exception:
                pass

    return normal, mono


def _wrap_line(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    out: list[str] = []
    s = text
    while len(s) > max_chars:
        out.append(s[:max_chars])
        s = s[max_chars:]
    if s:
        out.append(s)
    return out


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    content = md_path.read_text(encoding="utf-8", errors="replace").splitlines()

    normal_font, mono_font = _register_fonts()

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_w, page_h = A4
    left = 18 * mm
    right = 18 * mm
    top = 18 * mm
    bottom = 18 * mm

    y = page_h - top
    font_size = 10
    leading = 13
    max_width = page_w - left - right
    # Rough estimate: average char width in mono at size 10
    max_chars = int(max_width / (font_size * 0.55))

    in_code = False

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = page_h - top

    for raw in content:
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_code = not in_code
            continue

        # Simple markdown: headings
        if not in_code and re.match(r"^#{1,6}\s", line):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            size = 16 if level == 1 else 13 if level == 2 else 11
            c.setFont(normal_font, size)
            for wline in _wrap_line(text, max_chars):
                if y <= bottom:
                    new_page()
                c.drawString(left, y, wline)
                y -= (leading + 2)
            y -= 4
            c.setFont(normal_font, font_size)
            continue

        # Bullet points (keep it simple)
        if not in_code and line.strip().startswith("- "):
            c.setFont(normal_font, font_size)
            bullet_text = "• " + line.strip()[2:]
            for wline in _wrap_line(bullet_text, max_chars):
                if y <= bottom:
                    new_page()
                c.drawString(left, y, wline)
                y -= leading
            continue

        if in_code:
            c.setFont(mono_font, font_size)
        else:
            c.setFont(normal_font, font_size)

        # Add a little extra spacing around separators
        if not in_code and line.strip() == "---":
            y -= 8
            continue

        # Normal line
        for wline in _wrap_line(line, max_chars):
            if y <= bottom:
                new_page()
            c.drawString(left, y, wline)
            y -= leading

        # Blank line spacing
        if line.strip() == "":
            y -= 2

    c.save()


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[1]
    md = base / "docs" / "ALTERACOES_INTERFACE_2026-04-23.md"
    pdf = base / "docs" / "ALTERACOES_INTERFACE_2026-04-23.pdf"
    md_to_pdf(md, pdf)
    print(f"Gerado: {pdf}")

