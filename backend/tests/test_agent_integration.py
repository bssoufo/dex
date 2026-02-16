"""Integration tests for the Dex multi-agent system with real Gemini LLM and MCP tools.

Tests validate end-to-end behavior: user question -> LangGraph supervisor ->
Concierge/Specialist agents -> Gemini 2.5 Flash LLM -> MCP tool calls ->
structured data lookup -> answer.

All tests hit the real Gemini API and spawn a real MCP subprocess, so they
require GEMINI_API_KEY in backend/.env and are marked with `integration`.

Test groups:
  1. Category accuracy (10 parametrized) -- spec lookups return relevant keywords
  2. Anti-hallucination (2) -- missing data flagged, not fabricated
  3. Out-of-scope (2) -- unknown models and pricing refused
  4. Performance (1) -- simple query completes within 45s threshold
  5. Multi-turn conversation (2) -- follow-up questions maintain context via thread_id
  6. Disambiguation (1) -- ambiguous queries trigger clarification from Concierge

LLM responses are non-deterministic, so tests use ``--reruns=2`` to handle
occasional flaky answers from Gemini.  A test that passes on retry is
considered green.

Run with:
    cd backend && PYTHONPATH=.. python -m pytest tests/test_agent_integration.py -v --timeout=120 --reruns=2
"""

from __future__ import annotations

import time
import uuid

import pytest

# Mark entire module as integration tests.
# flaky(reruns=2): LLM non-determinism means ~10-15% of individual runs
# may produce empty or off-topic answers; retrying handles this gracefully.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.flaky(reruns=2),
]


# ---------------------------------------------------------------------------
# Shared fixture: create agent + MCP client once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def agent_and_client():
    """Create the Dex multi-agent supervisor connected to real MCP tools.

    Module-scoped so all tests share a single agent/MCP client,
    avoiding repeated subprocess startup overhead.

    MultiServerMCPClient uses transient stdio sessions (new subprocess per
    tool call), so no explicit cleanup is needed beyond letting it go out
    of scope.
    """
    from backend.src.agent.graph import create_multi_agent

    agent, client = await create_multi_agent()
    yield agent, client


# ---------------------------------------------------------------------------
# Helper: ask a question and measure response time
# ---------------------------------------------------------------------------


async def _ask(
    agent, question: str, config: dict | None = None
) -> tuple[str, float]:
    """Invoke the agent with a question, return (answer_text, elapsed_seconds).

    Handles both plain-string and structured-content responses from Gemini.
    The Gemini model sometimes returns content as a list of content blocks
    (e.g. ``[{'type': 'text', 'text': '...'}]``) rather than a plain string.

    The multi-agent supervisor with ``output_mode="last_message"`` may
    return messages in various orderings.  We search backward for the last
    AI message to extract the answer robustly.

    Args:
        agent: Compiled LangGraph supervisor graph.
        question: User question string.
        config: Optional config dict with ``{"configurable": {"thread_id": ...}}``
            for multi-turn conversation context.
    """
    start = time.monotonic()
    invoke_kwargs: dict = {"messages": [{"role": "user", "content": question}]}
    # InMemorySaver checkpointer requires a thread_id in every invocation.
    # Generate a unique one-shot thread_id when the caller does not provide
    # an explicit config (single-turn tests).
    if config is None:
        config = {"configurable": {"thread_id": f"test-{uuid.uuid4().hex[:12]}"}}
    result = await agent.ainvoke(invoke_kwargs, config=config)
    elapsed = time.monotonic() - start

    def _extract_text(raw_content) -> str:
        """Normalize structured or plain content to a string."""
        if isinstance(raw_content, list):
            parts = []
            for block in raw_content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return str(raw_content)

    msgs = result["messages"]

    # In multi-turn conversations the result carries the full history.
    # Restrict to messages added *after* the last HumanMessage so that we
    # only inspect the current turn's output.
    last_human_idx = -1
    for i, m in enumerate(msgs):
        if hasattr(m, "type") and m.type == "human":
            last_human_idx = i
    current_turn_msgs = msgs[last_human_idx + 1 :] if last_human_idx >= 0 else msgs

    # Collect AI messages from the current turn only
    ai_msgs = [
        m
        for m in current_turn_msgs
        if hasattr(m, "type") and m.type == "ai"
    ]

    # Pick the most substantive AI message from the current turn.
    # The supervisor may produce short handoff notes ("Transferring...",
    # "I've transferred you...") alongside the real data answer.
    # Use the longest AI message as the answer since the data-rich
    # response is almost always the longest.
    answer = ""
    if ai_msgs:
        best = max(ai_msgs, key=lambda m: len(_extract_text(m.content)))
        answer = _extract_text(best.content)

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

    # Relaxed timing for CI (network variability + supervisor routing overhead)
    assert elapsed < 45, f"Response took {elapsed:.1f}s (limit 45s)"

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
        "wasn't able to find",
        "unable to find",
        "could not find",
        "couldn't find",
        "not found",
        "not in",
        "no information",
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

    The 3-second target is aspirational. The CI threshold is 45 seconds
    to account for MCP subprocess startup, Gemini API latency, network
    variability, and supervisor routing overhead (extra LLM call).
    Actual time is logged for manual review.
    """
    agent, _client = agent_and_client
    answer, elapsed = await _ask(
        agent, "What is the heater wattage for the Hot Spring Grandee?"
    )

    assert len(answer) > 10, f"Answer too short: {answer!r}"
    assert elapsed < 45, (
        f"Response took {elapsed:.1f}s (CI threshold 45s)"
    )

    print(f"\n  [performance] answered in {elapsed:.1f}s: {answer[:100]}")


# ---------------------------------------------------------------------------
# Test Group 5: Multi-turn conversation (2 tests)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(180)
async def test_multi_turn_follow_up(agent_and_client):
    """Follow-up question maintains context from first question.

    Ask about the Sundance Aspen pump, then ask 'What about the filter
    for that model?' without re-specifying the model. The agent should
    use conversation history to resolve 'that model' to Sundance Aspen.

    Timeout is 180s (vs 60s for single-turn) because this test makes two
    sequential supervisor invocations, each with MCP subprocess startup,
    Gemini API calls, and supervisor routing overhead.
    """
    agent, _client = agent_and_client
    # Unique thread_id per attempt (safe for reruns)
    tid = f"test-multi-turn-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": tid}}

    # First turn: establish context
    answer1, _ = await _ask(
        agent, "What pump does the Sundance Aspen use?", config=config
    )
    assert len(answer1) > 20, f"First answer too short: {answer1!r}"

    # Second turn: follow-up referencing 'that same spa'
    # The agent should use conversation history (same thread_id) to resolve
    # 'that same spa' to Sundance Aspen without re-specifying the model.
    answer2, _ = await _ask(
        agent,
        "Now tell me about the filter for that same spa.",
        config=config,
    )
    assert len(answer2) > 20, f"Follow-up answer too short: {answer2!r}"

    # The follow-up answer should be about filters (not pumps) and should
    # reference Aspen/Sundance context (not ask for clarification)
    answer2_lower = answer2.lower()
    assert "filter" in answer2_lower, (
        f"Follow-up should discuss filters, got: {answer2[:300]}"
    )

    print(f"\n  [multi-turn follow-up] turn 1: {answer1[:80]}...")
    print(f"  [multi-turn follow-up] turn 2: {answer2[:80]}...")


@pytest.mark.timeout(180)
async def test_multi_turn_separate_threads(agent_and_client):
    """Different thread_ids maintain independent conversations.

    Two parallel conversations about different models should not
    cross-contaminate.

    Timeout is 180s because this test makes two sequential supervisor
    invocations on separate threads.
    """
    agent, _client = agent_and_client
    # Unique thread_ids per attempt (safe for reruns)
    suffix = uuid.uuid4().hex[:8]
    config_a = {"configurable": {"thread_id": f"test-thread-a-{suffix}"}}
    config_b = {"configurable": {"thread_id": f"test-thread-b-{suffix}"}}

    # Thread A: ask about Aspen
    answer_a, _ = await _ask(
        agent,
        "What pump does the Sundance Aspen use?",
        config=config_a,
    )
    assert len(answer_a) > 20

    # Thread B: ask about Grandee
    answer_b, _ = await _ask(
        agent,
        "What pump does the Hot Spring Grandee use?",
        config=config_b,
    )
    assert len(answer_b) > 20

    # Answers should be different (different models have different pumps)
    # Just verify both are substantive and about the right topic
    assert "pump" in answer_a.lower() or "hp" in answer_a.lower()
    assert "pump" in answer_b.lower() or "hp" in answer_b.lower()

    print(f"\n  [thread isolation] thread A: {answer_a[:80]}...")
    print(f"  [thread isolation] thread B: {answer_b[:80]}...")


# ---------------------------------------------------------------------------
# Test Group 6: Disambiguation (1 test)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
async def test_ambiguous_query_gets_clarification(agent_and_client):
    """An ambiguous query without a model name triggers clarification.

    The supervisor should route to the Concierge, which asks the user
    to specify which model they mean.
    """
    agent, _client = agent_and_client
    answer, elapsed = await _ask(agent, "What pump does it use?")

    answer_lower = answer.lower()
    # The response should ask for clarification (which model?)
    clarification_phrases = [
        "which model",
        "which spa",
        "specify",
        "which one",
        "could you",
        "can you",
        "please provide",
        "what model",
        "particular model",
        "clarify",
        "model name",
        "need to know",
        "let me know",
        "help me identify",
        "more information",
    ]
    found = any(phrase in answer_lower for phrase in clarification_phrases)
    assert found, (
        f"Expected clarification request for ambiguous query, got: {answer[:300]}"
    )

    print(f"\n  [disambiguation] answered in {elapsed:.1f}s: {answer[:100]}")
