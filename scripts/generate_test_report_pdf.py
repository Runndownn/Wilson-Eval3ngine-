#!/usr/bin/env python3
"""Generate PDF from markdown test report."""

from pathlib import Path
from weasyprint import HTML
import markdown

# Read markdown report
md_path = Path(__file__).parent.parent / "docs" / "test_report.md"
pdf_path = Path(__file__).parent.parent / "docs" / "Wilson-Eval3ngine_Test_Report.pdf"

md_content = md_path.read_text()

# Convert to HTML with TOC and styling
html_content = markdown.markdown(md_content, extensions=["tables", "toc", "fenced_code"])

# Add basic styling for PDF
styled_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{ margin: 1in; size: letter; }}
body {{ font-family: 'DejaVu Sans', sans-serif; line-height: 1.6; color: #333; }}
h1 {{ color: #264653; border-bottom: 2px solid #264653; padding-bottom: 0.3em; }}
h2 {{ color: #8338ec; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }}
h3 {{ color: #2a9d8f; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid #777; padding: 0.5em; text-align: left; }}
th {{ background: #f0f0f0; }}
code {{ background: #f5f5f5; padding: 0.2em 0.4em; border-radius: 3px; }}
pre {{ background: #f5f5f5; padding: 1em; border-radius: 5px; overflow-x: auto; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""

HTML(string=styled_html).write_pdf(str(pdf_path))
print(f"Generated: {pdf_path}")