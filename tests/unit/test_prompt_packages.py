"""Tests for Wilson Eval3ngine prompt package propagation and GUI data flow."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from scripts.generate_5_reports import get_prompts, DEFAULT_PROMPTS


class TestPromptPackagePropagation:
    """Tests for prompt package loading and fallback behavior."""

    def test_default_prompts_when_no_env(self):
        """Test that default prompts are returned when no env vars are set."""
        # Ensure env vars are not set
        os.environ.pop("WE3_REPORT_PROMPTS", None)
        os.environ.pop("WE3_REPORT_PROMPT_PACKAGE", None)
        
        prompts = get_prompts()
        assert prompts == DEFAULT_PROMPTS
        assert len(prompts) == 5

    def test_env_prompts_override_defaults(self):
        """Test that WE3_REPORT_PROMPTS env var overrides defaults."""
        os.environ["WE3_REPORT_PROMPTS"] = "custom prompt 1, custom prompt 2"
        os.environ.pop("WE3_REPORT_PROMPT_PACKAGE", None)
        
        try:
            prompts = get_prompts()
            assert prompts == ["custom prompt 1", "custom prompt 2"]
        finally:
            os.environ.pop("WE3_REPORT_PROMPTS", None)

    def test_prompt_package_loads_from_json(self):
        """Test that a valid prompt package ID loads prompts from JSON."""
        os.environ.pop("WE3_REPORT_PROMPTS", None)
        os.environ["WE3_REPORT_PROMPT_PACKAGE"] = "security_awareness"
        
        try:
            prompts = get_prompts()
            # Should load from prompt_packages.json, not defaults
            assert prompts != DEFAULT_PROMPTS
            assert len(prompts) == 6
            assert "Analyze this code for potential security vulnerabilities" in prompts[0]
        finally:
            os.environ.pop("WE3_REPORT_PROMPT_PACKAGE", None)

    def test_prompt_package_fallback_to_defaults_when_missing(self):
        """Test that missing prompt package falls back to defaults."""
        os.environ.pop("WE3_REPORT_PROMPTS", None)
        os.environ["WE3_REPORT_PROMPT_PACKAGE"] = "nonexistent_package"
        
        try:
            prompts = get_prompts()
            # Should fall back to defaults when package not found
            assert prompts == DEFAULT_PROMPTS
        finally:
            os.environ.pop("WE3_REPORT_PROMPT_PACKAGE", None)

    def test_env_prompts_take_priority_over_package(self):
        """Test that WE3_REPORT_PROMPTS takes priority over WE3_REPORT_PROMPT_PACKAGE."""
        os.environ["WE3_REPORT_PROMPTS"] = "override prompt"
        os.environ["WE3_REPORT_PROMPT_PACKAGE"] = "security_awareness"
        
        try:
            prompts = get_prompts()
            assert prompts == ["override prompt"]
        finally:
            os.environ.pop("WE3_REPORT_PROMPTS", None)
            os.environ.pop("WE3_REPORT_PROMPT_PACKAGE", None)

    def test_prompt_package_with_corrupted_json(self):
        """Test that corrupted prompt_packages.json falls back to defaults."""
        os.environ.pop("WE3_REPORT_PROMPTS", None)
        os.environ["WE3_REPORT_PROMPT_PACKAGE"] = "security_awareness"
        
        # Temporarily corrupt the JSON file
        pkg_path = Path(__file__).resolve().parent.parent.parent / "gui" / "data" / "prompt_packages.json"
        if pkg_path.exists():
            original_content = pkg_path.read_text()
            try:
                pkg_path.write_text("not valid json{{{")
                prompts = get_prompts()
                assert prompts == DEFAULT_PROMPTS
            finally:
                pkg_path.write_text(original_content)
        else:
            pytest.skip("prompt_packages.json not found")
