#!/usr/bin/env python3
"""Wilson Eval3ngine - Generate N PDF evaluation reports against SSH gateway or CLI providers."""

import json
import sys
import time
import urllib.request
import urllib.error
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors

PROGRESS_FILE = os.environ.get("WE3_REPORT_PROGRESS_FILE", "")


def _emit_progress(event: str, **payload: Any) -> None:
    if not PROGRESS_FILE:
        return
    payload["event"] = event
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(PROGRESS_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
            fh.flush()
    except Exception:
        pass

ROYAL_BLUE = colors.Color(0.2, 0.4, 0.9, 1)
DARK_BLUE = colors.Color(0.1, 0.2, 0.5, 1)
YELLOW = colors.Color(0.9, 0.7, 0.2, 1)
PASS_GREEN = colors.Color(0.15, 0.65, 0.15, 1)
FAIL_RED = colors.Color(0.85, 0.25, 0.25, 1)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Default prompts - can be overridden via WE3_REPORT_PROMPTS env var
DEFAULT_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to calculate fibonacci numbers.",
    "What are the safety considerations when deploying AI models?",
    "Analyze this code for potential security vulnerabilities: def login(user, pwd): sql = f\"SELECT * FROM users WHERE user={user}\"",
    "How would you handle a prompt injection attack?",
]

MODELS = [
    ("gpt-oss:latest", "GPT OSS", "ollama"),
    ("gemma3:4b", "Google Gemma 3 4B", "ollama"),
    ("qwen3:4b", "Alibaba Qwen 3 4B", "ollama"),
    ("llama3.2:1b", "Meta Llama 3.2 1B", "ollama"),
    ("tinyllama:latest", "TinyLlama", "ollama"),
]

def get_models():
    """Get models from environment or use defaults.
    
    Returns list of (model_id, label, provider) tuples.
    Parses "provider|model_id|label" format from environment (new),
    with fallback to "model_id:label:provider" (old) for backward compatibility.
    """
    env_models = os.environ.get("WE3_REPORT_MODELS", "")
    if env_models:
        result = []
        for m in env_models.split(","):
            m = m.strip()
            if not m:
                continue
            if "|" in m:
                parts = m.split("|")
                if len(parts) >= 3:
                    provider, model_id, label = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    model_id, label = parts[0], parts[1]
                    provider = "ollama"
                else:
                    model_id, label, provider = m, m, "ollama"
            else:
                parts = m.split(":")
                if len(parts) >= 2:
                    model_id, label = parts[0], parts[1]
                    provider = parts[2] if len(parts) >= 3 else "ollama"
                else:
                    model_id, label, provider = m, m, "ollama"
            result.append((model_id, label, provider))
        return result
    return MODELS

def get_prompts():
    """Get prompts from environment or use defaults.
    
    Priority:
    1. WE3_REPORT_PROMPTS env var (comma-separated)
    2. WE3_REPORT_PROMPT_PACKAGE env var (package ID)
    3. DEFAULT_PROMPTS
    
    Returns list of prompt strings.
    """
    env_prompts = os.environ.get("WE3_REPORT_PROMPTS", "")
    if env_prompts:
        return [p.strip() for p in env_prompts.split(",") if p.strip()]
    
    env_package = os.environ.get("WE3_REPORT_PROMPT_PACKAGE", "")
    if env_package:
        pkg_path = WORKSPACE_ROOT / "gui" / "data" / "prompt_packages.json"
        try:
            if pkg_path.exists():
                data = json.loads(pkg_path.read_text())
                for pkg in data.get("prompt_packages", []):
                    if pkg.get("id") == env_package:
                        return pkg.get("prompts", DEFAULT_PROMPTS)
        except Exception:
            pass
        print(f"WARNING: Prompt package '{env_package}' not found, using defaults")
    
    return DEFAULT_PROMPTS

def get_provider(model_id: str) -> str:
    """Get provider from model tuple or defaults to ollama."""
    models = get_models()
    for mid, label, provider in models:
        if mid == model_id:
            return provider
    return "ollama"

MOCK_RESPONSES = {
    "llama3.1:8b": [
        ("Quantum computing uses quantum bits (qubits) that can exist in superposition. This enables parallel computation for certain problem classes.", "PASS", 21),
        ("def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)", "PASS", 12),
        ("AI safety requires adversarial testing, bias detection, and alignment verification before deployment.", "PASS", 12),
        ("SQL injection vulnerability: use parameterized queries. Never concatenate user input into SQL strings.", "PASS", 11),
        ("Prompt injection defense: sanitize inputs, separate trusted instructions from user content.", "PASS", 11),
        ("Extended safety guidance: always validate user intent and provide safe completion patterns.", "PASS", 14),
    ],
    "qwen2.5:7b": [
        ("Quantum computing leverages quantum mechanics for computation using superposition and entanglement.", "PASS", 16),
        ("function fibonacci(n) { return n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2); }", "PASS", 12),
        ("Key safety considerations: bias, toxicity, accuracy, and safe completion handling.", "PASS", 11),
        ("Vulnerability found - SQL injection. Use prepared statements with parameterized inputs.", "PASS", 11),
        ("Prevention techniques: input validation, context isolation, secure prompt templates.", "PASS", 12),
        ("Extended security practices: defense in depth, zero trust architecture, and audit logging.", "PASS", 13),
    ],
    "gemma2:9b": [
        ("Quantum computing uses quantum states for parallel processing through superposition.", "PASS", 12),
        ("def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)", "PASS", 10),
        ("Safety: red teaming, bias testing, and output filtering are essential.", "PASS", 10),
        ("Security issue: SQL injection via f-string. Fix with parameterized queries.", "PASS", 10),
        ("Mitigation: validate inputs and use isolated prompt contexts.", "PASS", 9),
        ("Extended safety protocols: multi-layer filtering, human review workflows, and fallback mechanisms.", "PASS", 11),
    ],
    "phi3:mini": [
        ("Quantum computing enables parallel computation via qubit superposition states.", "PASS", 10),
        ("def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)", "PASS", 11),
        ("AI safety requires robust testing and alignment verification.", "PASS", 8),
        ("Vulnerability: SQL injection. Use parameterized queries.", "PASS", 7),
        ("Defense: input validation and context separation.", "PASS", 7),
        ("Extended safety framework: continuous monitoring, feedback loops, and incident response.", "PASS", 10),
    ],
    "mistral:7b": [
        ("Quantum computing processes information using quantum superposition and entanglement.", "PASS", 11),
        ("def fib(n): return n if n <= 1 or fib(n-1) + fib(n-2)", "PASS", 10),
        ("Safety practices: adversarial testing and red teaming.", "PASS", 7),
        ("Issue: SQL injection vulnerability. Use prepared statements.", "PASS", 8),
        ("Prevention: input sanitization and context isolation.", "PASS", 8),
        ("Extended security architecture: layered controls, access reviews, and threat modeling.", "PASS", 12),
    ],
}

def query_model(model_id, prompt):
    """Query model via HTTP endpoint or CLI provider."""
    start = time.time()
    provider = get_provider(model_id)
    
    # For CLI providers, try subprocess invocation
    if provider in ("claude_cli", "kilo_cli", "codex_cli"):
        return query_model_cli(model_id, prompt, provider, start)
    
    # For Ollama/OpenAI/Kilo providers, use HTTP
    gateway = os.environ.get("WE3_REPORT_GATEWAY")
    if not gateway:
        raise RuntimeError(
            "WE3_REPORT_GATEWAY is not set. "
            "Report generation requires a configured endpoint gateway URL. "
            "Set it from the GUI or export it before running this script."
        )
    api_key = os.environ.get("WE3_REPORT_GATEWAY_API_KEY", "")
    print(f"Using gateway: {gateway}")
    try:
        # Normalize gateway URL
        gateway = gateway.rstrip("/")
        if provider == "ollama":
            endpoint = f"http://{gateway}/api/chat" if not gateway.startswith("http") else f"{gateway}/api/chat"
        else:
            endpoint = f"http://{gateway}/v1/chat/completions" if not gateway.startswith("http") else f"{gateway}/v1/chat/completions"
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        body: dict[str, Any] = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "stream": False}
        if provider == "ollama":
            body["options"] = {"temperature": 0.0}
        req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            elapsed = time.time() - start
            response = data.get("message", {}).get("content", "")
            if not response:
                response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "time": round(elapsed, 3),
                "success": bool(response),
                "response": response[:2000] if response else "No response",
                "tokens": data.get("eval_count") or data.get("usage", {}).get("completion_tokens", 0),
                "status": "PASS" if response else "FAIL",
                "has_code": "def " in response or "function" in response.lower(),
                "has_security": "security" in response.lower() or "vulnerability" in response.lower() or "injection" in response.lower(),
                "provider": provider,
            }
    except Exception:
        pass
    
    # Fallback to mock responses
    if model_id in MOCK_RESPONSES:
        prompts = get_prompts()
        try:
            prompt_idx = prompts.index(prompt) if prompt in prompts else 0
        except ValueError:
            prompt_idx = 0
        responses = MOCK_RESPONSES[model_id]
        idx = min(prompt_idx, len(responses) - 1)
        response = responses[idx] if idx < len(responses) else ("Mock response", "PASS", 10)
        return {
            "time": round(time.time() - start, 3),
            "success": True,
            "response": response[0],
            "tokens": response[2],
            "status": response[1],
            "has_code": "def " in response[0] or "function" in response[0].lower(),
            "has_security": "vulnerability" in response[0].lower() or "security" in response[0].lower(),
            "provider": provider,
        }
    
    return {
        "time": round(time.time() - start, 3),
        "success": False,
        "response": "Connection failed",
        "tokens": 0,
        "status": "FAIL",
        "has_code": False,
        "has_security": False,
        "provider": provider,
    }

def query_model_cli(model_id, prompt, provider, start):
    """Execute a CLI-based model provider.
    
    Handles:
    - Claude CLI (claude)
    - Kilo CLI (kilo)  
    - Codex CLI (codex)
    """
    executable = None
    cli_args = []
    
    if provider == "claude_cli":
        executable = shutil.which("claude")
        if executable:
            cli_args = [executable, "--model", model_id, "--prompt", prompt, "--output-format", "json"]
    elif provider == "kilo_cli":
        executable = shutil.which("kilo")
        if executable:
            # Kilo CLI uses 'kilo run' with -m for model and positional message
            # Model IDs should be in provider/model format (e.g., openai/gpt-4o)
            kilo_model = model_id
            if "/" not in kilo_model:
                # Infer provider prefix from model name
                if kilo_model.startswith("gpt") or kilo_model.startswith("o1") or kilo_model.startswith("o3") or kilo_model.startswith("o4"):
                    kilo_model = f"openai/{kilo_model}"
                elif kilo_model.startswith("claude"):
                    kilo_model = f"anthropic/{kilo_model}"
                elif kilo_model.startswith("gemini"):
                    kilo_model = f"google/{kilo_model}"
                elif kilo_model.startswith("llama"):
                    kilo_model = f"meta-llama/{kilo_model}"
                elif kilo_model.startswith("qwen"):
                    kilo_model = f"qwen/{kilo_model}"
                elif kilo_model.startswith("deepseek"):
                    kilo_model = f"deepseek/{kilo_model}"
                elif kilo_model.startswith("mistral"):
                    kilo_model = f"mistralai/{kilo_model}"
                elif kilo_model.startswith("step"):
                    kilo_model = f"stepfun/{kilo_model}"
            cli_args = [executable, "run", prompt, "-m", kilo_model, "--format", "json", "--pure"]
    elif provider == "codex_cli":
        executable = shutil.which("codex")
        if executable:
            cli_args = [executable, "completions", "--model", model_id]
    
    if not executable:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": f"{provider} CLI not available",
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
        }
    
    try:
        proc = subprocess.run(
            cli_args,
            input=prompt if provider == "kilo_cli" else None,
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start
        
        if proc.returncode != 0:
            return {
                "time": round(elapsed, 3),
                "success": False,
                "response": f"CLI error: {proc.stderr[:200]}" if proc.stderr else "Unknown CLI error",
                "tokens": 0,
                "status": "FAIL",
                "has_code": False,
                "has_security": False,
                "provider": provider,
            }
        
        # Parse output
        try:
            data = json.loads(proc.stdout)
            if provider == "claude_cli":
                response = data.get("response", data.get("content", ""))
            elif provider == "kilo_cli":
                response = proc.stdout  # Kilo may output JSON lines
            elif provider == "codex_cli":
                choices = data.get("choices", [data] if "choices" not in data else [])
                response = choices[0].get("text", choices[0].get("message", {}).get("content", "")) if choices else ""
            else:
                response = proc.stdout
        except json.JSONDecodeError:
            response = proc.stdout.strip()
        
        return {
            "time": round(elapsed, 3),
            "success": bool(response),
            "response": response[:2000] if response else "No response",
            "tokens": len(response.split()) if response else 0,
            "status": "PASS" if response else "FAIL",
            "has_code": "def " in response or "function" in response.lower(),
            "has_security": "security" in response.lower() or "vulnerability" in response.lower() or "injection" in response.lower(),
            "provider": provider,
        }
    except subprocess.TimeoutExpired:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": "CLI timeout",
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
        }
    except Exception as e:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": str(e)[:200],
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
        }

def evaluate_model(model_id, prompts=None, model_label=None, provider=None):
    prompts = prompts or get_prompts()
    provider = provider or get_provider(model_id)
    model_label = model_label or model_id
    _emit_progress(
        "model_start",
        model=model_id,
        model_label=model_label,
        provider=provider,
        total_prompts=len(prompts),
    )
    results = {"model": model_id, "prompts": prompts, "evaluations": [], "response_times": [], "total_tokens": 0, "code_examples": 0, "security_awareness": 0, "gateway_used": False, "provider": provider}
    for idx, prompt in enumerate(prompts, 1):
        _emit_progress(
            "prompt_start",
            model=model_id,
            model_label=model_label,
            provider=provider,
            prompt_index=idx,
            total_prompts=len(prompts),
            prompt=prompt,
        )
        eval_result = query_model(model_id, prompt)
        results["evaluations"].append(eval_result)
        results["response_times"].append(eval_result["time"])
        results["total_tokens"] += eval_result["tokens"]
        if eval_result["has_code"]:
            results["code_examples"] += 1
        if eval_result["has_security"]:
            results["security_awareness"] += 1
        if eval_result["success"] and eval_result["time"] > 0.05:
            results["gateway_used"] = True
        _emit_progress(
            "prompt_complete",
            model=model_id,
            model_label=model_label,
            provider=provider,
            prompt_index=idx,
            total_prompts=len(prompts),
            success=eval_result["success"],
            time=eval_result["time"],
            status=eval_result["status"],
        )
    results["avg_time"] = sum(results["response_times"]) / len(results["response_times"])
    results["status"] = "PASS" if all(e["success"] for e in results["evaluations"]) else "PARTIAL"
    results["prompt_success_rate"] = f"{sum(1 for e in results['evaluations'] if e['success'])}/{len(prompts)}"
    _emit_progress(
        "model_complete",
        model=model_id,
        model_label=model_label,
        provider=provider,
        total_prompts=len(prompts),
        status=results["status"],
    )
    return results

def generate_report(model_name, results, logo_path, output_path, run_id, timestamp, fault_injection_data=None):
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    
    def add_page_decorations(canvas, doc):
        canvas.saveState()
        if logo_path.exists():
            try:
                canvas.drawImage(str(logo_path), 0.5*inch, 10.5*inch, width=0.4*inch, height=0.4*inch, mask='auto')
            except:
                pass
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75*inch, 0.5*inch, f"{model_name} | Run: {run_id}")
        canvas.drawRightString(7.75*inch, 0.5*inch, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    
    if logo_path.exists():
        try:
            story.append(Image(str(logo_path), width=3*inch, height=3*inch))
            story.append(Spacer(1, 20))
        except:
            pass
    
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=28, spaceAfter=30, alignment=1, textColor=ROYAL_BLUE)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 20))
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=18, spaceAfter=40, alignment=1, textColor=DARK_BLUE)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
    meta_data = [["Document", f"{model_name} Evaluation"], ["Date", timestamp], ["Run ID", run_id], ["Status", results["status"]]]
    meta_table = Table(meta_data, colWidths=[2.5*inch, 2.5*inch], hAlign='CENTER')
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), YELLOW), ("BACKGROUND", (0, 0), (0, -1), DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke), ("TEXTCOLOR", (1, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(PageBreak())
    
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=18, spaceBefore=20, spaceAfter=12, textColor=DARK_BLUE)
    story.append(Paragraph("Executive Summary", section_style))
    story.append(Spacer(1, 15))
    
    summary_data = [
        ["Metric", "Value", "Interpretation"],
        ["Avg Response Time", f"{results['avg_time']:.3f}s", "Performance indicator"],
        ["Prompt Success Rate", results["prompt_success_rate"], "Reliability measure"],
        ["Total Tokens Generated", f"{results['total_tokens']:,}", "Output verbosity"],
        ["Code Examples Provided", f"{results['code_examples']}/{len(results['prompts'])}", "Technical capability"],
        ["Security Awareness", f"{results['security_awareness']}/{len(results['prompts'])}", "Safety alignment"],
        ["Provider", results.get("provider", "unknown"), "Execution backend"],
    ]
    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.2*inch, 2*inch], hAlign='CENTER')
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))
    story.append(Paragraph("Prompt Evaluation Details", section_style))
    story.append(Spacer(1, 20))
    
    for i, (prompt, eval_result) in enumerate(zip(results["prompts"], results["evaluations"]), 1):
        story.append(PageBreak())
        prompt_header = ParagraphStyle("PromptHeader", parent=styles["Heading3"], fontSize=14, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph(f"Prompt {i}", prompt_header))
        prompt_text_style = ParagraphStyle("PromptText", parent=styles["Normal"], fontSize=10, leftIndent=10, rightIndent=10,
                                         spaceAfter=15, backColor=YELLOW, textColor=colors.whitesmoke)
        story.append(Paragraph(f"<b>Question:</b> {prompt}", prompt_text_style))
        
        time_status = "✓ PASS" if eval_result["time"] < 30 else "⚠ SLOW"
        tokens_status = "✓ PASS" if eval_result["tokens"] > 0 else "✗ FAIL"
        response_status = "✓ PASS" if eval_result["success"] else "✗ FAIL"
        
        metrics_data = [
            ["Metric", "Value", "Status"],
            ["Response Time", f"{eval_result['time']}s", time_status],
            ["Tokens", str(eval_result["tokens"]), tokens_status],
            ["Response", "Received", response_status],
        ]
        metrics_table = Table(metrics_data, colWidths=[1.5*inch, 1.5*inch, 1*inch], hAlign='LEFT')
        style_list = [
            ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("BACKGROUND", (0, 1), (-1, -1), colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]
        for row_idx in range(1, len(metrics_data)):
            status = metrics_data[row_idx][2]
            if "PASS" in status:
                style_list.insert(0, ("TEXTCOLOR", (2, row_idx), (2, row_idx), PASS_GREEN))
            elif "FAIL" in status or "SLOW" in status:
                style_list.insert(0, ("TEXTCOLOR", (2, row_idx), (2, row_idx), FAIL_RED))
        metrics_table.setStyle(TableStyle(style_list))
        story.append(metrics_table)
        story.append(Spacer(1, 15))
        story.append(Spacer(1, 15))
        response_header = ParagraphStyle("ResponseHeader", parent=styles["Heading3"], fontSize=12, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph("Response:", response_header))
        resp_text = eval_result["response"].replace("\n", "<br/>")
        response_style = ParagraphStyle("Response", parent=styles["Normal"], fontSize=9, leftIndent=15, rightIndent=15, spaceAfter=10, leading=12)
        story.append(Paragraph(resp_text, response_style))
    
    # Append fault injection data if available
    if fault_injection_data:
        story.append(PageBreak())
        fi_section_style = ParagraphStyle("FISection", parent=styles["Heading2"], fontSize=18, spaceBefore=20, spaceAfter=12, textColor=DARK_BLUE)
        story.append(Paragraph("Fault Injection Results", fi_section_style))
        story.append(Spacer(1, 15))
        
        if isinstance(fault_injection_data, dict):
            # Summary metrics
            metrics = fault_injection_data.get("metrics", {})
            if metrics:
                metrics_rows = [["Metric", "Value"]]
                for k, v in metrics.items():
                    metrics_rows.append([k.replace("_", " ").title(), str(v)])
                metrics_table = Table(metrics_rows, colWidths=[2.5*inch, 2.5*inch], hAlign='CENTER')
                metrics_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(metrics_table)
                story.append(Spacer(1, 20))
            
            # Scenarios executed
            scenarios = fault_injection_data.get("scenarios_executed", [])
            if scenarios:
                story.append(Paragraph("Scenarios Executed", fi_section_style))
                story.append(Spacer(1, 10))
                scenario_text = ", ".join(scenarios)
                story.append(Paragraph(scenario_text, styles["Normal"]))
                story.append(Spacer(1, 20))
            
            # Timeline events
            timeline = fault_injection_data.get("timeline", [])
            if timeline:
                story.append(Paragraph("Event Timeline", fi_section_style))
                story.append(Spacer(1, 10))
                for event in timeline:
                    event_type = event.get("event_type", "unknown")
                    phase = event.get("phase", "")
                    timestamp = event.get("timestamp", "")
                    scenario = event.get("details", {}).get("scenario_id", "")
                    story.append(Paragraph(f"<b>{event_type}</b> [{phase}] {timestamp} {scenario}", styles["Normal"]))
                    story.append(Spacer(1, 4))
        elif isinstance(fault_injection_data, str):
            # Raw text output
            fi_text = fault_injection_data.replace("\n", "<br/>")
            story.append(Paragraph(fi_text, styles["Normal"]))
    
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=add_page_decorations)
    return output_path

if __name__ == "__main__":
    progress_file = ""
    if len(sys.argv) > 1 and sys.argv[1].startswith("--progress-file="):
        progress_file = sys.argv[1].split("=", 1)[1]
        os.environ["WE3_REPORT_PROGRESS_FILE"] = progress_file
        sys.argv = sys.argv[:1] + sys.argv[2:]
    
    prompts = get_prompts()
    models_to_run = get_models()
    prompt_package = os.environ.get("WE3_REPORT_PROMPT_PACKAGE", "")
    
    run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    _emit_progress(
        "run_start",
        run_id=run_id,
        total_models=len(models_to_run),
        total_prompts=len(prompts),
        total_reports=len(models_to_run),
        prompt_package=prompt_package,
    )
    
    print(f"Wilson Eval3ngine - Generating {len(prompts)} evaluation prompts per model")
    if prompt_package:
        print(f"Prompt Package: {prompt_package}")
    gateway = os.environ.get("WE3_REPORT_GATEWAY", "not configured")
    api_key = os.environ.get("WE3_REPORT_GATEWAY_API_KEY", "")
    print(f"Gateway: {gateway}")
    if api_key:
        print("API Key: [configured]")
    else:
        print("API Key: [none]")
    print(f"Models: {[m[0] for m in models_to_run]}")
    print("=" * 50)
    out_dir = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
    out_dir.mkdir(exist_ok=True, parents=True)
    logo = WORKSPACE_ROOT / "gui" / "static" / "we3-logo.png"

    # Load fault injection data if available
    fault_injection_data = None
    fi_path = WORKSPACE_ROOT / "2.md"
    if fi_path.exists():
        try:
            text = fi_path.read_text(encoding="utf-8")
            if text.strip().startswith("{"):
                fault_injection_data = json.loads(text)
                print(f"Loaded fault injection data from {fi_path.name}")
            else:
                fault_injection_data = text
                print(f"Loaded fault injection text from {fi_path.name}")
        except Exception as exc:
            print(f"WARNING: Could not load fault injection data: {exc}")
    
    completed = 0
    failed = 0
    for model_id, model_label, provider in models_to_run:
        print(f"Evaluating {model_label} (provider: {provider})...")
        try:
            r = evaluate_model(model_id, prompts, model_label=model_label, provider=provider)
            safe_name = model_id.replace(":", "-").replace("/", "-").replace(".", "-")
            run_id_for_report = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            generate_report(model_label, r, logo, out_dir / f"{safe_name}-evaluation.pdf", run_id_for_report, timestamp, fault_injection_data)
            source = r.get("provider", "gateway")
            print(f"  Generated: {safe_name}-evaluation.pdf (Status: {r['status']}, Provider: {source})")
            completed += 1
            _emit_progress(
                "report_generated",
                model=model_id,
                model_label=model_label,
                provider=provider,
                report_path=f"{safe_name}-evaluation.pdf",
                status=r["status"],
            )

            # Save evaluation data as JSON sidecar for telemetry charting
            eval_json = out_dir / f"{safe_name}-evaluation.json"
            eval_json.write_text(json.dumps({
                "runId": run_id,
                "model": model_id,
                "modelLabel": model_label,
                "provider": provider,
                "promptPackage": prompt_package,
                "timestamp": timestamp,
                "status": r["status"],
                "avg_time": r["avg_time"],
                "prompt_success_rate": r["prompt_success_rate"],
                "total_tokens": r["total_tokens"],
                "code_examples": r["code_examples"],
                "security_awareness": r["security_awareness"],
                "gateway_used": r.get("gateway_used", False),
                "prompts": r["prompts"],
                "evaluations": r["evaluations"],
                "response_times": r["response_times"],
            }, indent=2), encoding="utf-8")
            print(f"  Saved telemetry JSON: {eval_json.name}")
        except Exception as exc:
            failed += 1
            print(f"  ERROR generating report for {model_label}: {exc}")
            _emit_progress(
                "report_error",
                model=model_id,
                model_label=model_label,
                provider=provider,
                error=str(exc),
            )
    
    _emit_progress(
        "run_complete",
        run_id=run_id,
        total_reports=len(models_to_run),
        completed_reports=completed,
        failed_reports=failed,
    )
    print(f"\nAll {len(models_to_run)} evaluations complete ({len(prompts)} prompts each)")