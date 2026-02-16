"""Unit tests for the Dex multi-agent package.

Tests validate:
- Per-agent prompt content (supervisor routing, concierge clarification,
  specialist anti-hallucination rules, model listings, response format template)
- Model creation configuration (Gemini 2.5 Flash, temperature=0, max tokens)
- Deterministic validator behavior (no tool calls, short answers, null detection,
  source attribution, prose density / scannable format)

All tests are unit-level -- no LLM calls or MCP connections needed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.src.agent.prompts import (
    CONCIERGE_PROMPT,
    SPECIALIST_PROMPT,
    SUPERVISOR_PROMPT,
)
from backend.src.agent.validator import validate_response


# ---------- Specialist prompt content tests ----------


def test_specialist_prompt_contains_anti_hallucination_rules():
    """Specialist prompt must contain critical anti-hallucination instructions."""
    assert "NEVER fabricate" in SPECIALIST_PROMPT
    assert "ALWAYS use tools" in SPECIALIST_PROMPT


def test_specialist_prompt_lists_all_manufacturers():
    """Specialist prompt must mention all 3 manufacturers."""
    assert "Sundance" in SPECIALIST_PROMPT
    assert "Hot Spring" in SPECIALIST_PROMPT
    assert "Bullfrog" in SPECIALIST_PROMPT


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
def test_specialist_prompt_lists_all_19_models(model_name: str):
    """Specialist prompt must list every one of the 19 POC model names."""
    assert model_name in SPECIALIST_PROMPT, (
        f"Model '{model_name}' not found in SPECIALIST_PROMPT"
    )


def test_specialist_prompt_contains_out_of_scope_handling():
    """Specialist prompt must instruct agent on out-of-scope queries."""
    prompt_lower = SPECIALIST_PROMPT.lower()
    assert "pricing" in prompt_lower


def test_specialist_prompt_contains_not_available_handling():
    """Specialist prompt must instruct agent on not-available fields."""
    assert "not_available_fields" in SPECIALIST_PROMPT


def test_specialist_prompt_contains_tool_instructions():
    """Specialist prompt must reference all 3 MCP tools."""
    assert "list_models" in SPECIALIST_PROMPT
    assert "get_model_overview" in SPECIALIST_PROMPT
    assert "get_spec_category" in SPECIALIST_PROMPT


# ---------- Supervisor prompt tests ----------


def test_supervisor_prompt_routes_to_agents():
    """Supervisor prompt must reference both concierge and specialist agents."""
    assert "concierge" in SUPERVISOR_PROMPT
    assert "specialist" in SUPERVISOR_PROMPT


def test_supervisor_prompt_prefers_specialist():
    """Supervisor prompt must indicate most queries go to specialist."""
    prompt_lower = SUPERVISOR_PROMPT.lower()
    assert "most queries should go directly to specialist" in prompt_lower


# ---------- Concierge prompt tests ----------


def test_concierge_prompt_never_answers():
    """Concierge prompt must instruct to NEVER answer spec questions."""
    assert "NEVER answer spec questions" in CONCIERGE_PROMPT


def test_concierge_prompt_never_fabricates():
    """Concierge prompt must instruct to NEVER fabricate data."""
    assert "NEVER fabricate" in CONCIERGE_PROMPT


def test_concierge_prompt_lists_all_manufacturers():
    """Concierge prompt must mention all 3 manufacturers."""
    assert "Sundance" in CONCIERGE_PROMPT
    assert "Hot Spring" in CONCIERGE_PROMPT
    assert "Bullfrog" in CONCIERGE_PROMPT


@pytest.mark.parametrize("model_name", ALL_19_MODELS)
def test_concierge_prompt_lists_all_19_models(model_name: str):
    """Concierge prompt must list every one of the 19 POC model names."""
    assert model_name in CONCIERGE_PROMPT, (
        f"Model '{model_name}' not found in CONCIERGE_PROMPT"
    )


def test_concierge_prompt_mentions_list_models():
    """Concierge prompt must mention the list_models tool."""
    assert "list_models" in CONCIERGE_PROMPT


# ---------- Validator tests ----------


def _make_ai_message(content: str):
    """Create a mock AI message."""
    return SimpleNamespace(type="ai", content=content)


def _make_tool_message(name: str = "get_spec_category", content: str = "{}"):
    """Create a mock tool message."""
    return SimpleNamespace(type="tool", name=name, content=content)


def test_validate_response_no_tool_calls():
    """Validator warns when no tool call messages are present."""
    state = {
        "messages": [
            _make_ai_message("The Aspen uses a 2.5HP pump."),
        ]
    }
    warnings = validate_response(state)
    assert any("No tool calls" in w for w in warnings)


def test_validate_response_short_answer():
    """Validator warns when the AI response is too short."""
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message("OK"),
        ]
    }
    warnings = validate_response(state)
    assert any("too short" in w.lower() for w in warnings)


def test_validate_response_contains_null():
    """Validator warns when the AI response contains literal 'null'."""
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(
                "The Aspen pump part number is null according to our records."
            ),
        ]
    }
    warnings = validate_response(state)
    assert any("null" in w.lower() for w in warnings)


def test_validate_response_clean():
    """Validator returns no warnings for a proper response."""
    state = {
        "messages": [
            _make_tool_message("list_models", '{"models": [...]}'),
            _make_tool_message(
                "get_spec_category", '{"jet_pumps": {"hp": 2.5}}'
            ),
            _make_ai_message(
                "The Sundance Aspen uses a **2.5 HP** jet pump.\n"
                "- Wavemaster 8000\n"
                "- 1-speed, 56 Frame\n\n"
                "Source: 880-series-2026.pdf, page 22"
            ),
        ]
    }
    warnings = validate_response(state)
    assert warnings == []


def test_validate_response_empty_state():
    """Validator handles empty messages gracefully."""
    state = {"messages": []}
    warnings = validate_response(state)
    assert any("No messages" in w for w in warnings)


def test_validate_response_missing_messages_key():
    """Validator handles missing messages key gracefully."""
    state = {}
    warnings = validate_response(state)
    assert any("No messages" in w for w in warnings)


def test_validate_response_null_not_in_longer_words():
    """Validator does not flag 'null' inside longer words like 'nullable'."""
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(
                "The field is nullable and may not have a value assigned yet."
            ),
        ]
    }
    warnings = validate_response(state)
    # "nullable" should NOT trigger the null warning
    assert not any("null" in w.lower() for w in warnings)


# ---------- Source attribution validator tests ----------


def test_validate_response_no_source_attribution():
    """Validator warns when tool-using response lacks source attribution."""
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(
                "The Sundance Aspen uses a 2.5 HP jet pump (Wavemaster 8000)."
            ),
        ]
    }
    warnings = validate_response(state)
    assert any("source attribution" in w.lower() for w in warnings)


def test_validate_response_has_source_attribution():
    """Validator does not warn when source attribution is present."""
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(
                "The Sundance Aspen uses a **2.5 HP** jet pump.\n"
                "- Wavemaster 8000\n"
                "- 1-speed, 56 Frame\n\n"
                "Source: 880-series-2026.pdf, page 22"
            ),
        ]
    }
    warnings = validate_response(state)
    assert not any("source attribution" in w.lower() for w in warnings)


# ---------- Prose density / scannable format validator tests ----------


def test_validate_response_prose_density_warning():
    """Validator warns when long response is a single line (not scannable)."""
    long_single_line = (
        "The Sundance Aspen uses a 2.5 HP jet pump manufactured by Wavemaster "
        "which is a continuous-duty motor with 56 Frame design running at 11A "
        "maximum draw and it is compatible with the standard plumbing configuration. "
        "Source: 880-series-2026.pdf, page 22"
    )
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(long_single_line),
        ]
    }
    warnings = validate_response(state)
    assert any("scannable" in w.lower() for w in warnings)


def test_validate_response_scannable_format_no_warning():
    """Validator does not warn when long response has multiple lines."""
    multiline = (
        "The Sundance Aspen uses a **2.5 HP** jet pump:\n"
        "- Wavemaster 8000\n"
        "- 1-speed, 56 Frame\n"
        "- 11A max draw\n"
        "- Compatible with standard plumbing\n\n"
        "Source: 880-series-2026.pdf, page 22"
    )
    state = {
        "messages": [
            _make_tool_message(),
            _make_ai_message(multiline),
        ]
    }
    warnings = validate_response(state)
    assert not any("scannable" in w.lower() for w in warnings)


# ---------- Prompt content tests for response quality ----------


def test_specialist_prompt_contains_source_attribution_rule():
    """Specialist prompt must contain the source attribution rule."""
    assert "ALWAYS include source attribution" in SPECIALIST_PROMPT


def test_specialist_prompt_contains_find_cross_references():
    """Specialist prompt must instruct use of find_cross_references tool."""
    assert "find_cross_references" in SPECIALIST_PROMPT


def test_specialist_prompt_contains_response_format_template():
    """Specialist prompt must contain the structured response format template."""
    assert "Direct Answer" in SPECIALIST_PROMPT
    assert "Formatting Rules" in SPECIALIST_PROMPT


# ---------- Model creation tests ----------


def test_create_model_returns_gemini_instance(monkeypatch):
    """create_model returns a ChatGoogleGenerativeAI with gemini-2.5-flash."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")

    from langchain_google_genai import ChatGoogleGenerativeAI

    from backend.src.agent.config import create_model

    model = create_model()
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert "gemini-2.5-flash" in model.model


def test_create_model_temperature_zero(monkeypatch):
    """create_model sets temperature to 0 for deterministic outputs."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")

    from backend.src.agent.config import create_model

    model = create_model()
    assert model.temperature == 0


def test_create_model_max_output_tokens(monkeypatch):
    """create_model sets max_output_tokens to 2048 for response quality."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")

    from backend.src.agent.config import create_model

    model = create_model()
    assert model.max_output_tokens == 2048


# ---------- Graph structure tests ----------


def test_graph_imports_no_validator():
    """graph.py must NOT import validate_response (separation of concerns)."""
    import inspect

    from backend.src.agent import graph

    source = inspect.getsource(graph)
    assert "validate_response" not in source


def test_init_exports_validate_response():
    """__init__.py must re-export validate_response for API layer access."""
    from backend.src.agent import validate_response as vr

    assert callable(vr)


def test_init_exports_create_multi_agent():
    """__init__.py must export create_multi_agent as the primary factory."""
    from backend.src.agent import create_multi_agent

    assert callable(create_multi_agent)


def test_init_exports_create_dex_agent_compat():
    """__init__.py must export create_dex_agent for backward compatibility."""
    from backend.src.agent import create_dex_agent

    assert callable(create_dex_agent)
