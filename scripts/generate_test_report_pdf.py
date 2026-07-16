#!/usr/bin/env python3
"""Generate PDF from markdown test report with logo cover page."""

from pathlib import Path
from weasyprint import HTML
import markdown

# Read markdown report
md_path = Path(__file__).parent.parent / "docs" / "test_report.md"
pdf_path = Path(__file__).parent.parent / "docs" / "Wilson-Eval3ngine_Test_Report.pdf"
logo_path = Path(__file__).parent.parent / "docs" / "64493cd5-d7b8-4737-b8ad-1245ae595ffd.png"

md_content = md_path.read_text()

# Convert to HTML with extensions
html_content = markdown.markdown(md_content, extensions=["tables", "toc", "fenced_code"])

# Add comprehensive styling for PDF (larger, more readable)
styled_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{ margin: 0.75in; size: letter; }}
@page {{ @bottom-center {{ content: counter(page); font-size: 10pt; color: #666; }} }}
@page :first {{ margin: 0; }}

body {{ 
    font-family: 'DejaVu Sans', 'Liberation Sans', sans-serif; 
    line-height: 1.5; 
    color: #222;
    font-size: 11pt;
}}

/* Cover page styling */
.cover-page {{
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100vh;
    text-align: center;
    padding: 0;
    margin: 0;
}}

.cover-logo {{
    max-width: 300px;
    max-height: 300px;
    margin-bottom: 2em;
}}

.cover-title {{
    font-size: 36pt;
    color: #264653;
    margin: 0.5em 0;
    font-weight: bold;
}}

.cover-subtitle {{
    font-size: 18pt;
    color: #8338ec;
    margin: 0.5em 0;
}}

.cover-meta {{
    font-size: 12pt;
    color: #666;
    margin: 2em 0;
}}

.cover-status {{
    font-size: 14pt;
    color: #e63946;
    margin: 2em 0;
    font-weight: bold;
}}

h1 {{ 
    color: #264653; 
    border-bottom: 3px solid #264653; 
    padding-bottom: 0.4em;
    font-size: 24pt;
    margin-top: 1.5em;
}}

h2 {{ 
    color: #8338ec; 
    border-bottom: 1px solid #ccc; 
    padding-bottom: 0.3em;
    font-size: 16pt;
    margin-top: 1.2em;
}}

h3 {{ 
    color: #2a9d8f;
    font-size: 13pt;
    margin-top: 1em;
}}

table {{ 
    border-collapse: collapse; 
    width: 100%; 
    margin: 1em 0;
    font-size: 10pt;
}}

th, td {{ 
    border: 1px solid #999; 
    padding: 0.6em; 
    text-align: left; 
    vertical-align: top;
}}

th {{ 
    background: #e8e8e8;
    font-weight: bold;
}}

code {{ 
    background: #f0f0f0; 
    padding: 0.1em 0.3em; 
    border-radius: 3px;
    font-family: 'DejaVu Sans Mono', monospace;
}}

pre {{ 
    background: #f5f5f5; 
    padding: 0.8em; 
    border-radius: 5px; 
    overflow-x: auto;
    border: 1px solid #ddd;
}}

ul, ol {{ margin: 0.8em 0; padding-left: 2em; }}
li {{ margin: 0.3em 0; }}

strong {{ font-weight: bold; }}
em {{ font-style: italic; }}

.toc {{ background: #f9f9f9; padding: 1em; border: 1px solid #ddd; margin: 1em 0; }}
</style>
</head>
<body>
<!-- Cover Page -->
<div class="cover-page">
    <img src="file://{logo_path}" alt="Wilson Eval3ngine Logo" class="cover-logo">
    <h1 class="cover-title">Wilson Eval3ngine</h1>
    <p class="cover-subtitle">Test Report - Foundation Release v0.1.0</p>
    <div class="cover-meta">
        <p>Generated: 2026-07-16</p>
        <p>Framework Version: 0.1.0</p>
        <p>Release Tier: foundation</p>
        <p>Python Version: 3.13.12</p>
    </div>
    <p class="cover-status">STATUS: NOT APPROVED FOR PRODUCTION CERTIFICATION</p>
</div>
<!-- Content Pages -->
{html_content}
</body>
</html>
"""

HTML(string=styled_html).write_pdf(str(pdf_path))
print(f"Generated: {pdf_path}")
print(f"Pages: PDF contains {len(HTML(string=styled_html).render().pages)} pages")