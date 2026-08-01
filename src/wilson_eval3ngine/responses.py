"""Reasoning-aware response handler for Wilson Eval3ngine.

Handles the full spectrum of LLM response formats across providers:
- OpenAI-compatible: choices[0].message.content
- Ollama: message.content
- Reasoning models: choices[0].message.reasoning / reasoning_details
- Hybrid: both content and reasoning present

Also extracts reasoning token counts and metadata for telemetry and charting.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("we3.responses")


@dataclass
class ModelResponse:
    """Standardized response from any model provider.

    Attributes:
        text: The primary response text (content or reasoning, whichever is non-empty)
        content: The content field if present (may be None for reasoning models)
        reasoning: The reasoning field if present (may be None for non-reasoning models)
        reasoning_details: Full reasoning_details array from the provider
        is_reasoning: True if the response came from a reasoning model (content was null)
        has_both: True if both content and reasoning are present
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens (including reasoning)
        reasoning_tokens: Number of reasoning-specific tokens (if reported)
        total_tokens: Total tokens consumed
        model: The actual model returned by the provider (may differ from requested)
        provider: Provider name (e.g., "StepFun", "Google")
        finish_reason: OpenAI finish reason string
        raw: The full raw response dict for debugging
    """

    text: str = ""
    content: Optional[str] = None
    reasoning: Optional[str] = None
    reasoning_details: list[dict[str, Any]] = field(default_factory=list)
    is_reasoning: bool = False
    has_both: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    provider: str = ""
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_code(self) -> bool:
        """Check if the response contains code examples."""
        text = self.text or ""
        return "def " in text or "function" in text.lower() or "class " in text

    @property
    def has_security(self) -> bool:
        """Check if the response mentions security concepts."""
        text = (self.text or "").lower()
        return any(kw in text for kw in [
            "security", "vulnerability", "injection", "attack",
            "safe", "defense", "mitigation", "threat", "exploit",
        ])

    @property
    def response_length(self) -> int:
        """Character length of the primary response text."""
        return len(self.text)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for JSON storage."""
        return {
            "text": self.text,
            "content": self.content,
            "reasoning": self.reasoning,
            "reasoning_details": self.reasoning_details,
            "is_reasoning": self.is_reasoning,
            "has_both": self.has_both,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
        }


def parse_response(raw_data: dict[str, Any]) -> ModelResponse:
    """Parse a raw API response into a standardized ModelResponse.

    Handles OpenAI, Ollama, and reasoning-model response formats.
    """
    raw = dict(raw_data)
    result = ModelResponse(raw=raw)

    # Extract model and provider
    result.model = raw.get("model", "")
    result.provider = raw.get("provider", "")

    # Extract usage tokens
    usage = raw.get("usage", {})
    if usage:
        result.prompt_tokens = usage.get("prompt_tokens", 0)
        result.completion_tokens = usage.get("completion_tokens", 0)
        result.total_tokens = usage.get("total_tokens", 0)
        comp_details = usage.get("completion_tokens_details", {})
        result.reasoning_tokens = comp_details.get("reasoning_tokens", 0)

    # Extract message from choices (OpenAI format) or message (Ollama format)
    message = None
    choices = raw.get("choices")
    if choices and isinstance(choices, list) and len(choices) > 0:
        message = choices[0].get("message", {})
        result.finish_reason = choices[0].get("finish_reason", "")
    elif "message" in raw:
        message = raw.get("message", {})

    if not message:
        # Try top-level message for Ollama
        message = raw.get("message", {})

    content = message.get("content") if message else None
    reasoning = message.get("reasoning") if message else None
    reasoning_details = message.get("reasoning_details", []) if message else []

    # Determine response type
    if content and reasoning:
        result.has_both = True
        result.content = content
        result.reasoning = reasoning
        result.reasoning_details = reasoning_details
        # Prefer content as the primary text when both are present
        result.text = content
    elif reasoning and not content:
        result.is_reasoning = True
        result.reasoning = reasoning
        result.reasoning_details = reasoning_details
        result.text = reasoning
    elif content and not reasoning:
        result.content = content
        result.text = content
    else:
        # Neither content nor reasoning — check for error
        result.content = None
        result.reasoning = None
        result.text = ""

    return result


def extract_reasoning_text(response_data: dict[str, Any]) -> str:
    """Extract reasoning text from a response, checking multiple locations.

    Order of preference:
    1. choices[0].message.reasoning
    2. choices[0].message.reasoning_details (joined)
    3. message.reasoning
    """
    # OpenAI format
    choices = response_data.get("choices", [])
    if choices and isinstance(choices, list):
        msg = choices[0].get("message", {})
        reasoning = msg.get("reasoning")
        if reasoning:
            return reasoning
        # Check reasoning_details
        details = msg.get("reasoning_details", [])
        if details:
            texts = [d.get("text", "") for d in details if d.get("text")]
            if texts:
                return "\n".join(texts)

    # Ollama format
    msg = response_data.get("message", {})
    reasoning = msg.get("reasoning")
    if reasoning:
        return reasoning

    return ""


def get_primary_text(response_data: dict[str, Any]) -> str:
    """Get the primary text from a response, handling reasoning models.

    For reasoning models, the content field may be null while reasoning contains
    the actual response. This function checks both and returns whichever is non-empty.
    """
    # Try content first (standard)
    choices = response_data.get("choices", [])
    if choices and isinstance(choices, list):
        msg = choices[0].get("message", {})
        content = msg.get("content")
        if content:
            return content
        # Fall back to reasoning
        reasoning = msg.get("reasoning")
        if reasoning:
            return reasoning
        # Check reasoning_details
        details = msg.get("reasoning_details", [])
        if details:
            texts = [d.get("text", "") for d in details if d.get("text")]
            if texts:
                return "\n".join(texts)

    # Ollama format
    msg = response_data.get("message", {})
    content = msg.get("content")
    if content:
        return content
    reasoning = msg.get("reasoning")
    if reasoning:
        return reasoning

    return ""


def get_token_usage(response_data: dict[str, Any]) -> dict[str, int]:
    """Extract token usage from a response, including reasoning tokens.

    Returns a dict with:
    - prompt_tokens
    - completion_tokens
    - total_tokens
    - reasoning_tokens (if available)
    """
    usage = response_data.get("usage", {})
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}

    comp_details = usage.get("completion_tokens_details", {})
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "reasoning_tokens": comp_details.get("reasoning_tokens", 0),
    }
