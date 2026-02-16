"""FastAPI application for the Dex technical knowledge assistant.

Exposes a /query endpoint that accepts natural language questions and
returns answers via the LangGraph ReAct agent connected to MCP tools.
The MCP client and agent are created once at startup via the lifespan
pattern and reused across all requests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.src.api.models import QueryRequest, QueryResponse

# Module-level state managed by lifespan
_agent = None
_mcp_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MCP client and agent at boot, clean up at shutdown."""
    global _agent, _mcp_client

    from backend.src.agent.graph import _create_mcp_client, _create_model
    from backend.src.agent.prompts import SYSTEM_PROMPT
    from langgraph.prebuilt import create_react_agent

    _mcp_client = _create_mcp_client()
    tools = await _mcp_client.get_tools()
    model = _create_model()
    _agent = create_react_agent(model=model, tools=tools, prompt=SYSTEM_PROMPT)

    yield

    if _mcp_client:
        await _mcp_client.close()
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

    Invokes the Dex ReAct agent which uses MCP tools to look up
    data from the structured spec database.
    """
    if _agent is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": request.question}]}
    )

    # Extract the final AI message
    ai_message = result["messages"][-1]

    # Collect tool call info for debugging
    tool_call_info = None
    tool_messages = [
        m for m in result["messages"] if hasattr(m, "type") and m.type == "tool"
    ]
    if tool_messages:
        tool_call_info = [
            {"tool": m.name, "content": m.content[:200]} for m in tool_messages
        ]

    return QueryResponse(answer=ai_message.content, tool_calls=tool_call_info)
