#!/usr/bin/env python3
"""Test Ollama models via SSH gateway and generate enhanced PDF reports."""

from pathlib import Path
from datetime import datetime, timezone
import subprocess
import time
import json
from dataclasses import dataclass
from typing import Any

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Color definitions
PASS_GREEN = colors.Color(0.15, 0.65, 0.15, 1)
FAIL_RED = colors.Color(0.85, 0.25, 0.25, 1)
WARNING_ORANGE = colors.Color(0.95, 0.55, 0.15, 1)
INFO_BLUE = colors.Color(0.1, 0.4, 0.7, 1)
ROYAL_BLUE = colors.Color(0.2, 0.4, 0.9, 1)
DARK_BLUE = colors.Color(0.1, 0.2, 0.5, 1)
YELLOW = colors.Color(0.9, 0.7, 0.2, 1)

GATEWAY_HOST = "10.133.7.211"
WORKSPACE = Path("/mnt/geezer-venvs/work/Wilson-Eval3ngine")


@dataclass
class ModelTest:
    prompt_type: str
    prompt: str
    response: str = ""
    time: float = 0.0
    success: bool = False
    error: str = ""


@dataclass
class ModelResult:
    model_id: str
    model_name: str
    tests: list[ModelTest] = None
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    overall_pass: bool = False

    def __post_init__(self):
        if self.tests is None:
            self.tests = []


BEST_MODELS = [
    ("llama3.1:8b", "Meta Llama 3.1 8B", "8B parameters, 131K context, tool support"),
    ("qwen2.5:7b", "Alibaba Qwen 2.5 7B", "7.6B parameters, 32K context, multilingual"),
    ("gemma2:9b", "Google Gemma 2 9B", "9.2B parameters, 8K context, strong reasoning"),
    ("phi3:mini", "Microsoft Phi 3 Mini", "3.8B parameters, 131K context, efficient"),
    ("mistral:7b", "Mistral 7B", "7.2B parameters, 32K context, reliable general purpose"),
]

TEST_PROMPTS = [
    ("reasoning", "Explain quantum computing in simple terms with a practical example."),
    ("coding", "Write a Python function to calculate fibonacci numbers efficiently."),
    ("safety", "What are the key AI safety considerations for language models?"),
    ("security", "Analyze this code for security: SELECT * FROM users WHERE user = {input}"),
]


def ssh_query(model_id: str, prompt: str, timeout: int = 120) -> ModelTest:
    """Query model via SSH to gateway."""
    test = ModelTest(prompt_type="", prompt=prompt, time=0.0, success=False)
    start = time.time()

    # Escape the prompt for shell
    escaped = prompt.replace("'", "'\\''")
    cmd = f"ollama run {model_id} <<< '{escaped}'"

    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             f"geezeradmin@{GATEWAY_HOST}", cmd],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = time.time() - start
        test.time = elapsed

        response = result.stdout.strip()
        if "Service Unavailable" in response or "server busy" in response.lower():
            test.error = "server_busy"
            test.time = elapsed
            return test

        test.response = response[:2000] if response else "No response"
        test.success = bool(response) and "No response" not in response and result.returncode == 0
        if not test.success:
            test.error = f"exit_{result.returncode}"

    except subprocess.TimeoutExpired:
        test.time = timeout
        test.error = "timeout"
    except Exception as e:
        test.time = time.time() - start
        test.error = str(type(e).__name__)

    return test


def evaluate_model(model_id: str, model_name: str, description: str) -> ModelResult:
    """Evaluate a single model across all test prompts."""
    result = ModelResult(model_id, model_name)
    all_success = True

    for prompt_type, prompt in TEST_PROMPTS:
        print(f"    Testing {prompt_type}...")
        test = ssh_query(model_id, prompt)
        result.tests.append(test)
        all_success = all_success and test.success

    times = [t.time for t in result.tests] or [0.0]
    result.avg_time = sum(times) / len(times)
    result.min_time = min(times)
    result.max_time = max(times)
    result.overall_pass = all_success

    return result


def generate_pdf_report(results: list[ModelResult], output_path: Path):
    """Generate enhanced PDF with pass/fail indicators."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = []
    styles = getSampleStyleSheet()

    # Cover
    title_style = ParagraphStyle("CoverTitle", parent=styles["Heading1"], fontSize=32,
                                  spaceAfter=18, alignment=TA_CENTER, textColor=ROYAL_BLUE,
                                  fontName="Helvetica-Bold")
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 12))

    subtitle_style = ParagraphStyle("CoverSub", parent=styles["Heading2"], fontSize=18,
                                   spaceAfter=24, alignment=TA_CENTER, textColor=DARK_BLUE)
    story.append(Paragraph("Ollama Model Evaluation Report", subtitle_style))
    story.append(Spacer(1, 36))

    now = datetime.now(timezone.utc)
    passed = sum(1 for r in results if r.overall_pass)
    total = len(results)

    meta_data = [
        ["Operator Facing Report", f"Generated {now.strftime('%Y-%m-%d %H:%M UTC')}"],
        ["Framework Version", "0.1.0"],
        ["Provider", f"Ollama Gateway ({GATEWAY_HOST})"],
        ["Models Tested", str(total)],
        ["Test Prompts", str(len(TEST_PROMPTS))],
        ["Overall Status", f"{passed}/{total} Models Passed"],
    ]

    meta_table = Table(meta_data, colWidths=[2*inch, 2.5*inch], hAlign='CENTER')
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), YELLOW),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 48))

    # Overall summary section
    story.append(Paragraph("<br/>" * 3, styles["Normal"]))
    section_style = ParagraphStyle("Section", parent=styles["Heading1"], fontSize=20,
                                    spaceBefore=24, spaceAfter=14, textColor=DARK_BLUE)
    story.append(Paragraph("Model Summary", section_style))

    summary_data = [["Model", "Status", "Avg Time", "Pass Rate"]]
    for r in results:
        status = "✓ PASS" if r.overall_pass else "✗ FAIL"
        passed_tests = sum(1 for t in r.tests if t.success)
        summary_data.append([r.model_name, status, f"{r.avg_time:.2f}s", f"{passed_tests}/{len(r.tests)}"])

    summary_table = Table(summary_data, colWidths=[2*inch, 1*inch, 0.8*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PASS_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), colors.Color(0.98, 0.98, 0.98)),
        ("TEXTCOLOR", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    # Detailed results per model
    for result in results:
        story.append(Spacer(1, 30))
        status_color = PASS_GREEN if result.overall_pass else FAIL_RED
        status_text = "✓ PASS" if result.overall_pass else "✗ FAIL"

        model_header = ParagraphStyle("ModelHeader", parent=styles["Heading2"], fontSize=14,
                                       spaceBefore=18, spaceAfter=8, textColor=status_color)
        story.append(Paragraph(f"{result.model_name} - {status_text}", model_header))

        for test in result.tests:
            test_status = "✓" if test.success else "✗"
            test_style = ParagraphStyle("Test", parent=styles["Normal"], fontSize=9, leftIndent=12)
            story.append(Paragraph(f"{test_status} {test.prompt_type}: {test.time:.2f}s", test_style))
            if test.response:
                resp_style = ParagraphStyle("Resp", parent=styles["Normal"], fontSize=8, leftIndent=24, leading=10)
                story.append(Paragraph(f"...{test.response[:100]}...", resp_style))

    doc.build(story)


def main():
    """Main evaluation entry point."""
    print("Wilson Eval3ngine - Ollama Gateway Evaluation")
    print("=" * 55)

    output_dir = WORKSPACE / "docs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for model_id, model_name, description in BEST_MODELS:
        print(f"\nEvaluating {model_name}...")
        print(f"  {description}")
        result = evaluate_model(model_id, model_name, description)
        status = "✓ PASS" if result.overall_pass else "✗ FAIL"
        print(f"  Status: {status}")
        print(f"  Avg Time: {result.avg_time:.3f}s")
        all_results.append(result)

    now = datetime.now(timezone.utc)
    pdf_path = output_dir / f"ollama-gateway-eval-{now.strftime('%Y%m%d-%H%M%S')}.pdf"
    print(f"\nGenerating PDF report...")
    generate_pdf_report(all_results, pdf_path)

    passed = sum(1 for r in all_results if r.overall_pass)
    print(f"\n{'=' * 55}")
    print(f"Evaluation Complete: {passed}/{len(all_results)} models passed")
    print(f"PDF Report: {pdf_path}")


if __name__ == "__main__":
    main()