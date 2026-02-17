"""Dex multi-agent supervisor graph.

Creates a supervisor-orchestrated multi-agent graph with:
- Concierge: Clarifies ambiguous queries (has list_models tool only)
- Specialist: Answers spec questions (has all 3 MCP tools)
- Supervisor: Routes queries to the appropriate agent

Uses InMemorySaver checkpointer for multi-turn conversation via thread_id.
The Validator is NOT part of the graph -- it is a separate pure Python
function called by the API layer after agent.ainvoke() returns.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from backend.src.agent.config import create_mcp_client, create_model
from backend.src.agent.prompts import (
    CONCIERGE_PROMPT,
    SPECIALIST_PROMPT,
    SUPERVISOR_PROMPT,
)


async def create_multi_agent(mcp_tools=None):
    """Create the Dex multi-agent supervisor graph.

    Builds a supervisor graph with Concierge and Specialist agents.
    The Concierge has only the list_models tool for disambiguation.
    The Specialist has all MCP tools for data lookup.

    Args:
        mcp_tools: Optional list of MCP tools. If None, creates an MCP
            client and loads tools automatically.

    Returns:
        Tuple of (compiled_graph, mcp_client_or_none).
        mcp_client is returned only if this function created it (so the
        caller can manage its lifecycle). If mcp_tools were passed in,
        returns None for the client.
    """
    client = None
    if mcp_tools is None:
        client = create_mcp_client()
        mcp_tools = await client.get_tools()

    model = create_model()

    # Find the list_models tool for the Concierge
    list_models_tool = next(
        (t for t in mcp_tools if t.name == "list_models"),
        None,
    )
    # Concierge gets list_models only; fallback to all tools if not found
    concierge_tools = [list_models_tool] if list_models_tool else mcp_tools

    concierge = create_react_agent(
        model=model,
        tools=concierge_tools,
        name="concierge",
        prompt=CONCIERGE_PROMPT,
    )

    specialist = create_react_agent(
        model=model,
        tools=mcp_tools,
        name="specialist",
        prompt=SPECIALIST_PROMPT,
    )

    workflow = create_supervisor(
        agents=[concierge, specialist],
        model=model,
        prompt=SUPERVISOR_PROMPT,
        include_agent_name="inline",
        output_mode="last_message",
    )

    checkpointer = InMemorySaver()
    app = workflow.compile(
        checkpointer=checkpointer,
    )
    # Safety net: prevent runaway loops if supervisor fails to terminate.
    # Default LangGraph recursion_limit is 25; we set it explicitly.
    app.recursion_limit = 25

    return app, client


async def create_dex_agent():
    """Create the Dex agent (backward compatibility wrapper).

    .. deprecated::
        Use :func:`create_multi_agent` instead. This wrapper exists
        only for backward compatibility during migration.

    Returns:
        Tuple of (agent_graph, mcp_client).
    """
    return await create_multi_agent()
