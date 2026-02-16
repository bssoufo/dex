"""FastAPI application for the Dex technical knowledge assistant.

Exposes a /query endpoint that accepts natural language questions and
returns answers via the multi-agent supervisor graph connected to MCP tools.
The graph and MCP client are created once at startup via the lifespan
pattern and reused across all requests. Conversation state is maintained
via LangGraph's InMemorySaver checkpointer keyed by thread_id.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI

from backend.src.api.models import QueryRequest, QueryResponse

# Module-level state managed by lifespan
_agent = None
_mcp_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start multi-agent graph at boot, clean up at shutdown."""
    global _agent, _mcp_client

    from backend.src.agent.graph import create_multi_agent

    agent, client = await create_multi_agent()
    _agent = agent
    _mcp_client = client

    yield

    _agent = None
    _mcp_client = None


app = FastAPI(title="Dex API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "agent_ready": _agent is not None}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a natural language question about spa specifications.

    Invokes the Dex multi-agent supervisor graph which routes queries
    to the appropriate agent (Concierge or Specialist) via MCP tools.
    Runs the deterministic validator on every response and includes
    any warnings in the response payload.
    """
    if _agent is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Generate or reuse conversation ID for checkpointer thread
    conv_id = request.conversation_id or str(uuid4())
    config = {"configurable": {"thread_id": conv_id}}

    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": request.question}]},
        config=config,
    )

    # Extract the final AI message
    ai_message = result["messages"][-1]

    # Normalize content: Gemini may return a list of content blocks
    raw = ai_message.content
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        answer_text = "\n".join(parts)
    else:
        answer_text = str(raw)

    # Collect tool call info for debugging
    tool_call_info = None
    tool_messages = [
        m for m in result["messages"] if hasattr(m, "type") and m.type == "tool"
    ]
    if tool_messages:
        tool_call_info = [
            {"tool": m.name, "content": m.content[:200]} for m in tool_messages
        ]

    # Run deterministic validator on the agent result
    from backend.src.agent.validator import validate_response

    warnings = validate_response(result)
    validation_warnings = warnings if warnings else None

    return QueryResponse(
        answer=answer_text,
        conversation_id=conv_id,
        tool_calls=tool_call_info,
        validation_warnings=validation_warnings,
    )
