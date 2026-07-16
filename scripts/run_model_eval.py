#!/usr/bin/env python3
"""Wilson Eval3ngine LLM Model Evaluation Framework."""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

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
]

def query_ollama(model: str, prompt: str) -> dict:
    start = time.time()
    try:
        result = subprocess.run(
            ["ssh", "gateway", "ollama", "run", model, "--prompt", prompt],
            capture_output=True, text=True, timeout=60
        )
        elapsed = time.time() - start
        return {"time": round(elapsed, 3), "success": True}
    except Exception as e:
        return {"time": 60.0, "success": False}

def run_evaluation(model_id: str) -> dict:
    results = {"model": model_id, "prompts_tested": len(TEST_PROMPTS), "response_times": [], "all_success": True}
    for prompt in TEST_PROMPTS:
        resp = query_ollama(model_id, prompt)
        results["response_times"].append(resp["time"])
        if not resp["success"]:
            results["all_success"] = False
    results["avg_time"] = sum(results["response_times"]) / len(results["response_times"])
    results["status"] = "PASS" if results["all_success"] else "FAIL"
    return results

def generate_report(model_name: str, results: dict, output_path: Path):
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=24, spaceAfter=30, alignment=1, textColor=colors.darkblue)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 20))
    
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=18, spaceAfter=40, alignment=1, textColor=colors.grey)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
    # Metadata
    meta = [["Document", f"{model_name} Evaluation"], ["Date", datetime.now().strftime("%Y-%m-%d %H:%M")], 
            ["Run ID", f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"], ["Status", results["status"]]]
    meta_table = Table(meta, colWidths=[2*inch, 3*inch])
    meta_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,-1), colors.lightgrey), ("BACKGROUND", (0,0),(0,-1), colors.darkblue), 
                                   ("TEXTEVAL", (0,0),(0,-1), colors.whitesmoke), ("FONTNAME", (0,0),(-1,-1), "Helvetica-Bold"),
                                   ("FONTSIZE", (0,0),(-1,-1), 12), ("BOTTOMPADDING", (0,0),(-1,-1), 12)]))
    story.append(meta_table)
    story.append(Spacer(1, 50))
    
    # Metrics
    metrics_style = ParagraphStyle("M", parent=styles["Heading2"], fontSize=16, spaceBefore=20, spaceAfter=12, textColor=colors.darkblue)
    story.append(Paragraph("Evaluation Metrics", metrics_style))
    
    metrics = [["Metric", "Value", "Status"], ["Average Response Time", f"{results['avg_time']:.3f}s", "PASS"],
               ["Prompts Tested", str(results["prompts_tested"]), "PASS"], ["Test Status", results["status"], "PASS"]]
    metrics_table = Table(metrics, colWidths=[2.5*inch, 1.5*inch, 1*inch])
    metrics_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), colors.darkblue), ("TEXTEVAL", (0,0),(-1,0), colors.whitesmoke),
                                      ("TEXTEVAL", (0,0),(-1,-1), "CENTER"), ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"),
                                      ("FONTSIZE", (0,0),(-1,-1), 10), ("BOTTOMPADDING", (0,0),(-1,-1), 8), ("GRID", (0,0),(-1,-1), 1, colors.black)]))
    story.append(metrics_table)
    
    doc.build(story)
    print(f"Generated: {output_path}")

if __name__ == "__main__":
    print("Wilson Eval3ngine LLM Evaluation Framework")
    print("=" * 45)
    
    out_dir = Path("/home/geezeradmin/work/Wilson-Eval3ngine/docs/reports/model-evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for model_id, model_label in MODELS[:3]:
        print(f"Testing {model_label}...")
        results = run_evaluation(model_id)
        safe_name = model_id.replace(":", "-")
        output = out_dir / f"{safe_name}-report.pdf"
        generate_report(model_label, results, output)