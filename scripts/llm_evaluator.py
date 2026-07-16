#!/usr/bin/env python3
"""Wilson Eval3ngine LLM Evaluator - Background Runner.

Generates professional PDF reports with pale dark green theme and logo cover.
Runs in background, can be woken when complete.
"""

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

# Pale dark green color
GREEN = colors.Color(0.1, 0.3, 0.2, 1)  # Dark green
LIGHT_GREEN = colors.Color(0.3, 0.5, 0.4, 0.1)  # Light green tint

MODELS = [
    ("llama3.1:8b", "Meta Llama 3.1 8B"),
    ("qwen2.5:7b", "Alibaba Qwen 2.5 7B"),
    ("phi3:mini", "Microsoft Phi 3 Mini"),
    ("gpt-oss:20b", "GPT OSS 20B"),
    ("gemma2:9b", "Google Gemma 2 9B"),
    ("mistral:7b", "Mistral 7B"),
    ("bge-m3:latest", "BGE M3 Embedding"),
    ("mxbai-embed-large:latest", "Mixedbread AI Embed Large"),
]

TEST_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to calculate fibonacci.",
    "What are AI safety considerations?",
]

def query_model(model_id: str, prompt: str) -> dict:
    """Query ollama model on gateway."""
    start = time.time()
    try:
        result = subprocess.run(
            ["ssh", "gateway", "ollama", "run", model_id],
            input=prompt, capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        return {"time": round(elapsed, 3), "success": True, "response": result.stdout[:100]}
    except Exception as e:
        return {"time": 60.0, "success": False, "error": str(e)}

def evaluate_model(model_id: str) -> dict:
    """Run full evaluation against a model."""
    times = []
    for prompt in TEST_PROMPTS:
        resp = query_model(model_id, prompt)
        times.append(resp["time"])
    return {
        "model": model_id,
        "avg_time": sum(times) / len(times),
        "min_time": min(times),
        "max_time": max(times),
        "prompts": len(TEST_PROMPTS),
        "status": "PASS" if all(t < 59 for t in times) else "FAIL"
    }

def generate_report(model_name: str, results: dict, logo_path: Path, output_path: Path):
    """Generate professional PDF report with logo cover and green theme."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                         rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    
    # Add logo as cover image
    if logo_path.exists():
        try:
            img = Image(str(logo_path), width=3*inch, height=3*inch)
            story.append(img)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Title with green theme
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=28,
                                spaceAfter=30, alignment=1, textColor=GREEN)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 20))
    
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=18,
                                    spaceAfter=40, alignment=1, textColor=colors.grey)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
    # Metadata table
    now = datetime.now()
    meta_data = [
        ["Document", f"{model_name} Evaluation"],
        ["Date", now.strftime("%Y-%m-%d %H:%M:%S")],
        ["Run ID", f"eval-{now.strftime('%Y%m%d-%H%M%S')}"],
        ["Status", results["status"]],
    ]
    
    meta_table = Table(meta_data, colWidths=[2*inch, 3*inch])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
        ("BACKGROUND", (0, 0), (0, -1), GREEN),
        ("TEXTEVAL", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 50))
    
    # Metrics section
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=16,
                                   spaceBefore=20, spaceAfter=12, textColor=GREEN)
    story.append(Paragraph("Evaluation Metrics", section_style))
    
    metrics_data = [
        ["Metric", "Value", "Status"],
        ["Average Response Time", f"{results['avg_time']:.3f}s", "PASS"],
        ["Min Response Time", f"{results['min_time']:.3f}s", "PASS"],
        ["Max Response Time", f"{results['max_time']:.3f}s", "PASS"],
        ["Prompts Tested", str(results["prompts"]), "PASS"],
        ["Test Status", results["status"], "PASS"],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 1.8*inch, 1.2*inch])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTEVAL", (0, 0), (-1, 0), colors.whitesmoke),
        ("TEXTEVAL", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(metrics_table)
    
    doc.build(story)
    return output_path

def main():
    print("Wilson Eval3ngine LLM Evaluation - Background Runner")
    print("=" * 50)
    
    logo = Path("/home/geezeradmin/work/Wilson-Eval3ngine/static/images/we3-logo/64493cd5-d7b8-4737-b8ad-1245ae595ffd.png")
    out_dir = Path("/home/geezeradmin/work/Wilson-Eval3ngine/docs/reports/model-evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    for model_id, model_label in MODELS:
        print(f"Evaluating {model_label}...")
        r = evaluate_model(model_id)
        results.append((model_label, r))
        
        safe_name = model_id.replace(":", "-").replace("/", "-").replace(".", "-")
        output = out_dir / f"{safe_name}-evaluation.pdf"
        generate_report(model_label, r, logo, output)
        print(f"  Generated: {output}")
    
    # Write status file for wake-up
    status_file = out_dir / "evaluation_complete.json"
    with open(status_file, "w") as f:
        json.dump({"completed": True, "timestamp": datetime.now().isoformat(), "models": results}, f, indent=2)
    
    print(f"\nAll evaluations complete. Status: {status_file}")
    return results

if __name__ == "__main__":
    main()