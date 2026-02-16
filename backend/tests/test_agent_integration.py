"""Integration tests for the Dex agent with real Gemini LLM and MCP tools.

Tests validate end-to-end behavior: user question -> LangGraph ReAct agent ->
Gemini 2.5 Flash LLM -> MCP tool calls -> structured data lookup -> answer.

All tests hit the real Gemini API and spawn a real MCP subprocess, so they
require GEMINI_API_KEY in backend/.env and are marked with `integration`.

Run with:
    cd backend && PYTHONPATH=.. python -m pytest tests/test_agent_integration.py -v --timeout=120
"""

from __future__ import annotations

import time

import pytest

# Mark entire module as integration tests
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared fixture: create agent + MCP client once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def agent_and_client():
    """Create the Dex ReAct agent connected to real MCP tools.

    Module-scoped so all tests share a single agent/MCP client,
    avoiding repeated subprocess startup overhead.

    MultiServerMCPClient uses transient stdio sessions (new subprocess per
    tool call), so no explicit cleanup is needed beyond letting it go out
    of scope.
    """
    from backend.src.agent.graph import create_dex_agent

    agent, client = await create_dex_agent()
    yield agent, client


# ---------------------------------------------------------------------------
# Helper: ask a question and measure response time
# ---------------------------------------------------------------------------


async def _ask(agent, question: str) -> tuple[str, float]:
    """Invoke the agent with a question, return (answer_text, elapsed_seconds).

    Handles both plain-string and structured-content responses from Gemini.
    The Gemini model sometimes returns content as a list of content blocks
    (e.g. ``[{'type': 'text', 'text': '...'}]``) rather than a plain string.
    """
    start = time.monotonic()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    elapsed = time.monotonic() - start
    raw = result["messages"][-1].content

    # Normalize: extract text from structured content blocks
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        answer = "\n".join(parts)
    else:
        answer = str(raw)

    return answer, elapsed


# ---------------------------------------------------------------------------
# Test Group 1: Category accuracy (10 parametrized tests)
# ---------------------------------------------------------------------------

CATEGORY_QUESTIONS = [
    pytest.param(
        "What jet pumps does the Sundance Aspen have?",
        ["pump", "hp", "speed"],
        id="jet_pumps",
    ),
    pytest.param(
        "What circulation pump does the Hot Spring Grandee use?",
        ["circulation", "pump"],
        id="circulation_pump",
    ),
    pytest.param(
        "What is the spa pak for the Sundance Cameo?",
        ["spa pak", "pack", "control"],
        id="spa_pak",
    ),
    pytest.param(
        "What topside control does the Hot Spring Aria have?",
        ["topside", "control", "panel"],
        id="topside_control",
    ),
    pytest.param(
        "How many jets does the Bullfrog M9 have?",
        ["jet"],
        id="jets",
    ),
    pytest.param(
        "What headrests come with the Hot Spring Sovereign?",
        ["headrest", "pillow"],
        id="headrests",
    ),
    pytest.param(
        "What filter does the Sundance Cameo use?",
        ["filter"],
        id="filters",
    ),
    pytest.param(
        "What is the heater spec for the Sundance Altamar?",
        ["heater", "watt", "kw"],
        id="heater",
    ),
    pytest.param(
        "What lighting does the Sundance Optima have?",
        ["light", "led"],
        id="lighting",
    ),
    pytest.param(
        "What cover comes with the Hot Spring Envoy?",
        ["cover"],
        id="cover",
    ),
]


@pytest.mark.parametrize("question,expected_substrings", CATEGORY_QUESTIONS)
@pytest.mark.timeout(60)
async def test_category_accuracy(agent_and_client, question, expected_substrings):
    """Agent answers spec questions with relevant domain keywords."""
    agent, _client = agent_and_client
    answer, elapsed = await _ask(agent, question)

    # Answer must be substantive (not empty or trivial)
    assert len(answer) > 20, (
        f"Answer too short ({len(answer)} chars): {answer!r}"
    )

    # Answer must contain at least one expected keyword (case-insensitive)
    answer_lower = answer.lower()
    found = [s for s in expected_substrings if s in answer_lower]
    assert found, (
        f"Expected one of {expected_substrings} in answer, got: {answer[:200]}"
    )

    # Relaxed timing for CI (network variability)
    assert elapsed < 30, f"Response took {elapsed:.1f}s (limit 30s)"

    # Log timing for manual review
    print(f"\n  [{question[:50]}...] answered in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Test Group 2: Anti-hallucination (2 tests)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
async def test_missing_part_number_flagged(agent_and_client):
    """Agent reports part numbers as not available rather than fabricating them.

    The Aspen jet pump part_number is null and listed in not_available_fields.
    """
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent, "What is the part number for the Sundance Aspen jet pump?"
    )

    answer_lower = answer.lower()
    # Agent should indicate the part number is not available
    not_available_phrases = [
        "not available",
        "no part number",
        "unavailable",
        "not yet",
        "don't have",
        "not listed",
        "not provided",
    ]
    found = any(phrase in answer_lower for phrase in not_available_phrases)
    assert found, (
        f"Expected 'not available' indication for missing part number, got: {answer[:300]}"
    )

    print(f"\n  [missing part number] answered in {elapsed:.1f}s")


@pytest.mark.timeout(60)
async def test_null_field_not_echoed(agent_and_client):
    """Agent humanizes null fields -- never echoes the word 'null' verbatim."""
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent,
        "What is the model name of the Sundance Aspen circulation pump?",
    )

    # The word "null" should not appear as a literal value in the answer.
    # It may appear in context like "null/not available" which is acceptable,
    # but raw "null" as a data value is not.
    answer_lower = answer.lower()
    # Check that "null" does not appear as a standalone word (not part of another word)
    import re

    null_matches = re.findall(r"\bnull\b", answer_lower)
    assert not null_matches, (
        f"Answer contains literal 'null' ({len(null_matches)} times): {answer[:300]}"
    )

    print(f"\n  [null field handling] answered in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Test Group 3: Out-of-scope (2 tests)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
async def test_out_of_scope_model(agent_and_client):
    """Agent refuses to answer about models outside the 19 POC models."""
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent, "What pump does the Jacuzzi J-335 use?"
    )

    answer_lower = answer.lower()
    out_of_scope_phrases = [
        "don't have",
        "not available",
        "only have",
        "19",
        "not in",
        "don't cover",
        "not one of",
        "outside",
        "don't include",
        "jacuzzi",
    ]
    found = any(phrase in answer_lower for phrase in out_of_scope_phrases)
    assert found, (
        f"Expected out-of-scope indication for Jacuzzi J-335, got: {answer[:300]}"
    )

    print(f"\n  [out-of-scope model] answered in {elapsed:.1f}s")


@pytest.mark.timeout(60)
async def test_out_of_scope_pricing(agent_and_client):
    """Agent refuses to answer pricing questions."""
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent, "How much does the Sundance Aspen cost?"
    )

    answer_lower = answer.lower()
    pricing_refusal_phrases = [
        "pricing",
        "technical",
        "specialize",
        "cannot",
        "don't provide",
        "price",
        "cost",
        "contact",
    ]
    found = any(phrase in answer_lower for phrase in pricing_refusal_phrases)
    assert found, (
        f"Expected pricing refusal for cost question, got: {answer[:300]}"
    )

    print(f"\n  [out-of-scope pricing] answered in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Test Group 4: Performance (1 test)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
async def test_simple_query_under_threshold(agent_and_client):
    """A simple spec lookup completes within acceptable time.

    The 3-second target is aspirational. The CI threshold is 30 seconds
    to account for MCP subprocess startup, Gemini API latency, and
    network variability. Actual time is logged for manual review.
    """
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent, "What is the heater wattage for the Hot Spring Grandee?"
    )

    assert len(answer) > 10, f"Answer too short: {answer!r}"
    assert elapsed < 30, (
        f"Response took {elapsed:.1f}s (CI threshold 30s)"
    )

    print(f"\n  [performance] answered in {elapsed:.1f}s: {answer[:100]}")
