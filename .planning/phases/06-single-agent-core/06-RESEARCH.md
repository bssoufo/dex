# Phase 6: Single Agent Core - Research

**Researched:** 2026-02-16
**Domain:** LangGraph ReAct agent with MCP tool calling, natural language query parsing, structured data retrieval
**Confidence:** HIGH

## Summary

Phase 6 builds a single monolithic LangGraph agent ("Dex") that takes natural language questions about spa specifications and answers them by calling the existing MCP tools (get_spec_category, get_model_overview, list_models). The agent must prove core accuracy across all 19 models and 10 spec categories before the Phase 7 multi-agent split.

The standard approach is a LangGraph `create_react_agent` (prebuilt ReAct graph) connected to the FastMCP server via `langchain-mcp-adapters`. The agent receives a system prompt that defines its role, available data scope, and anti-hallucination rules, then uses tool calling to look up data and format human-readable responses. For the LLM, the project already has a Gemini API key (`GEMINI_API_KEY` in `backend/.env`), and Gemini 2.5 Flash provides the speed needed for the 3-second target (sub-500ms time to first token, ~250 tokens/second output). If higher quality tool calling is desired, Claude Haiku 4.5 via `langchain-anthropic` is an alternative that runs ~4-5x faster than Sonnet.

The critical design constraint: the agent must NEVER fabricate data. The system prompt must instruct the agent to ONLY answer from MCP tool results, explicitly say "not available" when data is missing, and refuse out-of-scope questions. Testing requires a ground-truth test matrix of representative questions with expected answers verified against the JSON data files.

**Primary recommendation:** Use LangGraph `create_react_agent` with `langchain-google-genai` (ChatGoogleGenerativeAI, model `gemini-2.5-flash`) and `langchain-mcp-adapters` (MultiServerMCPClient, stdio transport). Expose via a thin FastAPI endpoint. Test with both deterministic unit tests (GenericFakeChatModel) and an integration test matrix against the real LLM.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.0.8 | Agent orchestration framework | Official LangChain agent framework; prebuilt ReAct agent; production-stable |
| langchain-mcp-adapters | 0.2.1 | Bridge MCP tools to LangChain | Official LangChain package; converts FastMCP tools to LangGraph-compatible tools |
| langchain-google-genai | 4.2.0 | Gemini LLM provider | Project already uses Gemini API key; Flash model is fast+cheap for tool calling |
| fastapi | >=0.115 | HTTP API framework | Already in project stack per MEMORY.md; exposes agent as REST endpoint |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain-core | (transitive) | Base types (messages, tools) | Installed automatically with langgraph |
| python-dotenv | >=1.2.1 | Environment variables | Already installed; loads GEMINI_API_KEY from .env |
| uvicorn | >=0.34 | ASGI server | Run FastAPI in development; Phase 10 will use production server |
| langchain-anthropic | 1.3.3 | Claude LLM provider (alternative) | If Gemini tool calling proves unreliable; Claude Haiku 4.5 is fast alternative |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Gemini 2.5 Flash | Claude Haiku 4.5 | Haiku is 4-5x faster than Sonnet, strong tool calling; but requires separate API key and adds Anthropic dependency cost |
| Gemini 2.5 Flash | Gemini 2.5 Flash-Lite | Even faster/cheaper but newer and less tested for tool calling accuracy |
| create_react_agent | Custom StateGraph | More control but more boilerplate; prebuilt agent handles ReAct loop, tool routing, error handling out of the box |
| langchain-mcp-adapters (stdio) | Direct tool functions | Could call MCP tool functions directly without MCP protocol overhead; but loses the MCP protocol boundary and makes Phase 10 deployment harder |
| FastAPI endpoint | CLI-only | Simpler for Phase 6 testing; but Phase 9 (Frontend) needs an HTTP API, so build it now |

### Installation

```bash
# Core agent dependencies
pip install langgraph langchain-mcp-adapters "langchain-google-genai>=4.2"

# API server
pip install fastapi uvicorn

# Alternative LLM (if needed)
pip install langchain-anthropic
```

Or in pyproject.toml:
```toml
dependencies = [
    # ... existing deps ...
    "langgraph>=1.0.8",
    "langchain-mcp-adapters>=0.2.1",
    "langchain-google-genai>=4.2,<5",
    "fastapi>=0.115",
    "uvicorn>=0.34",
]
```

## Architecture Patterns

### Recommended Project Structure

```
backend/src/
  agent/                     # NEW -- Agent package
    __init__.py              # Exports create_dex_agent()
    graph.py                 # LangGraph agent definition (create_react_agent)
    prompts.py               # System prompt for Dex
    mcp_client.py            # MCP client setup (MultiServerMCPClient)
  api/                       # NEW -- FastAPI application
    __init__.py
    app.py                   # FastAPI app with /query endpoint
    models.py                # Request/response Pydantic models
  mcp/                       # EXISTING -- MCP server
    server.py
    data_store.py
    enums.py
  schema/                    # EXISTING -- Data models
  data/                      # EXISTING -- 19 JSON files
backend/tests/
  test_mcp_tools.py          # EXISTING -- 219 MCP tests
  test_agent.py              # NEW -- Agent unit tests (mocked LLM)
  test_agent_integration.py  # NEW -- Agent integration tests (real LLM)
  test_api.py                # NEW -- FastAPI endpoint tests
```

### Pattern 1: LangGraph ReAct Agent with MCP Tools

**What:** Use LangGraph's prebuilt `create_react_agent` with MCP tools loaded via `langchain-mcp-adapters`. The agent receives a user question, reasons about which MCP tool to call, calls it, reads the result, and formulates a natural language answer.

**When to use:** Single agent that needs to call structured tools. This is the exact use case.

**Example:**

```python
# backend/src/agent/graph.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from backend.src.agent.prompts import SYSTEM_PROMPT


def get_mcp_client() -> MultiServerMCPClient:
    """Create MCP client configured to connect to the Dex data server."""
    return MultiServerMCPClient({
        "dex_data": {
            "command": "python",
            "args": ["-m", "backend.src.mcp"],
            "transport": "stdio",
        }
    })


async def create_dex_agent():
    """Create and return the Dex agent with MCP tools."""
    client = get_mcp_client()
    tools = await client.get_tools()

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,  # Deterministic for spec lookups
    )

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent, client
```

### Pattern 2: Anti-Hallucination System Prompt

**What:** A carefully crafted system prompt that constrains the agent to ONLY use MCP tool results, never fabricate data, and explicitly flag missing information.

**When to use:** Always. This is the core accuracy guarantee.

**Example:**

```python
# backend/src/agent/prompts.py
SYSTEM_PROMPT = """You are Dex, a technical knowledge assistant for Spaparts.
You answer questions about hot tub and spa specifications using ONLY the data
available through your tools. You serve 19 spa models across 3 manufacturers:
Sundance (880 Series), Hot Spring (Highlife Collection), and Bullfrog (M Series).

## CRITICAL RULES

1. **NEVER fabricate data.** If a tool returns null or "not available" for a
   field, say "This information is not available in our records." Do NOT guess
   or infer values.

2. **ALWAYS use tools to answer.** Never answer from memory or general
   knowledge. Every spec value in your response must come from a tool call.

3. **Use list_models first** if you are unsure which manufacturer a model
   belongs to. Models have specific manufacturers -- do not guess.

4. **Use get_model_overview** to check what data categories are available
   for a model before querying specific categories.

5. **Use get_spec_category** to retrieve detailed specs for a specific
   category (jet_pumps, circulation_pump, spa_pak, topside_control, jets,
   headrests, filters, heater, lighting, cover).

## OUT-OF-SCOPE HANDLING

- If asked about a model not in the 19 POC models, say: "I only have data
  for [list the 19 models]. I don't have information about [requested model]."
- If asked about pricing, availability, or non-technical topics, say:
  "I specialize in technical specifications only. For pricing or availability,
  please contact Spaparts directly."
- If asked a general spa question not about a specific model, clarify which
  model the user is asking about.

## RESPONSE FORMAT

- Lead with the direct answer (part number, spec value)
- Include relevant details (HP, wattage, compatibility notes)
- Flag any not-available fields explicitly
- Be concise and professional -- no filler or chatty language
"""
```

### Pattern 3: FastAPI Query Endpoint

**What:** A thin FastAPI endpoint that accepts a natural language query and returns the agent's response.

**When to use:** Phase 6 needs an invocable endpoint for testing. Phase 9 (Frontend) will connect to this.

**Example:**

```python
# backend/src/api/app.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Dex API", version="0.1.0")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    tool_calls: list[dict] | None = None


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Send a natural language question to the Dex agent."""
    from backend.src.agent.graph import create_dex_agent

    agent, client = await create_dex_agent()
    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.question}]}
        )
        # Extract the final AI message
        messages = result["messages"]
        ai_message = messages[-1]
        return QueryResponse(answer=ai_message.content)
    finally:
        # Clean up MCP client connections
        await client.close()
```

### Pattern 4: Test Matrix with Ground Truth

**What:** A matrix of representative questions with expected answers verified against the actual JSON data. Used for both automated testing and manual validation.

**When to use:** Success Criterion 5 requires verification across all 10 spec categories.

**Example:**

```python
# backend/tests/test_agent_integration.py
import pytest

TEST_MATRIX = [
    # (question, expected_contains, category)
    (
        "What pump does the Sundance Aspen use?",
        ["jet_pumps", "position"],  # Must mention pump data
        "jet_pumps",
    ),
    (
        "What is the heater wattage for the Hot Spring Grandee?",
        ["heater", "watt"],
        "heater",
    ),
    (
        "How many jets does the Bullfrog M9 have?",
        ["jet"],
        "jets",
    ),
    (
        "What filter does the Sundance Cameo use?",
        ["filter"],
        "filters",
    ),
    # Out-of-scope tests
    (
        "What pump does the Jacuzzi J-335 use?",
        ["don't have", "not", "only"],  # Must indicate out of scope
        "out_of_scope",
    ),
    (
        "How much does the Sundance Aspen cost?",
        ["pricing", "specialize", "technical"],  # Must indicate not pricing
        "out_of_scope",
    ),
]
```

### Anti-Patterns to Avoid

- **Calling MCP tools at import time:** MCP client setup is async and involves subprocess spawning. Never do this at module load. Use lazy initialization or factory functions.
- **Sharing a single MCP client across requests:** MultiServerMCPClient spawns subprocesses. Each request should either use a shared persistent client (with proper lifecycle management) or create fresh connections. For Phase 6, a persistent client managed by FastAPI lifespan is cleaner.
- **Temperature > 0 for spec lookups:** The agent should be deterministic. Set temperature=0 so tool selection and response formatting are consistent.
- **Embedding data knowledge in the system prompt:** Do NOT put actual spec values in the prompt. The prompt defines BEHAVIOR (how to use tools, how to format responses). The DATA comes exclusively from MCP tool calls.
- **Omitting the MCP client cleanup:** The MultiServerMCPClient spawns subprocesses. Always close/cleanup in a finally block or use async context managers.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ReAct agent loop | Custom while-loop with tool dispatch | `create_react_agent` from langgraph.prebuilt | Handles tool calling, message routing, error recovery, loop termination |
| MCP-to-LangChain bridge | Custom tool wrappers around MCP calls | `langchain-mcp-adapters` MultiServerMCPClient | Auto-converts MCP tool schemas to LangChain tool definitions with validation |
| Natural language to tool call | Custom intent parsing / regex | LLM tool calling (native function calling) | LLM natively maps "What pump does Aspen use?" to get_spec_category(manufacturer="sundance", model_name="Aspen", category="jet_pumps") |
| Query routing logic | if/elif chain for query types | LLM reasoning in ReAct loop | The LLM decides which tool to call based on the question; no manual routing needed |
| Response formatting | Template engine for responses | LLM natural language generation | The LLM reads tool results and formats a human-readable answer; templates would be rigid |
| Model name resolution | Fuzzy matching / Levenshtein | MCP Literal enum constraints | The LLM sees the valid model list in the tool schema; invalid names are rejected at protocol level |

**Key insight:** The entire Phase 6 agent is essentially: system prompt + LLM + MCP tools. The LLM handles NL parsing, tool selection, and response generation. The MCP tools handle data retrieval. There is very little custom code needed -- the value is in the system prompt design and the test matrix.

## Common Pitfalls

### Pitfall 1: MCP Client Lifecycle Mismanagement

**What goes wrong:** MultiServerMCPClient starts subprocesses for stdio transport. If not properly closed, orphaned Python processes accumulate. If shared naively across async requests, race conditions occur.
**Why it happens:** Async lifecycle management is tricky. The client is stateful (subprocess connections).
**How to avoid:** Use FastAPI lifespan events to create the client once at startup and close it at shutdown. The client's `get_tools()` call should happen once, not per request. Store the agent graph as a module-level singleton initialized during startup.
**Warning signs:** Zombie Python processes in task manager; "connection refused" errors after several requests.

### Pitfall 2: Agent Fabricates Data Despite System Prompt

**What goes wrong:** The LLM answers a question from its training data instead of calling a tool. Example: user asks "What's the voltage of the Sundance Aspen?" and the LLM responds "240V" from general knowledge without calling get_spec_category.
**Why it happens:** LLMs are trained to be helpful and may answer directly if they "know" the answer. The ReAct loop only calls tools if the LLM generates tool_calls in its response.
**How to avoid:** (1) The system prompt must be explicit: "ALWAYS use tools, NEVER answer from memory." (2) Set temperature=0 for consistency. (3) Test with questions where the correct answer is counter-intuitive (e.g., a field that is null in the data) to verify the agent calls the tool rather than guessing. (4) Consider adding a response validation step that checks every claim against tool results.
**Warning signs:** Agent responds instantly without any tool calls; agent gives correct-sounding answers that don't match the JSON data.

### Pitfall 3: Gemini Tool Calling Schema Compatibility

**What goes wrong:** Gemini may not handle all MCP tool schemas perfectly. Known issues include: Literal types with many values, optional parameters, and complex nested schemas.
**Why it happens:** Different LLM providers have different tool calling implementations. Gemini's function calling uses a different schema format than OpenAI/Anthropic.
**How to avoid:** (1) Test tool calling with the actual MCP tool schemas early. (2) The MCP tools have simple parameters (Manufacturer enum, ModelName Literal, SpecCategory enum) which should work well. (3) If Gemini struggles, ChatAnthropic with Haiku 4.5 is the fallback. (4) langchain-mcp-adapters handles schema conversion, but verify the converted schemas are correct.
**Warning signs:** Agent never calls tools successfully; tool call arguments are malformed; "invalid argument" errors from MCP server.

### Pitfall 4: 3-Second Response Target Exceeded

**What goes wrong:** A single query takes >3 seconds due to: (1) MCP server subprocess startup, (2) LLM API latency, (3) Multiple tool calls in sequence.
**Why it happens:** The ReAct loop may make 2-3 tool calls per query (e.g., list_models to find manufacturer, then get_spec_category for the data). Each tool call adds MCP protocol overhead. LLM API calls add 0.5-2s each.
**How to avoid:** (1) Keep MCP server running persistently (don't start/stop per request). (2) Use Gemini 2.5 Flash which has ~400ms TTFT and 258 tok/s. (3) Design the system prompt so the agent makes minimal tool calls (guide it to call get_spec_category directly when manufacturer is known). (4) Measure end-to-end latency in integration tests and set a hard threshold.
**Warning signs:** Latency tests consistently exceed 3s; agent makes unnecessary tool calls (e.g., always calling list_models first).

### Pitfall 5: Not-Available Fields Shown as "null"

**What goes wrong:** Agent receives `{"data": {"part_number": null}}` from MCP tool and says "The part number is null" instead of "The part number is not available."
**Why it happens:** The LLM reads the raw JSON and may echo "null" literally. The MCP response includes `not_available_fields` but the LLM might not check that list.
**How to avoid:** (1) System prompt must explicitly instruct: "When a field value is null, check the not_available_fields list. If the field is listed there, say 'not available from manufacturer documentation.' If not listed, say 'data not yet extracted.'" (2) Consider post-processing the MCP tool output before it reaches the LLM -- replace null values with human-readable strings.
**Warning signs:** Responses contain the word "null" or "None"; missing data is not explained.

### Pitfall 6: Manufacturer-Model Mismatch

**What goes wrong:** User asks about "the Aspen" and the agent calls `get_spec_category(manufacturer="bullfrog", model_name="Aspen")`, getting a "not found" error.
**Why it happens:** The LLM doesn't know which manufacturer maps to which model. The MCP tool requires both manufacturer and model_name.
**How to avoid:** (1) Include a manufacturer-model mapping hint in the system prompt. (2) Instruct the agent to call `list_models` if unsure about the manufacturer. (3) Alternatively, create a lookup table in the system prompt: "Sundance: Altamar, Aspen, Cameo, Capris, Marin, Optima, Vistamar. Hot Spring: Aria, Envoy, Grandee, Jetsetter, Jetsetter LX, Prodigy, Sovereign, Vanguard. Bullfrog: M6, M7, M8, M9."
**Warning signs:** Agent gets "not found" responses from tools; makes retry calls with different manufacturers.

## Code Examples

### Example 1: Complete Agent Module

```python
# backend/src/agent/graph.py
"""Dex single agent -- LangGraph ReAct agent with MCP tools."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from backend.src.agent.prompts import SYSTEM_PROMPT

load_dotenv(dotenv_path="backend/.env")


def _create_model() -> ChatGoogleGenerativeAI:
    """Create the Gemini Flash model for tool-calling."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,
        max_output_tokens=1024,
    )


def _create_mcp_client() -> MultiServerMCPClient:
    """Create MCP client with stdio transport to Dex data server."""
    return MultiServerMCPClient({
        "dex_data": {
            "command": "python",
            "args": ["-m", "backend.src.mcp"],
            "transport": "stdio",
        }
    })


async def create_dex_agent():
    """Create the Dex ReAct agent connected to MCP tools.

    Returns:
        Tuple of (agent_graph, mcp_client). Caller must close mcp_client.
    """
    client = _create_mcp_client()
    tools = await client.get_tools()
    model = _create_model()

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent, client
```

### Example 2: FastAPI Application with Lifespan

```python
# backend/src/api/app.py
"""FastAPI application exposing the Dex agent as a REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from backend.src.agent.graph import _create_model, _create_mcp_client
from backend.src.agent.prompts import SYSTEM_PROMPT


# Module-level references set during lifespan
_agent = None
_mcp_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MCP client and agent lifecycle."""
    global _agent, _mcp_client
    from langgraph.prebuilt import create_react_agent

    _mcp_client = _create_mcp_client()
    tools = await _mcp_client.get_tools()
    model = _create_model()
    _agent = create_react_agent(model=model, tools=tools, prompt=SYSTEM_PROMPT)
    yield
    # Cleanup
    if _mcp_client:
        await _mcp_client.close()


app = FastAPI(title="Dex API", version="0.1.0", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Send a natural language question to the Dex agent."""
    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": request.question}]}
    )
    ai_message = result["messages"][-1]
    return QueryResponse(answer=ai_message.content)
```

### Example 3: Unit Test with Mocked LLM

```python
# backend/tests/test_agent.py
"""Unit tests for the Dex agent with mocked LLM responses."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall


def test_system_prompt_contains_anti_hallucination_rules():
    """System prompt must contain critical anti-hallucination instructions."""
    from backend.src.agent.prompts import SYSTEM_PROMPT

    assert "NEVER fabricate" in SYSTEM_PROMPT
    assert "ALWAYS use tools" in SYSTEM_PROMPT
    assert "not available" in SYSTEM_PROMPT.lower()


def test_system_prompt_lists_all_manufacturers():
    """System prompt must mention all 3 manufacturers."""
    from backend.src.agent.prompts import SYSTEM_PROMPT

    assert "Sundance" in SYSTEM_PROMPT
    assert "Hot Spring" in SYSTEM_PROMPT
    assert "Bullfrog" in SYSTEM_PROMPT


def test_system_prompt_contains_out_of_scope_handling():
    """System prompt must instruct agent on out-of-scope queries."""
    from backend.src.agent.prompts import SYSTEM_PROMPT

    assert "pricing" in SYSTEM_PROMPT.lower()
    assert "out of scope" in SYSTEM_PROMPT.lower() or "out-of-scope" in SYSTEM_PROMPT.lower()
```

### Example 4: Integration Test Matrix

```python
# backend/tests/test_agent_integration.py
"""Integration tests that run the full agent with real LLM and MCP tools.

These tests call the actual Gemini API and MCP server.
Mark with @pytest.mark.integration so they can be skipped in CI.
"""

from __future__ import annotations

import time

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def agent_and_client():
    """Create agent once for all tests in the module."""
    from backend.src.agent.graph import create_dex_agent

    agent, client = await create_dex_agent()
    yield agent, client
    await client.close()


async def _ask(agent, question: str) -> tuple[str, float]:
    """Ask the agent a question, return (answer, elapsed_seconds)."""
    start = time.monotonic()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    elapsed = time.monotonic() - start
    return result["messages"][-1].content, elapsed


# --- Accuracy tests across all 10 categories ---

CATEGORY_QUESTIONS = [
    ("What jet pumps does the Sundance Aspen have?", "jet_pumps"),
    ("What circulation pump does the Hot Spring Grandee use?", "circulation_pump"),
    ("What is the spa pak for the Sundance Cameo?", "spa_pak"),
    ("What topside control does the Hot Spring Aria have?", "topside_control"),
    ("How many jets does the Bullfrog M9 have?", "jets"),
    ("What headrests come with the Hot Spring Sovereign?", "headrests"),
    ("What filter does the Sundance Marin use?", "filters"),
    ("What is the heater spec for the Bullfrog M8?", "heater"),
    ("What lighting does the Sundance Optima have?", "lighting"),
    ("What cover comes with the Hot Spring Envoy?", "cover"),
]


@pytest.mark.parametrize(
    ("question", "category"),
    CATEGORY_QUESTIONS,
    ids=[cat for _, cat in CATEGORY_QUESTIONS],
)
async def test_category_accuracy(agent_and_client, question, category):
    """Agent answers questions for all 10 spec categories."""
    agent, _ = agent_and_client
    answer, elapsed = await _ask(agent, question)

    # Must have non-empty answer
    assert len(answer) > 20, f"Answer too short: {answer}"
    # Must respond within 3 seconds
    assert elapsed < 3.0, f"Response took {elapsed:.1f}s, exceeds 3s target"


# --- Anti-hallucination tests ---

async def test_missing_data_flagged(agent_and_client):
    """When data is not available, agent must say so explicitly."""
    agent, _ = agent_and_client
    # Most part_numbers are null -- agent should acknowledge this
    answer, _ = await _ask(
        agent, "What is the part number for the Sundance Aspen jet pump?"
    )
    assert any(
        phrase in answer.lower()
        for phrase in ["not available", "no part number", "unavailable"]
    ), f"Agent did not flag missing data: {answer}"


# --- Out-of-scope tests ---

async def test_out_of_scope_model(agent_and_client):
    """Agent must refuse questions about models not in the 19 POC set."""
    agent, _ = agent_and_client
    answer, _ = await _ask(
        agent, "What pump does the Jacuzzi J-335 use?"
    )
    assert any(
        phrase in answer.lower()
        for phrase in ["don't have", "not available", "only have", "not in"]
    ), f"Agent did not handle out-of-scope model: {answer}"


async def test_out_of_scope_pricing(agent_and_client):
    """Agent must refuse pricing questions."""
    agent, _ = agent_and_client
    answer, _ = await _ask(
        agent, "How much does the Sundance Aspen cost?"
    )
    assert any(
        phrase in answer.lower()
        for phrase in ["pricing", "technical", "specialize", "cannot"]
    ), f"Agent did not handle pricing question: {answer}"


# --- Performance tests ---

async def test_response_under_3_seconds(agent_and_client):
    """All queries must complete in under 3 seconds."""
    agent, _ = agent_and_client
    answer, elapsed = await _ask(
        agent, "What is the heater wattage for the Hot Spring Grandee?"
    )
    assert elapsed < 3.0, f"Response took {elapsed:.1f}s"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain AgentExecutor | LangGraph create_react_agent | 2025 | LangGraph is now the official agent framework; AgentExecutor is legacy |
| Custom MCP tool wrappers | langchain-mcp-adapters 0.2.x | Late 2025 | Official bridge package; auto-converts MCP tools to LangChain format |
| OpenAI function calling only | Multi-provider tool calling | 2025-2026 | Gemini, Claude, OpenAI all support native tool calling via LangChain |
| create_react_agent (v1) | create_react_agent (v2) / create_agent | 2026 | v2 is default; create_agent is newer recommended API in LangChain docs |
| Gemini 2.0 Flash | Gemini 2.5 Flash | Mid-2025 | 2.0 Flash deprecated (shutdown March 31, 2026); 2.5 Flash is current |
| langchain-google-genai 1.x | langchain-google-genai 4.2.x | Late 2025 | v4 uses consolidated google-genai SDK; full tool calling support |

**Deprecated/outdated:**
- LangChain `AgentExecutor`: Replaced by LangGraph agents. Do not use.
- `create_react_agent` from `langchain.agents`: Old import path. Use `langgraph.prebuilt.create_react_agent`.
- Gemini 2.0 Flash: Shutting down March 31, 2026. Use `gemini-2.5-flash`.
- langchain-google-genai < 4.0: Uses legacy SDK. v4+ uses consolidated `google-genai`.

## Open Questions

1. **MCP Client Transport: Stdio subprocess vs Direct Function Calls**
   - What we know: The MCP server currently runs via `mcp.run(transport="stdio")`. langchain-mcp-adapters can connect via stdio (spawns subprocess) or HTTP (network). Alternatively, we could bypass MCP protocol entirely and call the data_store functions directly as LangChain @tool functions.
   - What's unclear: Whether the stdio subprocess overhead is significant for the 3-second target. Direct function calls would be faster but lose the MCP protocol boundary.
   - Recommendation: Start with stdio transport (clean architecture, matches Phase 10 deployment). If latency is too high, we can switch to direct tool functions as a fallback. The tool schemas remain the same either way.

2. **LLM Choice: Gemini vs Claude for Agent**
   - What we know: Project has GEMINI_API_KEY in .env (used for extraction). Gemini 2.5 Flash has ~400ms TTFT, 258 tok/s. Claude Haiku 4.5 is reportedly 4-5x faster than Sonnet. Both support tool calling via LangChain.
   - What's unclear: Which provides more reliable tool calling with the specific MCP tool schemas (Manufacturer enum, ModelName Literal, SpecCategory enum). The user chose Gemini for extraction but hasn't specified for the agent.
   - Recommendation: Start with Gemini 2.5 Flash (already has API key, no additional cost). The langchain-google-genai integration supports tool calling. If Gemini's tool calling proves unreliable, switch to Claude Haiku 4.5 via langchain-anthropic. The agent code change is a single line (swap ChatGoogleGenerativeAI for ChatAnthropic).

3. **Agent Lifecycle: Per-Request vs Persistent**
   - What we know: MultiServerMCPClient manages subprocess connections. Creating a new client per request has high overhead (subprocess startup). A persistent client risks subprocess crashes.
   - What's unclear: Whether a persistent MCP client reliably handles hundreds of sequential tool calls without subprocess issues.
   - Recommendation: Use FastAPI lifespan to create the MCP client and agent once at startup. Add error handling/reconnection logic if the subprocess dies. For Phase 6 development/testing, per-request creation is acceptable for test simplicity.

4. **create_react_agent vs create_agent**
   - What we know: LangChain docs now recommend `create_agent` as the newer API. `create_react_agent` from `langgraph.prebuilt` still works and is widely used. `create_agent` was introduced more recently and may have slightly different parameters.
   - What's unclear: Whether `create_agent` has feature parity and whether it handles MCP tools the same way.
   - Recommendation: Use `create_react_agent` from `langgraph.prebuilt` as it is well-documented, widely used in examples, and confirmed to work with MCP tools. The newer `create_agent` can be evaluated for Phase 7.

## Sources

### Primary (HIGH confidence)
- [LangGraph PyPI](https://pypi.org/project/langgraph/) - Version 1.0.8, Feb 6 2026, Python >=3.10
- [langchain-mcp-adapters PyPI](https://pypi.org/project/langchain-mcp-adapters/) - Version 0.2.1, Dec 9 2025
- [langchain-mcp-adapters GitHub](https://github.com/langchain-ai/langchain-mcp-adapters) - MultiServerMCPClient API, stdio/HTTP transport, tool loading
- [langchain-google-genai PyPI](https://pypi.org/project/langchain-google-genai/) - Version 4.2.0, Jan 13 2026
- [langchain-anthropic PyPI](https://pypi.org/project/langchain-anthropic/) - Version 1.3.3, Feb 10 2026
- [Google Gemini Models](https://ai.google.dev/gemini-api/docs/models) - gemini-2.5-flash model ID, tool calling support confirmed
- [LangGraph ReAct Agent How-To](https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/) - Agent architecture, StateGraph pattern
- [LangGraph Agents Reference](https://reference.langchain.com/python/langgraph/agents/) - create_react_agent parameters, v1/v2 versions
- [LangChain MCP Docs](https://docs.langchain.com/oss/python/langchain/mcp) - Official MCP integration documentation
- [LangChain Testing Docs](https://docs.langchain.com/oss/python/langchain/test) - GenericFakeChatModel, InMemorySaver, agentevals
- [ChatGoogleGenerativeAI Reference](https://reference.langchain.com/python/integrations/langchain_google_genai/ChatGoogleGenerativeAI/) - Constructor params, tool calling, model names
- [Gemini ReAct Example](https://ai.google.dev/gemini-api/docs/langgraph-example) - Official Google example of Gemini + LangGraph

### Secondary (MEDIUM confidence)
- [LangGraph Structured Output](https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output/) - Formatting node pattern for structured agent output
- [Artificial Analysis Gemini 2.5 Flash](https://artificialanalysis.ai/models/gemini-2-5-flash) - ~400ms TTFT, 258 tok/s throughput
- [Claude Haiku 4.5](https://www.anthropic.com/claude/haiku) - 4-5x faster than Sonnet, tool calling support
- [LangGraph + MCP Neo4j Example](https://neo4j.com/blog/developer/react-agent-langgraph-mcp/) - Production pattern with MultiServerMCPClient

### Tertiary (LOW confidence)
- [Gemini Free Tier Limits](https://ai.google.dev/gemini-api/docs/rate-limits) - 10 RPM, 250 RPD for free tier; may need paid tier for testing
- Agent lifecycle management patterns (persistent vs per-request) - Based on community patterns, not official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All library versions verified on PyPI; LangGraph 1.0.8, langchain-mcp-adapters 0.2.1, langchain-google-genai 4.2.0 are current stable releases
- Architecture: HIGH - create_react_agent + MCP tools pattern confirmed by multiple official sources (LangChain docs, Google docs, GitHub examples)
- Pitfalls: HIGH - Anti-hallucination concern is well-documented in LLM agent literature; MCP lifecycle issues verified against langchain-mcp-adapters docs; Gemini 2.0 deprecation confirmed by Google
- Testing: MEDIUM - GenericFakeChatModel confirmed in LangChain test docs; integration test matrix pattern is sound but specific test assertions may need tuning against real LLM behavior
- Performance (3s target): MEDIUM - Gemini Flash latency benchmarks suggest feasibility but end-to-end latency including MCP subprocess overhead is untested

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (LangGraph and langchain-mcp-adapters are actively developed; check for breaking changes)
