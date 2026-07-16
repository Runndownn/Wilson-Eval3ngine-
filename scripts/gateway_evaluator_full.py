#!/usr/bin/env python3
"""Wilson Eval3ngine LLM Evaluator - Production Version.

Generates comprehensive PDF reports with actual test results and analysis.
One prompt per page with professional layout.
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib import colors

# Neon Royal Blue for title (vibrant, rich)
ROYAL_BLUE = colors.Color(0.2, 0.4, 0.9, 1)  # Full intensity royal blue
# Darker Metallic Blue for section headings
DARK_BLUE = colors.Color(0.1, 0.2, 0.5, 1)  # Deep metallic blue
# Yellow highlight (original color)
YELLOW = colors.Color(0.9, 0.7, 0.2, 1)  # Original yellow-orange

# Mock responses for demonstrating report format when gateway is unavailable
MOCK_RESPONSES = {
    "llama3.1:8b": [
        ("Quantum computing is a complex topic, but I'll try to break it down in simple terms. It uses quantum bits (qubits) that can be in multiple states simultaneously through superposition, enabling parallel computation.", "PASS", 16),
        ("def fibonacci(n):\n    if n <= 0: return 0\n    if n == 1: return 1\n    return fibonacci(n-1) + fibonacci(n-2)", "PASS", 18),
        ("AI safety requires alignment testing, red teaming, and careful deployment controls. Key considerations include bias detection, adversarial robustness, and safe completion.", "PASS", 11),
        ("SQL injection vulnerability detected. Use parameterized queries instead of string interpolation in the login function. Never concatenate user input directly into SQL.", "PASS", 11),
        ("Prompt injection can be mitigated through proper input sanitization and separation of concerns. Treat prompt segments as inert text, not executable code.", "PASS", 13)
    ],
    "qwen2.5:7b": [
        ("Quantum computing uses qubits that can exist in superposition states. This allows quantum algorithms to evaluate multiple possibilities simultaneously, promising exponential speedups for certain problems.", "PASS", 16),
        ("function fibonacci(n) { return n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2); }", "PASS", 18),
        ("Safety considerations include bias detection, adversarial testing, and safe completion. Models must be tested against harmful content and edge cases.", "PASS", 11),
        ("Vulnerability found: direct SQL string interpolation. Recommendation: use prepared statements and parameterized queries for all database operations.", "PASS", 11),
        ("Prompt injection defense requires context isolation and input validation. Use separate channels for trusted instructions versus user content.", "PASS", 13)
    ],
    "phi3:mini": [
        ("Quantum computing uses quantum bits that can be both 0 and 1 simultaneously through superposition. This enables parallel computation impossible with classical bits.", "PASS", 16),
        ("def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)", "PASS", 18),
        ("AI safety involves safe exploration, robust testing, and alignment verification. Models must behave predictably under stress and adversarial conditions.", "PASS", 11),
        ("Security issue: SQL injection via f-string. Fix: use parameterized inputs instead of string formatting in database queries.", "PASS", 11),
        ("Handle prompt injection by validating inputs and using secure prompt templates. Never trust user content without verification.", "PASS", 13)
    ],
    "gpt-oss:20b": [
        ("Quantum computing is computing with quantum mechanical phenomena. Qubits leverage superposition and entanglement for computational advantages.", "PASS", 16),
        ("def fib(n): return n <= 1 and 1 or fib(n-1) + fib(n-2)", "PASS", 18),
        ("AI safety focuses on alignment, robustness, and interpretability. Models must be interpretable and aligned with human values.", "PASS", 11),
        ("The login function has SQL injection. Use parameterized queries to prevent malicious input from executing.", "PASS", 11),
        ("Prompt injection attacks can be prevented with proper sandboxing and input validation techniques.", "PASS", 13)
    ],
    "gemma2:9b": [
        ("Quantum computing harnesses quantum mechanics for computation. It processes information using quantum superposition and entanglement.", "PASS", 16),
        ("def fibonacci(n): a, b = 0, 1; [a, b] = [b, a+b] for _ in range(n); return a", "PASS", 18),
        ("Safety considerations: bias, toxicity, factual accuracy, and privacy. Models must be tested for harmful outputs.", "PASS", 11),
        ("Vulnerability: SQL injection. Solution: use parameterized queries and input validation.", "PASS", 11),
        ("Prompt injection requires careful prompt engineering and input filtering to prevent manipulation.", "PASS", 13)
    ],
    "mistral:7b": [
        ("Quantum computing uses quantum states for parallel computation. The principles of superposition and entanglement enable quantum advantage.", "PASS", 16),
        ("def fib(n): return n <= 1 or fib(n-1) + fib(n-2)", "PASS", 18),
        ("Safety: adversarial testing, red teaming, and output filtering. Models must be robust against attacks.", "PASS", 11),
        ("SQL injection in login function. Fix: use prepared statements with parameterized inputs.", "PASS", 11),
        ("Mitigation: context separation and input validation for prompt injection defense.", "PASS", 13)
    ],
    "bge-m3:latest": [
        ("Embedding model - quantum computing concepts vector representation.", "PASS", 7),
        ("fibonacci sequence embedding vector.", "PASS", 7),
        ("AI safety embedding vector.", "PASS", 7),
        ("SQL injection embedding vector.", "PASS", 7),
        ("Prompt injection embedding vector.", "PASS", 7)
    ],
    "mxbai-embed-large:latest": [
        ("Embedding model response vector.", "PASS", 7),
        ("fib function embedding vector.", "PASS", 7),
        ("Safety embedding vector.", "PASS", 7),
        ("Vulnerability embedding vector.", "PASS", 7),
        ("Injection embedding vector.", "PASS", 7)
    ],
    "gpt-oss:latest": [
        ("GPT OSS embedding model vector.", "PASS", 7),
        ("fibonacci embedding vector.", "PASS", 7),
        ("safety embedding vector.", "PASS", 7),
        ("vulnerability embedding vector.", "PASS", 7),
        ("prompt embedding vector.", "PASS", 7)
    ],
    "gptoss20b:latest": [
        ("GPT OSS 20B embedding vector.", "PASS", 7),
        ("fib embedding vector.", "PASS", 7),
        ("AI safety embedding vector.", "PASS", 7),
        ("SQL embedding vector.", "PASS", 7),
        ("injection embedding vector.", "PASS", 7)
    ]
}

MODELS = [
    ("llama3.1:8b", "Meta Llama 3.1 8B"),
    ("qwen2.5:7b", "Alibaba Qwen 2.5 7B"),
    ("phi3:mini", "Microsoft Phi 3 Mini"),
    ("gpt-oss:20b", "GPT OSS 20B"),
    ("gemma2:9b", "Google Gemma 2 9B"),
    ("mistral:7b", "Mistral 7B"),
    ("bge-m3:latest", "BGE M3 Embedding"),
    ("mxbai-embed-large:latest", "Mixedbread AI Embed Large"),
    ("gpt-oss:latest", "GPT OSS Latest"),
    ("gptoss20b:latest", "GPT OSS 20B Latest"),
]

TEST_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to calculate fibonacci numbers.",
    "What are the safety considerations when deploying AI models?",
    "Analyze this code for potential security vulnerabilities: def login(user, pwd): sql = f\"SELECT * FROM users WHERE user={user}\"",
    "How would you handle a prompt injection attack?",
]

GATEWAY = "10.133.7.211"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def query_model(model_id: str, prompt: str, use_mock: bool = False) -> dict:
    """Query ollama on gateway and capture full response."""
    start = time.time()
    
    # Use mock data if gateway unavailable or use_mock flag set
    if use_mock and model_id in MOCK_RESPONSES:
        time.sleep(0.05)  # Simulate response time
        responses = MOCK_RESPONSES[model_id]
        idx = TEST_PROMPTS.index(prompt) if prompt in TEST_PROMPTS else 0
        response = responses[idx] if idx < len(responses) else ("Mock response", "PASS", 10)
        elapsed = time.time() - start
        return {
            "time": round(elapsed, 3),
            "success": True,
            "response": response[0],
            "tokens": response[2],
            "status": response[1],
            "has_code": "def " in response[0] or "function" in response[0].lower(),
            "has_security": "security" in response[0].lower() or "vulnerability" in response[0].lower() or "injection" in response[0].lower()
        }
    
    for attempt in range(3):
        try:
            cmd = f'''echo '{prompt}' | ollama run {model_id} 2>/dev/null'''
            result = subprocess.run(["ssh", GATEWAY, cmd], capture_output=True, text=True, timeout=120)
            elapsed = time.time() - start
            response = result.stdout.strip() if result.stdout.strip() else "No response"
            if "Service Unavailable" in result.stdout or "server busy" in result.stdout.lower():
                if attempt < 2:
                    time.sleep(5)
                    continue
            if result.returncode != 0 and not result.stdout.strip():
                response = f"No response (exit code: {result.returncode})"
            tokens = len(response.split())
            success = bool(response.strip()) and "No response" not in response
            status = "PASS" if success else "FAIL"
            return {
                "time": round(elapsed, 3),
                "success": success,
                "response": response[:800],
                "tokens": tokens,
                "status": status,
                "has_code": "def " in response or "function" in response.lower(),
                "has_security": "security" in response.lower() or "vulnerability" in response.lower() or "injection" in response.lower()
            }
        except subprocess.TimeoutExpired:
            continue
        except Exception as e:
            if attempt == 2:
                return {"time": 120.0, "success": False, "error": str(e), "response": "Connection failed", "tokens": 0, "status": "FAIL", "has_code": False, "has_security": False}
    return {"time": 120.0, "success": False, "error": "Max retries", "response": "Service unavailable", "tokens": 0, "status": "FAIL", "has_code": False, "has_security": False}

def evaluate_model(model_id: str, use_mock: bool = False) -> dict:
    """Full evaluation with detailed metrics."""
    results = {
        "model": model_id,
        "prompts": TEST_PROMPTS,
        "evaluations": [],
        "response_times": [],
        "total_tokens": 0,
        "code_examples": 0,
        "security_awareness": 0
    }
    
    for prompt in TEST_PROMPTS:
        eval_result = query_model(model_id, prompt, use_mock=use_mock)
        results["evaluations"].append(eval_result)
        results["response_times"].append(eval_result["time"])
        results["total_tokens"] += eval_result["tokens"]
        if eval_result["has_code"]:
            results["code_examples"] += 1
        if eval_result["has_security"]:
            results["security_awareness"] += 1
    
    results["avg_time"] = sum(results["response_times"]) / len(results["response_times"])
    results["min_time"] = min(results["response_times"])
    results["max_time"] = max(results["response_times"])
    results["status"] = "PASS" if all(e["success"] for e in results["evaluations"]) else "PARTIAL"
    results["prompt_success_rate"] = f"{sum(1 for e in results['evaluations'] if e['success'])}/{len(TEST_PROMPTS)}"
    return results

def add_page_decorations(canvas, doc, model_name, run_id):
    """Add header logo and footer to each page."""
    canvas.saveState()
    
    # Header corner - small logo
    logo_path = WORKSPACE_ROOT / "static" / "images" / "we3-logo" / "64493cd5-d7b8-4737-b8ad-1245ae595ffd.png"
    if logo_path.exists():
        try:
            canvas.drawImage(str(logo_path), 0.5*inch, 10.5*inch, width=0.4*inch, height=0.4*inch, mask='auto')
        except:
            pass
    
    # Footer with model name and run ID
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.75*inch, 0.5*inch, f"{model_name} | Run: {run_id}")
    
    # Page number
    canvas.drawRightString(7.75*inch, 0.5*inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()

def generate_report(model_name: str, results: dict, logo_path: Path, output_path: Path):
    """Generate comprehensive PDF with one prompt per page, professional layout."""
    now = datetime.now()
    run_id = f"eval-{now.strftime('%Y%m%d-%H%M%S')}"
    
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    
    # Page callback for pages after cover
    def page_callback(canvas, doc):
        add_page_decorations(canvas, doc, model_name, run_id)
    
    # Cover Page
    if logo_path.exists():
        try:
            img = Image(str(logo_path), width=3*inch, height=3*inch)
            story.append(img)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Title - Royal Blue
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=28, spaceAfter=30, alignment=1, textColor=ROYAL_BLUE)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 20))
    
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=18, spaceAfter=40, alignment=1, textColor=DARK_BLUE)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
# Metadata on cover - centered (wider columns to fit long model names)
    meta_data = [["Document", f"{model_name} Evaluation"], ["Date", now.strftime("%Y-%m-%d %H:%M:%S")],
                 ["Run ID", run_id], ["Status", results["status"]]]
    meta_table = Table(meta_data, colWidths=[2.5*inch, 2.5*inch], hAlign='CENTER')
    meta_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,-1), YELLOW), ("BACKGROUND", (0,0),(0,-1), DARK_BLUE),
                                     ("TEXTCOLOR", (0,0),(0,-1), colors.whitesmoke), ("TEXTCOLOR", (1,0),(-1,-1), colors.black),
                                     ("FONTNAME", (0,0),(-1,-1), "Helvetica-Bold"),
                                     ("FONTSIZE", (0,0),(-1,-1), 10), ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
                                     ("ALIGN", (0,0),(-1,-1), "CENTER"),
                                     ("LEFTPADDING", (0,0),(-1,-1), 6), ("RIGHTPADDING", (0,0),(-1,-1), 6),
                                     ("TOPPADDING", (0,0),(-1,-1), 4), ("BOTTOMPADDING", (0,0),(-1,-1), 4)]))
    story.append(meta_table)
    
    # Page break to second page for Executive Summary
    story.append(PageBreak())
    
    # Executive Summary on page 2
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=18, spaceBefore=20, spaceAfter=12, textColor=DARK_BLUE)
    story.append(Paragraph("Executive Summary", section_style))
    story.append(Spacer(1, 15))
    
    summary_data = [["Metric", "Value", "Interpretation"],
                    ["Avg Response Time", f"{results['avg_time']:.3f}s", "Performance indicator"],
                    ["Prompt Success Rate", results["prompt_success_rate"], "Reliability measure"],
                    ["Total Tokens Generated", f"{results['total_tokens']:,}", "Output verbosity"],
                    ["Code Examples Provided", f"{results['code_examples']}/{len(TEST_PROMPTS)}", "Technical capability"],
                    ["Security Awareness", f"{results['security_awareness']}/{len(TEST_PROMPTS)}", "Safety alignment"]]
    
    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.2*inch, 2*inch], hAlign='CENTER')
    summary_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), YELLOW), ("TEXTCOLOR", (0,0),(-1,0), colors.whitesmoke),
                                      ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0),(-1,-1), 10),
                                      ("VALIGN", (0,0),(-1,-1), "MIDDLE"), ("ALIGN", (0,0),(-1,-1), "CENTER"),
                                      ("LEFTPADDING", (0,0),(-1,-1), 6), ("RIGHTPADDING", (0,0),(-1,-1), 6),
                                      ("TOPPADDING", (0,0),(-1,-1), 6), ("BOTTOMPADDING", (0,0),(-1,-1), 6),
                                      ("GRID", (0,0),(-1,-1), 0.5, colors.grey)]))
    story.append(summary_table)
    story.append(Spacer(1, 30))
    
    # Prompt Evaluation Details header (stays on this page, prompts start after)
    story.append(Paragraph("Prompt Evaluation Details", section_style))
    story.append(Spacer(1, 20))
    
    # Each prompt gets its own page (after the header page)
    for i, (prompt, eval_result) in enumerate(zip(TEST_PROMPTS, results["evaluations"]), 1):
        story.append(PageBreak())
        
        # Prompt header - Royal Blue for subtitles
        prompt_header = ParagraphStyle("PromptHeader", parent=styles["Heading3"], fontSize=14, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph(f"Prompt {i}", prompt_header))

        # Prompt text in a box - yellow background
        prompt_text_style = ParagraphStyle("PromptText", parent=styles["Normal"], fontSize=10, leftIndent=10, rightIndent=10, 
                                            spaceAfter=15, backColor=YELLOW, textColor=colors.whitesmoke)
        story.append(Paragraph(f"<b>Question:</b> {prompt}", prompt_text_style))

        # Metrics table - yellow header
        metrics_data = [
            ["Metric", "Value"],
            ["Response Time", f"{eval_result['time']}s"],
            ["Tokens", str(eval_result['tokens'])],
            ["Status", eval_result.get('status', 'PASS' if eval_result['success'] else 'FAIL')]
        ]
        metrics_table = Table(metrics_data, colWidths=[1.5*inch, 2*inch], hAlign='LEFT')
        metrics_table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), YELLOW), ("TEXTCOLOR", (0,0),(-1,0), colors.whitesmoke),
                                           ("BACKGROUND", (0,1),(-1,-1), colors.lightgrey),
                                           ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0),(-1,-1), 9),
                                           ("VALIGN", (0,0),(-1,-1), "MIDDLE"), ("ALIGN", (0,0),(-1,-1), "CENTER"),
                                           ("LEFTPADDING", (0,0),(-1,-1), 6), ("RIGHTPADDING", (0,0),(-1,-1), 6),
                                           ("TOPPADDING", (0,0),(-1,-1), 4), ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                                           ("GRID", (0,0),(-1,-1), 0.5, colors.grey)]))
        story.append(metrics_table)
        story.append(Spacer(1, 15))

        # Response section - Royal Blue for subtitles
        response_header = ParagraphStyle("ResponseHeader", parent=styles["Heading3"], fontSize=12, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph("Response:", response_header))
        
        # Response content in a styled box
        resp_text = eval_result["response"].replace("\n", "<br/>")
        response_style = ParagraphStyle("Response", parent=styles["Normal"], fontSize=9, leftIndent=15, rightIndent=15, 
                                       spaceAfter=10, leading=12)
        story.append(Paragraph(resp_text, response_style))
    
    # Build with page decorations
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=page_callback)
    return output_path

if __name__ == "__main__":
    import sys
    use_mock = "--mock" in sys.argv or "MOCK" in sys.argv
    
    print("Wilson Eval3ngine LLM Evaluation - Production")
    print(f"Mode: {'Mock Data' if use_mock else 'Live Gateway'}")
    print("=" * 50)
    
    out_dir = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
    out_dir.mkdir(exist_ok=True, parents=True)
    logo = WORKSPACE_ROOT / "static" / "images" / "we3-logo" / "64493cd5-d7b8-4737-b8ad-1245ae595ffd.png"
    
    for model_id, model_label in MODELS:
        print(f"Evaluating {model_label}...")
        r = evaluate_model(model_id, use_mock=use_mock)
        safe_name = model_id.replace(":", "-").replace("/", "-").replace(".", "-")
        generate_report(model_label, r, logo, out_dir / f"{safe_name}-evaluation.pdf")
        print(f"  Generated: {safe_name}-evaluation.pdf")
    
    print("All evaluations complete")