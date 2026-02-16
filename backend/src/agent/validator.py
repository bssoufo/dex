"""Deterministic response validation for the Dex agent.

Provides a pure Python validation function (no LLM call) that inspects
agent invocation results for quality issues. Designed to be called by
the API layer (app.py) after agent.ainvoke() returns, NOT as a LangGraph
graph node.

Checks performed:
1. At least one tool call message exists (fabrication guard)
2. Last AI message content is >20 chars (too-short guard)
3. Last AI message does not contain standalone "null" (leak guard)
4. Source attribution present when tools were used (traceability)
5. Response is scannable format, not prose-heavy (readability)
"""

from __future__ import annotations

import re


def validate_response(state: dict) -> list[str]:
    """Validate an agent invocation result for quality issues.

    Inspects the full result dict from ``agent.ainvoke()`` (which has
    a ``"messages"`` key) and returns a list of warning strings.
    An empty list means the response passed all checks.

    Checks performed:
    1. At least one tool call message exists -- if not, the response
       may be fabricated (no data lookup).
    2. Last AI message content is >20 chars -- if not, the response
       is too short to be useful.
    3. Last AI message does not contain the standalone word "null" --
       if found, raw null values may have leaked into the response.
    4. Source attribution present when tools were used -- responses
       citing tool data must include a "Source:" line.
    5. Response is scannable format -- long responses (>200 chars)
       must have at least 3 lines to avoid wall-of-text prose.

    Args:
        state: The full result dict from agent.ainvoke(), expected to
            have a "messages" key containing the message list.

    Returns:
        List of warning strings. Empty list means clean.
    """
    warnings: list[str] = []
    messages = state.get("messages", [])

    if not messages:
        warnings.append("No messages in state")
        return warnings

    # Check for tool call messages
    tool_messages = [
        m for m in messages if hasattr(m, "type") and m.type == "tool"
    ]
    if not tool_messages:
        warnings.append("No tool calls detected -- response may be fabricated")

    # Find the last AI message
    ai_messages = [
        m for m in messages if hasattr(m, "type") and m.type == "ai"
    ]
    if ai_messages:
        last_ai = ai_messages[-1]
        content = (
            last_ai.content
            if isinstance(last_ai.content, str)
            else str(last_ai.content)
        )

        # Check answer length
        if len(content) < 20:
            warnings.append("Response too short")

        # Check for literal "null" as standalone word
        if re.search(r"\bnull\b", content):
            warnings.append("Response contains literal 'null'")

        # Check for source attribution when tools were used
        if tool_messages and not re.search(r"[Ss]ources?:", content):
            warnings.append("No source attribution in response")

        # Check for scannable format (prose density)
        if len(content) > 200 and len(content.strip().split("\n")) < 3:
            warnings.append(
                "Response may not be scannable (few line breaks for length)"
            )

    return warnings
