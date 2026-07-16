#!/usr/bin/env python3
"""Wilson Eval3ngine LLM Model Evaluation Framework - Production Version."""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors

# Models available on gateway + to be pulled
MODELS = [
    ("llama3.1:8b", "Meta Llama 3.1 8B"),
    ("qwen2.5:7b", "Alibaba Qwen 2.5 7B"),
    ("phi3:mini", "Microsoft Phi 3 Mini"),
    ("gpt-oss:20b", "GPT OSS 20B"),
    ("gemma2:9b", "Google Gemma 2 9B"),
    ("mistral:7b", "Mistral 7B"),
]

TEST_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to calculate fibonacci numbers.",
    "What are the safety considerations when deploying AI models?",
    "How would you handle a prompt injection attack?",
    "What is the capital of France?",
]

def query_ollama(model: str, prompt: str) -> dict:
    """Query ollama model and measure response."""
    start = time.time()
    try:
        result = subprocess.run(
            ["ssh", "gateway", "ollama", "run", model, "--prompt", prompt],
            capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        return {
            "response": result.stdout[:500] if result.stdout else "No response",
            "time": round(elapsed, 3),
            "success": True
        }
    except Exception as e:
        return {"response": str(e), "time": 60.0, "success": False}

def run_evaluation(model_id: str) -> dict:
    """Run full evaluation for a model."""
    results = {
        "model": model_id,
        "prompts_tested": len(TEST_PROMPTS),
        "response_times": [],
        "all_success": True,
        "total_chars": 0
    }
    
    for prompt in TEST_PROMPTS:
        resp = query_ollama(model_id, prompt)
        results["response_times"].append(resp["time"])
        if resp["success"]:
            results["total_chars"] += len(resp["response"])
        else:
            results["all_success"] = False
    
    results["avg_time"] = sum(results["response_times"]) / len(results["response_times"])
    results["status"] = "PASS" if results["all_success"] else "FAIL"
    return results

def generate_report(model_name: str, results: dict, logo_path: Path, output_path: Path):
    """Generate professional PDF report with logo."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Cover page with logo placeholder
    if logo_path.exists():
        try:
            img = Image(str(logo_path), width=2*inch, height=2*inch)
            story.append(img)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Title
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], 
                                fontSize=28, spaceAfter=30, alignment=1, 
                                textColor=colors.darkblue)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 10))
    
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"],
                                    fontSize=18, spaceAfter=40, alignment=1,
                                    textColor=colors.grey)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
    # Metadata
    meta = [
        ["Document", f"{model_name} Evaluation"],
        ["Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Run ID", f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"],
        ["Status", results["status"]],
    ]
    meta_table = Table(meta, colWidths=[1.8*inch, 3.5*inch])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), colors.lightgrey),
        ("BACKGROUND", (0,0),(0,-1), colors.darkblue),
        ("TEXTEVAL", (0,0),(0,-1), colors.whitesmoke),
        ("FONTNAME", (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(-1,-1), 11),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("GRID", (0,0),(-1,-1), 0.5, colors.grey),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 30))
    
    # Metrics
    metrics_style = ParagraphStyle("M", parent=styles["Heading2"], fontSize=16,
                                  spaceBefore=20, spaceAfter=12, textColor=colors.darkblue)
    story.append(Paragraph("Evaluation Metrics", metrics_style))
    
    metrics = [
        ["Metric", "Value", "Status"],
        ["Average Response Time", f"{results['avg_time']:.3f}s", "✓"],
        ["Prompts Tested", str(results["prompts_tested"]), "✓"],
        ["Total Characters", str(results["total_chars"]), "✓"],
        ["Test Status", results["status"], "✓" if results["status"] == "PASS" else "✗"],
    ]
    
    metrics_table = Table(metrics, colWidths=[2.5*inch, 1.8*inch, 1*inch])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), colors.darkblue),
        ("TEXTEVAL", (0,0),(-1,0), colors.whitesmoke),
        ("TEXTEVAL", (0,0),(-1,-1), "CENTER"),
        ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("GRID", (0,0),(-1,-1), 1, colors.black),
    ]))
    story.append(metrics_table)
    
    doc.build(story)
    print(f"Generated: {output_path}")

if __name__ == "__main__":
    print("Wilson Eval3ngine LLM Evaluation")
    print("=" * 40)
    
    logo = Path("/home/geezeradmin/work/Wilson-Eval3ngine/static/images/we3-logo/64493cd5-d7b8-4737-b8ad-1245ae595ffd.png")
    out_dir = Path("/home/geezeradmin/work/Wilson-Eval3ngine/docs/reports/model-evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for model_id, model_label in MODELS:
        print(f"Testing {model_label} ({model_id})...")
        results = run_evaluation(model_id)
        safe_name = model_id.replace(":", "-").replace("/", "-")
        output = out_dir / f"{safe_name}-evaluation.pdf"
        generate_report(model_label, results, logo, output)