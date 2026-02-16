"""Unit tests for the Dex agent package.

Tests validate:
- System prompt content (anti-hallucination rules, model listing, etc.)
- Model creation configuration (Gemini 2.5 Flash, temperature=0)

All tests are unit-level -- no LLM calls or MCP connections needed.
"""

from __future__ import annotations

import os

import pytest

from backend.src.agent.prompts import SYSTEM_PROMPT


# ---------- System prompt content tests ----------


def test_system_prompt_contains_anti_hallucination_rules():
    """System prompt must contain critical anti-hallucination instructions."""
    assert "NEVER fabricate" in SYSTEM_PROMPT
    assert "ALWAYS use tools" in SYSTEM_PROMPT


def test_system_prompt_lists_all_manufacturers():
    """System prompt must mention all 3 manufacturers."""
    assert "Sundance" in SYSTEM_PROMPT
    assert "Hot Spring" in SYSTEM_PROMPT
    assert "Bullfrog" in SYSTEM_PROMPT


ALL_19_MODELS = [
    # Sundance (7)
    "Altamar",
    "Aspen",
    "Cameo",
    "Capris",
    "Marin",
    "Optima",
    "Vistamar",
    # Hot Spring (8)
    "Aria",
    "Envoy",
    "Grandee",
    "Jetsetter",
    "Jetsetter LX",
    "Prodigy",
    "Sovereign",
    "Vanguard",
    # Bullfrog (4)
    "M6",
    "M7",
    "M8",
    "M9",
]


@pytest.mark.parametrize("model_name", ALL_19_MODELS)
def test_system_prompt_lists_all_19_models(model_name: str):
    """System prompt must list every one of the 19 POC model names."""
    assert model_name in SYSTEM_PROMPT, (
        f"Model '{model_name}' not found in SYSTEM_PROMPT"
    )


def test_system_prompt_contains_out_of_scope_handling():
    """System prompt must instruct agent on out-of-scope queries."""
    prompt_lower = SYSTEM_PROMPT.lower()
    assert "pricing" in prompt_lower
    assert "out of scope" in prompt_lower or "out-of-scope" in prompt_lower


def test_system_prompt_contains_not_available_handling():
    """System prompt must instruct agent on not-available fields."""
    assert "not_available_fields" in SYSTEM_PROMPT


# ---------- Model creation tests ----------


def test_create_model_returns_gemini_instance(monkeypatch):
    """_create_model returns a ChatGoogleGenerativeAI instance with gemini-2.5-flash."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")

    from langchain_google_genai import ChatGoogleGenerativeAI

    from backend.src.agent.graph import _create_model

    model = _create_model()
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert "gemini-2.5-flash" in model.model


def test_create_model_temperature_zero(monkeypatch):
    """_create_model sets temperature to 0 for deterministic outputs."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")

    from backend.src.agent.graph import _create_model

    model = _create_model()
    assert model.temperature == 0
