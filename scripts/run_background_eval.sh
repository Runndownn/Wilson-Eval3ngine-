#!/bin/bash
# Wilson Eval3ngine - Model Evaluation Background Runner

cd ~/wilson-eval3ngine

# Install dependencies if needed
pip install reportlab 2>/dev/null || true

# Run evaluation in background
nohup python3 ~/wilson-eval3ngine/llm_evaluator.py > ~/wilson-eval3ngine/eval-output.log 2>&1 &

echo "Evaluation running in background"
echo "Monitor with: tail -f ~/wilson-eval3ngine/eval-output.log"
echo "Status file: ~/wilson-eval3ngine/reports/evaluation_complete.json"
echo "Reports dir: ~/wilson-eval3ngine/reports/"