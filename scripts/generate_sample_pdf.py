#!/usr/bin/env python3
"""Generate professional PDF from sample test run."""

from pathlib import Path
from weasyprint import HTML, CSS
import markdown

md_path = Path(__file__).parent.parent / "docs" / "samples" / "sample_run_report.md"
pdf_path = Path(__file__).parent.parent / "docs" / "samples" / "Wilson-Eval3ngine_Sample_Run.pdf"
logo_path = Path(__file__).parent.parent / "static" / "images" / "we3-logo" / "64493cd5-d7b8-4737-b8ad-1245ae595ffd.png"

md_content = md_path.read_text()
html_content = markdown.markdown(md_content, extensions=["tables", "fenced_code"])

styled_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{ margin: 0.75in; size: letter; }}
body {{ font-family: 'DejaVu Sans', 'Liberation Sans', sans-serif; line-height: 1.6; color: #222; font-size: 11pt; }}
h1 {{ color: #264653; border-bottom: 3px solid #264653; padding-bottom: 0.4em; margin-top: 1.5em; font-size: 24pt; }}
h2 {{ color: #8338ec; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; margin-top: 1.2em; font-size: 16pt; }}
h3 {{ color: #2a9d8f; margin-top: 1em; font-size: 13pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }}
th, td {{ border: 1px solid #999; padding: 0.6em; text-align: left; vertical-align: top; }}
th {{ background: #e8e8e8; font-weight: bold; }}
code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; font-family: 'DejaVu Sans Mono', monospace; }}
pre {{ background: #f5f5f5; padding: 0.8em; border-radius: 5px; overflow-x: auto; border: 1px solid #ddd; }}
.cover {{ text-align: center; padding: 2in 0; }}
.cover img {{ max-width: 300px; }}
.warning {{ border-left: 0.4rem solid #a66a00; padding-left: 1rem; background: #fff8e6; margin: 1em 0; }}
.code-block {{ font-family: monospace; font-size: 9pt; }}
</style>
</head>
<body>
<div class="cover">
<img src="file://{logo_path}" alt="Wilson Eval3ngine Logo">
<h1>Wilson Eval3ngine<br>Sample Test Run Report</h1>
<p><strong>Foundation v0.1.0</strong> • 2026-07-16</p>
</div>
{html_content}
</body>
</html>
"""

HTML(string=styled_html).write_pdf(str(pdf_path))
print(f"Generated: {pdf_path}")