"""Render Backend_Reference.md to Backend_Reference.pdf.

Run with isolated, throw-away deps:

    uv run --with markdown --with xhtml2pdf python docs/_render_pdf.py

This script is not part of the application; it's a one-off doc tool.
"""

from __future__ import annotations

import pathlib
import sys

import markdown
from xhtml2pdf import pisa

HERE = pathlib.Path(__file__).resolve().parent
MD_PATH = HERE / "Backend_Reference.md"
PDF_PATH = HERE / "Backend_Reference.pdf"

CSS = """
@page {
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @frame footer_frame {
        -pdf-frame-content: footerContent;
        bottom: 8mm;
        margin-left: 16mm;
        margin-right: 16mm;
        height: 8mm;
    }
}

body {
    font-family: "Helvetica", "Arial", sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1c1c1c;
}

h1 {
    font-size: 22pt;
    color: #0a3d62;
    border-bottom: 2pt solid #0a3d62;
    padding-bottom: 4pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
}

h2 {
    font-size: 15pt;
    color: #0a3d62;
    margin-top: 16pt;
    margin-bottom: 6pt;
}

h3 {
    font-size: 12pt;
    color: #1b4f72;
    margin-top: 12pt;
    margin-bottom: 4pt;
}

h4 {
    font-size: 10.5pt;
    color: #1b4f72;
    margin-top: 8pt;
    margin-bottom: 2pt;
}

p {
    margin-top: 4pt;
    margin-bottom: 4pt;
}

code {
    font-family: "Courier New", monospace;
    font-size: 9pt;
    background-color: #f4f4f4;
    padding: 1pt 3pt;
    border-radius: 2pt;
}

pre {
    font-family: "Courier New", monospace;
    font-size: 8.5pt;
    background-color: #f4f4f4;
    padding: 6pt;
    border-left: 2pt solid #0a3d62;
    border-radius: 2pt;
    line-height: 1.3;
    white-space: pre-wrap;
}

pre code {
    background: transparent;
    padding: 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 6pt;
    margin-bottom: 8pt;
    font-size: 9pt;
}

th, td {
    border: 0.5pt solid #cccccc;
    padding: 4pt 6pt;
    text-align: left;
    vertical-align: top;
}

th {
    background-color: #e6edf3;
    color: #0a3d62;
    font-weight: bold;
}

ul, ol {
    margin-top: 2pt;
    margin-bottom: 6pt;
    padding-left: 18pt;
}

li {
    margin-top: 1pt;
    margin-bottom: 1pt;
}

blockquote {
    border-left: 3pt solid #b3b3b3;
    padding-left: 8pt;
    color: #555555;
    margin: 6pt 0;
}

hr {
    border: none;
    border-top: 0.5pt solid #cccccc;
    margin: 12pt 0;
}

a {
    color: #0a3d62;
    text-decoration: none;
}

.cover {
    text-align: center;
    margin-top: 60pt;
}

.cover h1 {
    font-size: 30pt;
    border: none;
    margin-bottom: 8pt;
}

.cover .subtitle {
    font-size: 13pt;
    color: #555555;
    margin-bottom: 36pt;
}

.cover .meta {
    font-size: 10pt;
    color: #777777;
}

.footer {
    font-size: 8pt;
    color: #888888;
    text-align: center;
}
"""

COVER_HTML = """
<div class="cover">
  <h1>Inventory Backend</h1>
  <div class="subtitle">Reference for Frontend &amp; Integration Teams</div>
  <div class="meta">
    Phases 1&ndash;8 complete &middot; 36 endpoints &middot; 10 tables &middot; 199 tests
  </div>
</div>
<div style="page-break-after: always;"></div>
"""

FOOTER_HTML = (
    '<div id="footerContent" class="footer">'
    "Inventory Backend Reference &mdash; "
    "page <pdf:pagenumber/> of <pdf:pagecount/>"
    "</div>"
)


def build_html(md_text: str) -> str:
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Inventory Backend Reference</title>
  <style>{CSS}</style>
</head>
<body>
  {COVER_HTML}
  {body_html}
  {FOOTER_HTML}
</body>
</html>
"""


def main() -> int:
    if not MD_PATH.exists():
        print(f"Missing: {MD_PATH}", file=sys.stderr)
        return 1

    md_text = MD_PATH.read_text(encoding="utf-8")
    html = build_html(md_text)

    with PDF_PATH.open("wb") as fh:
        status = pisa.CreatePDF(src=html, dest=fh, encoding="utf-8")

    if status.err:
        print(f"PDF rendering failed: {status.err} errors", file=sys.stderr)
        return 2

    size_kb = PDF_PATH.stat().st_size / 1024
    print(f"Wrote {PDF_PATH} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
