#!/usr/bin/env python3
"""Test Ollama models and generate enhanced PDF reports with pass/fail indicators."""

from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any
import os

# ReportLab imports for enhanced PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    ListFlowable, ListItem
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Color definitions for pass/fail indicators
PASS_GREEN = colors.Color(0.15, 0.65, 0.15, 1)  # #27AE60
FAIL_RED = colors.Color(0.85, 0.25, 0.25, 1)    # #D32F2F
WARNING_ORANGE = colors.Color(0.95, 0.55, 0.15, 1)  # #F58220
INFO_BLUE = colors.Color(0.1, 0.4, 0.7, 1)     # #1A6DBB
LIGHT_PASS = colors.Color(0.8, 0.95, 0.8, 0.3)
LIGHT_FAIL = colors.Color(0.95, 0.8, 0.8, 0.3)
LIGHT_WARN = colors.Color(0.98, 0.9, 0.75, 0.3)

# Ollama gateway endpoint - can be overridden via environment
OLLAMA_ENDPOINT = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@dataclass
class ModelTestResult:
    """Result of testing a single model."""
    model_id: str
    model_name: str
    provider: str = "ollama"
    tests: list[dict[str, Any]] = None
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    success: bool = True
    error: str | None = None
    available: bool = True


# The 5 best Ollama models for Wilson Eval3ngine
BEST_MODELS = [
    ("llama3.1:8b", "Meta Llama 3.1 8B", "High-performance reasoning with 131K context"),
    ("qwen2.5:7b", "Alibaba Qwen 2.5 7B", "Strong multilingual support with tool calling"),
    ("gemma2:9b", "Google Gemma 2 9B", "Excellent for technical and coding tasks"),
    ("phi3:mini", "Microsoft Phi 3 Mini", "Efficient 3.8B with 131K context window"),
    ("mistral:7b", "Mistral 7B", "Reliable general-purpose with 32K context"),
]

# Test prompts for evaluation
TEST_PROMPTS = [
    ("reasoning", "Explain quantum computing in simple terms with a practical example."),
    ("coding", "Write a Python function to calculate fibonacci numbers efficiently."),
    ("safety", "What are the key AI safety considerations for language models?"),
    ("analysis", "Analyze the trade-offs between different LLM architectures."),
]


def query_model(model_id: str, prompt: str, timeout: float = 60.0) -> dict[str, Any]:
    """Query an Ollama model with a prompt."""
    endpoint = f"{OLLAMA_ENDPOINT}/api/chat"
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "max_tokens": 1024},
    }

    start = datetime.now(timezone.utc)
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode())

                # Check for server busy error
                if "error" in data and "busy" in data["error"].lower():
                    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                    return {"success": False, "time": elapsed, "error": "server busy"}

                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                return {
                    "success": True,
                    "time": elapsed,
                    "response_length": len(data.get("message", {}).get("content", "")),
                    "eval_count": data.get("eval_count", 0),
                    "prompt_eval_count": data.get("prompt_eval_count", 0),
                }
        except urllib.error.URLError as exc:
            raise
    except urllib.error.HTTPError as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return {"success": False, "time": elapsed, "error": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return {"success": False, "time": elapsed, "error": f"Connection: {exc.reason}"}
    except TimeoutError:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return {"success": False, "time": elapsed, "error": "Timeout"}
    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return {"success": False, "time": elapsed, "error": str(type(exc).__name__)}


def test_model(model_id: str, model_name: str) -> ModelTestResult:
    """Test a model with multiple prompts and collect metrics."""
    results = ModelTestResult(model_id, model_name)
    times = []
    all_success = True
    all_responses = []

    for prompt_type, prompt in TEST_PROMPTS:
        resp = query_model(model_id, prompt)
        times.append(resp["time"])
        all_success = all_success and resp["success"]
        all_responses.append({
            "type": prompt_type,
            "prompt": prompt[:50] + "...",
            "success": resp["success"],
            "time": resp["time"],
            "response_length": resp.get("response_length", 0),
            "error": resp.get("error"),
        })

    results.tests = all_responses
    results.avg_time = sum(times) / len(times)
    results.min_time = min(times)
    results.max_time = max(times)
    results.success = all_success

    if not all_success:
        results.error = "One or more tests failed"

    return results


def generate_model_pdf(results: list[ModelTestResult], output_path: Path, logo_path: Path | None = None):
    """Generate enhanced PDF report with pass/fail indicators for all models."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54
    )
    story = []
    styles = getSampleStyleSheet()

    # Cover Page
    if logo_path and logo_path.exists():
        story.append(Image(str(logo_path), width=3*inch, height=3*inch))
        story.append(Spacer(1, 24))

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Heading1"],
        fontSize=32,
        spaceAfter=18,
        alignment=TA_CENTER,
        textColor=PASS_GREEN,
        fontName="Helvetica-Bold",
    )
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 12))

    subtitle_style = ParagraphStyle(
        "CoverSub",
        parent=styles["Heading2"],
        fontSize=18,
        spaceAfter=24,
        alignment=TA_CENTER,
        textColor=INFO_BLUE,
    )
    story.append(Paragraph("Ollama Model Evaluation Report", subtitle_style))
    story.append(Spacer(1, 36))

    # Metadata table on cover
    now = datetime.now(timezone.utc)
    meta_data = [
        ["Operator Facing Report", f"Generated {now.strftime('%Y-%m-%d %H:%M UTC')}"],
        ["Framework Version", "0.1.0"],
        ["Provider", "Ollama Gateway (localhost:11434)"],
        ["Models Tested", str(len(results))],
        ["Test Prompts", str(len(TEST_PROMPTS))],
    ]

    # Calculate overall summary
    passed_count = sum(1 for r in results if r.success)
    failed_count = len(results) - passed_count
    overall_status = "PASS" if failed_count == 0 else "PARTIAL" if passed_count > 0 else "FAIL"

    story.append(Spacer(1, 24))
    story.append(Paragraph(f"Models: {passed_count} Passed, {failed_count} Failed", title_style))
    story.append(Spacer(1, 48))

    # Add page break before content
    story.append(Paragraph("<br/><br/>" * 3, styles["Normal"]))

    # Content sections
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading1"],
        fontSize=20,
        spaceBefore=24,
        spaceAfter=14,
        textColor=INFO_BLUE,
        keepWithNext=True,
    )
    story.append(Paragraph("Model Evaluation Results", section_style))

    # Results table with pass/fail indicators
    for result in results:
        status_color = PASS_GREEN if result.success else FAIL_RED
        status_text = "✓ PASS" if result.success else "✗ FAIL"

        model_header = ParagraphStyle(
            "ModelHeader",
            parent=styles["Heading2"],
            fontSize=14,
            spaceBefore=18,
            spaceAfter=8,
            textColor=status_color,
            leftIndent=0,
        )
        story.append(Paragraph(f"{result.model_name} - {status_text}", model_header))

        # Model metrics table
        metrics_data = [
            ["Metric", "Value", "Status"],
            ["Average Time", f"{result.avg_time:.3f}s", "✓" if result.avg_time < 25 else "⚠"],
            ["Min Time", f"{result.min_time:.3f}s", "✓"],
            ["Max Time", f"{result.max_time:.3f}s", "✓" if result.max_time < 45 else "⚠"],
            ["Tests Passed", f"{sum(1 for t in result.tests if t['success'])}/{len(result.tests)}", status_text],
        ]

        for test in result.tests:
            test_status = "✓ PASS" if test["success"] else "✗ FAIL"
            metrics_data.append([
                f"Test: {test['type']}",
                f"{test['time']:.3f}s ({test.get('response_length', 0)} chars)",
                test_status,
            ])

        metrics_table = Table(metrics_data, colWidths=[2.2*inch, 2.3*inch, 1.2*inch])
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INFO_BLUE),
            ("TEXTEVAL", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), colors.Color(0.98, 0.98, 0.98, 0.5)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 12))

    # Summary section
    story.append(Paragraph("Overall Summary", section_style))

    summary_data = [["Model", "Provider", "Avg Time", "Status", "Response Quality"]]

    for r in results:
        status = "✓ PASS" if r.success else "✗ FAIL"
        avg_resp = sum(t.get("response_length", 0) for t in r.tests) / len(r.tests)
        summary_data.append([r.model_name, "ollama", f"{r.avg_time:.2f}s", status, f"{int(avg_resp)} chars"])

    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.2*inch, 0.8*inch, 1*inch, 1.2*inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PASS_GREEN),
        ("TEXTEVAL", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), colors.Color(0.95, 0.95, 0.95, 0.5)),
        ("TEXTEVAL", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    doc.build(story)
    return output_path


def main():
    """Main entry point for Ollama model evaluation."""
    print("Wilson Eval3ngine - Ollama Model Evaluation")
    print("=" * 50)

    # Setup paths
    workspace = Path("/mnt/geezer-venvs/work/Wilson-Eval3ngine")
    output_dir = workspace / "docs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    logo_path = workspace / "static" / "images" / "we3-logo" / "64493cd5-d7b8-4737-b8ad-1245ae595ffd.png"
    logo_path = logo_path if logo_path.exists() else workspace / "static" / "images" / "we3-logo" / "we3-logo.png"

    # Test each model
    all_results: list[ModelTestResult] = []
    for model_id, model_name, description in BEST_MODELS:
        print(f"\nEvaluating {model_name}...")
        result = test_model(model_id, model_name)
        status = "✓ PASS" if result.success else "✗ FAIL"
        print(f"  Status: {status}")
        print(f"  Avg Time: {result.avg_time:.3f}s")
        print(f"  Tests: {sum(1 for t in result.tests if t['success'])}/{len(result.tests)} passed")
        all_results.append(result)

    # Generate PDF report
    now = datetime.now(timezone.utc)
    pdf_path = output_dir / f"ollama-models-evaluation-{now.strftime('%Y%m%d-%H%M%S')}.pdf"
    print(f"\nGenerating PDF report: {pdf_path}")
    generate_model_pdf(all_results, pdf_path, logo_path)

    # Summary
    passed = sum(1 for r in all_results if r.success)
    print(f"\n{'=' * 50}")
    print(f"Evaluation Complete: {passed}/{len(all_results)} models passed")
    print(f"PDF Report: {pdf_path}")

    return all_results


if __name__ == "__main__":
    results = main()