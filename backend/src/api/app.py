"""FastAPI application for the Dex technical knowledge assistant.

Exposes a /query endpoint that accepts natural language questions and
returns answers via the multi-agent supervisor graph connected to MCP tools.
Also exposes a /query/stream SSE endpoint that streams the response
progressively via Server-Sent Events using LangGraph's astream().
The graph and MCP client are created once at startup via the lifespan
pattern and reused across all requests. Conversation state is maintained
via LangGraph's InMemorySaver checkpointer keyed by thread_id.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:4173",  # Vite preview server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _normalize_content(raw) -> str:
    """Normalize message content, handling Gemini's list-of-blocks format.

    Gemini may return content as a list of dicts with ``"text"`` keys or
    plain strings. This helper collapses them into a single string.
    """
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(raw)


def _format_sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Stream agent response via Server-Sent Events.

    Uses LangGraph's ``astream(stream_mode="updates")`` to yield node-level
    updates as SSE events. The event sequence is:

    1. ``metadata`` -- conversation_id (sent immediately)
    2. ``token``    -- content from each agent node that produces messages
    3. ``done``     -- signals streaming is complete
    4. ``validation`` -- validator warnings on the accumulated response
    """
    if _agent is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Generate or reuse conversation ID for checkpointer thread
    conv_id = request.conversation_id or str(uuid4())
    config = {"configurable": {"thread_id": conv_id}}

    async def event_generator():
        # Send conversation_id immediately
        yield _format_sse("metadata", {"conversation_id": conv_id})

        # Accumulate messages for the validator
        accumulated_messages: list = []

        async for chunk in _agent.astream(
            {"messages": [{"role": "user", "content": request.question}]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_output in chunk.items():
                messages = node_output.get("messages", [])
                for msg in messages:
                    accumulated_messages.append(msg)
                    if hasattr(msg, "content") and msg.content:
                        content = _normalize_content(msg.content)
                        if content.strip():
                            yield _format_sse(
                                "token",
                                {"content": content, "node": node_name},
                            )

        # Signal streaming complete
        yield _format_sse("done", {"status": "complete"})

        # Run deterministic validator on accumulated state
        from backend.src.agent.validator import validate_response

        warnings = validate_response({"messages": accumulated_messages})
        yield _format_sse("validation", {"warnings": warnings})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
