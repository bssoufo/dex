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
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.src.api.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

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

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    _cors_origins = [os.getenv("ALLOWED_ORIGIN", "*")]
else:
    _cors_origins = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:4173",  # Vite preview server
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions -- return friendly message, log details."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again.",
            "type": type(exc).__name__,
        },
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


_HANDOFF_RE = re.compile(
    r"(?:Transferring (?:back )?to \w+\.?"
    r"|Successfully transferred (?:back )?to \w+\.?"
    r"|transfer_to_\w+)",
    re.IGNORECASE,
)


def _strip_handoff_text(text: str) -> str:
    """Remove LangGraph supervisor handoff artifacts from agent output."""
    return _HANDOFF_RE.sub("", text).strip()


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
        # Track the last agent that produced content (for deduplication)
        last_content = ""

        try:
            async for chunk in _agent.astream(
                {"messages": [{"role": "user", "content": request.question}]},
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in chunk.items():
                    # Skip supervisor routing messages — internal only
                    if node_name == "supervisor":
                        continue
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        accumulated_messages.append(msg)
                        # Skip tool messages (internal tool responses)
                        msg_type = getattr(msg, "type", None)
                        if msg_type == "tool":
                            continue
                        if not (hasattr(msg, "content") and msg.content):
                            continue
                        content = _normalize_content(msg.content)
                        # Strip handoff artifacts from content
                        content = _strip_handoff_text(content)
                        if not content.strip():
                            continue
                        if content != last_content:
                            last_content = content
                            yield _format_sse(
                                "token",
                                {"content": content, "node": node_name},
                            )
        except Exception as exc:
            logger.exception("Streaming error")
            yield _format_sse(
                "error",
                {"message": f"Agent error: {type(exc).__name__}"},
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


# ---------------------------------------------------------------------------
# Static file serving + SPA catch-all (MUST be after all API routes)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIR / "assets"),
        name="static-assets",
    )

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve React SPA -- any non-API path falls through to index.html."""
        file_path = FRONTEND_DIR / path
        if file_path.is_file() and ".." not in path:
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
