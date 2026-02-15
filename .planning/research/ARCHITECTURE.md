# Architecture Research

**Domain:** AI-powered technical knowledge assistant with multi-agent orchestration, structured data lookup, ETL pipeline, and React frontend
**Researched:** 2026-02-14
**Confidence:** HIGH (core patterns) / MEDIUM (specific integration details)

## System Overview

```
                          PRESENTATION LAYER
 ============================================================================
 |  React Frontend (Vite + assistant-ui or custom chat UI)                  |
 |  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐       |
 |  │  Chat Panel   │  │ Status/Debug │  │  ETL Review Dashboard    │       |
 |  │  (Q&A flow)   │  │   Panel      │  │  (human verification)   │       |
 |  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘       |
 ============================================================================
           │ SSE/HTTP          │ REST                  │ REST
           ▼                   ▼                       ▼
                          API LAYER
 ============================================================================
 |  FastAPI Server                                                          |
 |  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐       |
 |  │ /chat        │  │ /health      │  │ /etl/*                   │       |
 |  │ (SSE stream) │  │ /status      │  │ (review, approve, reject)│       |
 |  └──────┬───────┘  └──────────────┘  └────────────┬─────────────┘       |
 ============================================================================
           │                                          │
           ▼                                          ▼
                     ORCHESTRATION LAYER
 ============================================================================
 |  LangGraph Multi-Agent Graph                                             |
 |                                                                          |
 |  ┌─────────────┐    handoff     ┌──────────────┐    handoff             |
 |  │  Concierge  │ ─────────────► │  Specialist  │ ──────────►           |
 |  │  Agent      │                │  (Dex) Agent │             │          |
 |  │             │ ◄───────────── │              │             │          |
 |  │ - Clarify   │    response    │ - Query data │             │          |
 |  │ - Format    │                │ - MCP tools  │             ▼          |
 |  │ - Converse  │                └──────────────┘    ┌──────────────┐    |
 |  └─────────────┘                                    │  Validator   │    |
 |        ▲                                            │  Agent       │    |
 |        │              response                      │              │    |
 |        └────────────────────────────────────────────│ - Check gaps │    |
 |                                                     │ - Flag miss  │    |
 |                                                     └──────────────┘    |
 ============================================================================
           │ (Specialist calls MCP tools)
           ▼
                       DATA ACCESS LAYER
 ============================================================================
 |  FastMCP Server (Python, local process)                                  |
 |  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐       |
 |  │ lookup_part  │  │ get_specs    │  │ list_models              │       |
 |  │              │  │              │  │                          │       |
 |  │ (exact part# │  │ (full spec  │  │ (enumerate available     │       |
 |  │  by model)   │  │  sheet data)│  │  manufacturers/models)   │       |
 |  └──────┬───────┘  └──────┬──────┘  └────────────┬─────────────┘       |
 ============================================================================
           │                  │                       │
           ▼                  ▼                       ▼
                        DATA LAYER
 ============================================================================
 |  Structured JSON Files (POC) → PostgreSQL (production)                   |
 |  ┌──────────────────────────────────────────────────────────────┐        |
 |  │  data/                                                       │        |
 |  │  ├── sundance/                                               │        |
 |  │  │   └── 880-series/                                         │        |
 |  │  │       ├── aspen-2026.json                                 │        |
 |  │  │       └── optima-2026.json                                │        |
 |  │  ├── hotspring/                                              │        |
 |  │  │   └── highlife/                                           │        |
 |  │  │       ├── grandee-2026.json                               │        |
 |  │  │       └── ...                                             │        |
 |  │  └── bullfrog/                                               │        |
 |  │      └── m-series/                                           │        |
 |  │          ├── m9-2026.json                                    │        |
 |  │          └── ...                                             │        |
 |  └──────────────────────────────────────────────────────────────┘        |
 ============================================================================

              OFFLINE / BATCH PIPELINE (separate from runtime)
 ============================================================================
 |  ETL Pipeline                                                            |
 |  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐       |
 |  │ Extract  │───►│Transform │───►│ Validate │───►│ Load         │       |
 |  │          │    │          │    │ (human   │    │              │       |
 |  │ PDF parse│    │ LLM +    │    │  review) │    │ Write JSON   │       |
 |  │ Web scrape│   │ schema   │    │          │    │              │       |
 |  └──────────┘    └──────────┘    └──────────┘    └──────────────┘       |
 ============================================================================
```

## Component Responsibilities

| Component | Responsibility | Communicates With | Typical Implementation |
|-----------|----------------|-------------------|------------------------|
| **React Frontend** | User interaction, chat UI, ETL review dashboard | FastAPI via HTTP/SSE | Vite + React + assistant-ui or custom chat components + Tailwind/shadcn |
| **FastAPI Server** | HTTP API, SSE streaming, request routing, CORS, auth | Frontend (HTTP), LangGraph (Python calls), ETL pipeline (REST) | FastAPI with Pydantic models, SSE endpoints for streaming |
| **Concierge Agent** | Clarify user intent, manage conversation flow, format final responses | Specialist via handoff, Validator via handoff, Frontend via state | LangGraph node with system prompt, no tool access |
| **Specialist (Dex) Agent** | Execute precise data queries, return raw structured results | MCP Server via tools, Concierge/Validator via handoff | LangGraph node with MCP tools bound |
| **Validator Agent** | Check completeness, flag missing data, verify all spec fields covered | Concierge via handoff (returns validated or flagged response) | LangGraph node with validation logic, no tool access |
| **FastMCP Server** | Expose structured data as deterministic tools (no LLM in this layer) | JSON data files (read), Specialist Agent (called by) | FastMCP 3.x Python, tools return exact JSON, no inference |
| **Structured JSON Data** | Ground truth for all specs, parts, dimensions | MCP Server (read by), ETL Pipeline (written by) | JSON files organized by manufacturer/series/model |
| **ETL Pipeline** | Extract specs from PDFs/websites, transform to structured JSON, human review | Source documents (read), JSON data (write), Review UI (human approval) | Python scripts, LLM-assisted extraction with Pydantic schemas |

## Recommended Project Structure

```
dex/
├── backend/                    # Python backend (FastAPI + LangGraph + MCP)
│   ├── pyproject.toml          # Python project config (uv/pip)
│   ├── src/
│   │   ├── api/                # FastAPI application
│   │   │   ├── __init__.py
│   │   │   ├── main.py         # FastAPI app, CORS, routes
│   │   │   ├── routes/
│   │   │   │   ├── chat.py     # POST /chat → SSE streaming endpoint
│   │   │   │   ├── health.py   # GET /health, GET /status
│   │   │   │   └── etl.py      # ETL review endpoints
│   │   │   └── models/         # Pydantic request/response schemas
│   │   │       ├── chat.py
│   │   │       └── etl.py
│   │   │
│   │   ├── agents/             # LangGraph multi-agent system
│   │   │   ├── __init__.py
│   │   │   ├── graph.py        # Main LangGraph graph definition
│   │   │   ├── state.py        # Shared TypedDict state schema
│   │   │   ├── concierge.py    # Concierge agent node + prompt
│   │   │   ├── specialist.py   # Specialist agent node + MCP tools
│   │   │   └── validator.py    # Validator agent node + checks
│   │   │
│   │   ├── mcp_server/         # FastMCP data access server
│   │   │   ├── __init__.py
│   │   │   ├── server.py       # FastMCP server definition
│   │   │   ├── tools/          # Individual MCP tool definitions
│   │   │   │   ├── lookup.py   # lookup_part, get_specs, list_models
│   │   │   │   └── search.py   # search_by_attribute, cross_reference
│   │   │   └── data_loader.py  # Load and index JSON data files
│   │   │
│   │   └── etl/                # ETL pipeline (offline/batch)
│   │       ├── __init__.py
│   │       ├── extract/        # Source-specific extractors
│   │       │   ├── pdf.py      # PDF parsing (pdfplumber, Docling)
│   │       │   └── web.py      # Web scraping extractors
│   │       ├── transform/      # LLM-assisted transformation
│   │       │   ├── schema.py   # Pydantic models for spec data
│   │       │   └── llm.py      # LLM extraction + schema validation
│   │       ├── validate/       # Human review pipeline
│   │       │   ├── queue.py    # Review queue management
│   │       │   └── diff.py     # Show extraction vs source comparison
│   │       └── load/           # Write validated JSON
│   │           └── writer.py   # Write to data/ directory
│   │
│   └── tests/
│       ├── test_agents/
│       ├── test_mcp/
│       └── test_etl/
│
├── frontend/                   # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── chat/           # Chat interface components
│   │   │   │   ├── ChatPanel.tsx
│   │   │   │   ├── MessageList.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── InputBar.tsx
│   │   │   ├── etl/            # ETL review dashboard
│   │   │   │   ├── ReviewQueue.tsx
│   │   │   │   ├── ExtractionDiff.tsx
│   │   │   │   └── ApprovalForm.tsx
│   │   │   └── common/         # Shared UI components
│   │   ├── hooks/              # Custom React hooks
│   │   │   ├── useChat.ts      # SSE connection, message state
│   │   │   └── useETLReview.ts
│   │   ├── services/           # API client layer
│   │   │   └── api.ts          # Fetch wrappers for backend
│   │   └── types/              # TypeScript type definitions
│   │       └── index.ts
│   └── tsconfig.json
│
├── data/                       # Structured JSON spec data (ground truth)
│   ├── sundance/
│   │   └── 880-series/
│   │       ├── aspen-2026.json
│   │       └── ...
│   ├── hotspring/
│   │   └── highlife/
│   │       └── ...
│   └── bullfrog/
│       └── m-series/
│           └── ...
│
├── data/schemas/               # JSON Schema definitions for spec data
│   └── model-spec.schema.json  # Canonical schema all data conforms to
│
└── docs/                       # Internal documentation
    └── data-format.md          # Spec JSON format documentation
```

### Structure Rationale

- **backend/src/api/:** Thin HTTP layer. Its only job is request validation, SSE streaming setup, and calling into the agents or ETL modules. Keeps HTTP concerns separate from AI logic.
- **backend/src/agents/:** All LangGraph orchestration lives here. The graph.py file is the single entry point that wires Concierge, Specialist, and Validator together. State.py defines the shared state schema so all agents agree on data shape.
- **backend/src/mcp_server/:** Completely separate from agents. The MCP server is a standalone process that exposes deterministic tools. It reads from data/ and returns exact JSON. Zero LLM involvement in this layer -- this is the key architectural boundary that prevents hallucination.
- **backend/src/etl/:** Offline pipeline, never runs during user queries. Batch process that extracts from source documents, transforms with LLM assistance, and queues for human review before writing to data/.
- **frontend/:** Standard Vite + React app. Could be swapped for any frontend without touching backend. Communicates exclusively via HTTP/SSE.
- **data/:** Separate from code. Versioned ground truth. The ETL pipeline writes here, the MCP server reads from here. This separation means you can update data without redeploying code.

## Architectural Patterns

### Pattern 1: Supervisor-with-Handoffs (Agent Orchestration)

**What:** A Concierge agent acts as supervisor, using LangGraph's handoff mechanism to delegate to Specialist and Validator agents. Control flows through handoff tools -- the Concierge decides who to invoke and when, based on conversation state.

**When to use:** When you need sequential, conversation-aware orchestration where the LLM decides the next step based on evolving context. This is the Dex use case -- clarify intent first, then query, then validate.

**Trade-offs:**
- (+) Natural conversation flow with state preservation across agent transitions
- (+) Each agent has focused system prompt and limited tool access (principle of least privilege)
- (+) Concierge can loop back to Specialist if Validator flags gaps
- (-) Adds one extra model call per handoff (latency cost)
- (-) More complex to debug than a single agent

**Example:**
```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters import MultiServerMCPClient

# Shared state across all agents
class DexState(TypedDict):
    messages: Annotated[list, add_messages]
    current_agent: str
    query_context: dict  # manufacturer, series, model, year
    lookup_results: dict | None
    validation_status: str  # "pending" | "complete" | "gaps_found"

# Concierge: clarifies intent, formats responses
concierge = create_react_agent(
    model=model,
    tools=[],  # No data tools -- only handoffs
    name="concierge",
    prompt=CONCIERGE_SYSTEM_PROMPT,
)

# Specialist: queries structured data via MCP
async with MultiServerMCPClient({"dex_data": {...}}) as client:
    mcp_tools = await client.get_tools()

specialist = create_react_agent(
    model=model,
    tools=mcp_tools,  # MCP tools for exact lookup
    name="specialist",
    prompt=SPECIALIST_SYSTEM_PROMPT,
)

# Validator: checks completeness
validator = create_react_agent(
    model=model,
    tools=[],  # Reads state only
    name="validator",
    prompt=VALIDATOR_SYSTEM_PROMPT,
)
```

### Pattern 2: Deterministic Data Access via MCP (Zero-Hallucination Layer)

**What:** All data access goes through MCP tools that execute deterministic queries against structured JSON. The LLM never sees raw data files -- it calls named tools with typed parameters and gets exact results. The MCP server contains zero LLM logic; it is pure Python functions reading JSON.

**When to use:** When accuracy is non-negotiable and you need to guarantee that the data the LLM presents to users comes from verified sources with no inference or interpolation.

**Trade-offs:**
- (+) Eliminates hallucination at the data layer -- tools return exactly what is in the JSON
- (+) Auditable: every tool call has typed inputs and deterministic outputs
- (+) Testable: MCP tools are regular Python functions with predictable behavior
- (+) Swappable: replace JSON files with PostgreSQL later without changing agent code
- (-) Requires comprehensive tool design upfront -- if a query type is not a tool, the agent cannot answer it
- (-) More rigid than RAG -- cannot handle fuzzy/exploratory queries

**Example:**
```python
from fastmcp import FastMCP

mcp = FastMCP("dex-data")

@mcp.tool()
def lookup_part(
    manufacturer: str,
    model: str,
    year: int,
    spec_category: str
) -> dict:
    """Look up exact part specification for a spa model.

    Returns the complete spec entry including part_number,
    description, hp_wattage, and compatibility_notes.
    Returns {"error": "not_found"} if no match exists.
    """
    data = load_model_data(manufacturer, model, year)
    if data is None:
        return {"error": "not_found", "detail": f"No data for {manufacturer} {model} {year}"}

    spec = data.get("specs", {}).get(spec_category)
    if spec is None:
        return {"error": "spec_not_found", "detail": f"No {spec_category} data for this model"}

    return {
        "manufacturer": manufacturer,
        "model": model,
        "year": year,
        "category": spec_category,
        "data": spec  # Exact JSON from verified data file
    }

@mcp.tool()
def list_models(manufacturer: str | None = None) -> list[dict]:
    """List all available spa models in the database.

    Optionally filter by manufacturer. Returns model name,
    series, year, and available spec categories.
    """
    # Pure deterministic file enumeration
    ...

@mcp.tool()
def get_full_spec_sheet(manufacturer: str, model: str, year: int) -> dict:
    """Get complete spec sheet for a model across all 10 categories."""
    ...
```

### Pattern 3: SSE Streaming for Real-Time Chat

**What:** The FastAPI backend streams agent responses to the React frontend using Server-Sent Events (SSE). This provides real-time token-by-token display without the complexity of WebSocket bidirectional communication. The frontend sends a POST request and receives a streaming SSE response.

**When to use:** For chat interfaces where users expect to see responses appear progressively. SSE is simpler than WebSockets for the unidirectional streaming pattern (server pushes to client) that chat UIs need.

**Trade-offs:**
- (+) Simpler than WebSockets -- HTTP-based, works through proxies and load balancers easily
- (+) Native browser support via EventSource API
- (+) Automatic reconnection built into EventSource
- (-) Unidirectional only (server to client) -- sufficient for chat but not for features needing bidirectional real-time communication
- (-) Limited browser connection pool (6 per domain in HTTP/1.1)

**Example:**
```python
# FastAPI endpoint
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

@app.post("/chat")
async def chat(request: ChatRequest):
    async def event_stream():
        async for event in run_agent_graph(request.message, request.session_id):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

```typescript
// React frontend
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, session_id }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  // Parse SSE events and update UI
}
```

### Pattern 4: Offline ETL with Human-in-the-Loop Validation

**What:** A batch pipeline extracts specs from manufacturer PDFs and websites, transforms them into structured JSON using LLM-assisted extraction with Pydantic schema enforcement, then queues results for human review before writing to the data directory. The ETL pipeline is completely separate from the runtime query system.

**When to use:** When source data is unstructured (PDFs, websites) but output must be 100% verified structured data. The human review step is non-negotiable when wrong data means wrong physical parts.

**Trade-offs:**
- (+) LLM handles the heavy lifting of understanding PDF layouts and extracting fields
- (+) Pydantic schema enforcement catches structural errors automatically
- (+) Human review catches semantic errors the LLM might miss
- (+) Offline -- does not affect query latency or runtime reliability
- (-) Slower to onboard new models (human bottleneck)
- (-) Requires building a review UI

## Data Flow

### Runtime Query Flow (User asks a question)

```
User types: "What pump does the 2026 Sundance Aspen use?"
    │
    ▼
React Frontend ──POST /chat──► FastAPI Server
    │                               │
    │                         Creates LangGraph session
    │                               │
    │                               ▼
    │                     ┌── Concierge Agent ──┐
    │                     │  Reads message       │
    │                     │  Has enough context?  │
    │                     │  YES: handoff to      │
    │                     │       Specialist       │
    │                     │  NO: ask clarifying Q  │
    │                     └──────────┬────────────┘
    │                                │ handoff
    │                                ▼
    │                     ┌── Specialist Agent ──┐
    │                     │  Calls MCP tool:      │
    │                     │  lookup_part(          │
    │                     │    "sundance",         │
    │                     │    "aspen",            │
    │                     │    2026,               │
    │                     │    "jet_pump"           │
    │                     │  )                     │
    │                     │  Gets exact JSON back  │
    │                     │  Handoff to Validator  │
    │                     └──────────┬────────────┘
    │                                │ handoff
    │                                ▼
    │                     ┌── Validator Agent ───┐
    │                     │  Checks: all fields  │
    │                     │  present? Part # set? │
    │                     │  HP/wattage included?  │
    │                     │  PASS: handoff back   │
    │                     │  FAIL: flag gaps,     │
    │                     │        handoff back   │
    │                     └──────────┬────────────┘
    │                                │ handoff
    │                                ▼
    │                     ┌── Concierge Agent ──┐
    │                     │  Formats response:   │
    │                     │  "The 2026 Sundance  │
    │                     │   Aspen uses the     │
    │                     │   [exact part data]" │
    │                     └──────────┬───────────┘
    │                                │
    │◄───────SSE stream──────────────┘
    │
    ▼
React renders formatted response with part details
```

### ETL Pipeline Flow (Extracting data from sources)

```
Source PDF/Website
    │
    ▼
Extract Phase
    │  - pdfplumber/Docling for PDF table extraction
    │  - Web scraper for manufacturer sites
    │  - Raw text + table data output
    │
    ▼
Transform Phase
    │  - LLM (Claude/GPT) with Pydantic schema
    │  - Structured output enforcement
    │  - "Extract these 10 spec categories from this text"
    │  - Automated validation: schema check, type check
    │  - LLM-challenge: second LLM verifies extraction
    │
    ▼
Human Review Queue
    │  - Side-by-side: source PDF vs extracted JSON
    │  - Field-by-field approval/correction
    │  - Reviewer marks each field: correct / corrected / missing
    │  - Confidence scores visible
    │
    ▼
Load Phase
    │  - Write approved JSON to data/ directory
    │  - JSON Schema validation before write
    │  - Git-trackable (JSON files in repo)
    │
    ▼
data/sundance/880-series/aspen-2026.json  (verified ground truth)
```

### Key Data Flows

1. **Chat flow:** User message -> FastAPI -> LangGraph graph (Concierge -> Specialist -> Validator -> Concierge) -> SSE stream -> React UI. The LLM orchestrates but never invents data. All factual content comes from MCP tool responses.

2. **Data access flow:** Specialist agent calls MCP tool -> FastMCP server reads JSON file -> returns exact data -> Specialist includes in response. No vector search, no similarity matching, no inference on the data layer.

3. **ETL flow:** Source document -> Extract (parsing) -> Transform (LLM + schema) -> Review queue (human) -> Load (JSON write). Completely offline. Runtime system never calls the ETL pipeline.

4. **State flow:** LangGraph manages a shared `DexState` TypedDict that flows through all agent nodes. Messages accumulate via reducer. Current agent, query context, lookup results, and validation status are tracked. This state is the single source of truth for a conversation turn.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| POC (1-5 users, 19 models) | Monolith is correct. Single FastAPI process, in-process LangGraph, in-process MCP server, JSON files on disk. No database needed. |
| Small production (10-50 users, 100+ models) | Add PostgreSQL to replace JSON files. Add session persistence. Consider LangGraph Platform or Redis for state checkpointing. MCP server still in-process. |
| Medium production (50-500 users, 1000+ models) | Separate MCP server into its own process (FastMCP supports HTTP transport). Add caching layer for frequent lookups. Consider queue-based ETL with Celery/RQ. |
| Large (500+ users) | LangGraph Platform (managed). Database connection pooling. CDN for frontend. Horizontal scaling of API layer behind load balancer. |

### Scaling Priorities

1. **First bottleneck: LLM API latency.** Each query makes 3-4 LLM calls (Concierge, Specialist, Validator, Concierge again). At ~1-2s per call, total latency is 4-8s. Mitigation: use faster models for Validator (e.g., GPT-4o-mini or Claude Haiku for validation checks). Consider parallel execution where agents do not depend on each other.

2. **Second bottleneck: Concurrent sessions.** FastAPI handles this well with async, but LangGraph state management under concurrent load needs attention. Mitigation: ensure stateless request handling (each chat request carries session context or loads from checkpointer).

3. **Third bottleneck: Data volume.** With 19 models and 10 categories, JSON files are trivially small. At 1000+ models, consider PostgreSQL for indexed queries. The MCP tool interface stays the same -- only the implementation behind the tools changes.

## Anti-Patterns

### Anti-Pattern 1: Letting the LLM Read Data Files Directly

**What people do:** Give the LLM access to raw JSON/database via a generic "read file" or "run SQL" tool, letting it interpret and filter data.
**Why it is wrong:** The LLM can misinterpret data, skip fields, invent values, or return partial results. When a wrong part number means a wrong physical part ships, this is unacceptable. You also lose auditability -- you cannot trace exactly what query produced what result.
**Do this instead:** Create purpose-built MCP tools with typed parameters and deterministic outputs. The tool does the lookup, not the LLM. The LLM's job is only to determine which tool to call and with what parameters.

### Anti-Pattern 2: RAG / Vector Search for Structured Data

**What people do:** Embed spec sheets into a vector database and use similarity search to find relevant chunks when users ask questions.
**Why it is wrong:** Vector similarity returns "close enough" results. For part numbers, close enough means wrong. Embedding "pump model XYZ-1234" and "pump model XYZ-1235" will have nearly identical vectors, but they are completely different physical parts. RAG is designed for fuzzy knowledge retrieval -- this domain demands exact retrieval.
**Do this instead:** Structure data into a deterministic schema and query it with exact-match tools. Use JSON files (POC) or a relational database (production) with precise queries. The MCP tool layer provides this deterministic interface.

### Anti-Pattern 3: Monolithic Single-Agent with All Tools

**What people do:** Create one agent with system prompt containing all instructions (conversation management + data lookup + validation) and all tools bound.
**Why it is wrong:** The system prompt becomes enormous and the agent struggles to follow all instructions consistently. Tool selection becomes noisy with many tools competing. Validation steps get skipped when the agent "decides" the answer is good enough. Testing is impossible -- you cannot test conversation flow separately from data access.
**Do this instead:** Separate concerns into agents. Concierge owns conversation. Specialist owns data access. Validator owns quality checks. Each has a focused prompt and limited tools. The LangGraph graph enforces the flow.

### Anti-Pattern 4: Skipping Human Review in ETL

**What people do:** Trust LLM extraction output directly and load it into the data store without human verification.
**Why it is wrong:** LLMs hallucinate. Even with Pydantic schema enforcement, the LLM can extract the wrong value from the right field. A pump spec of "2.5 HP" might get extracted as "2.0 HP" because the LLM misread a table. In this domain, that error propagates silently until a customer gets the wrong part.
**Do this instead:** Every extracted record goes through human review before it becomes ground truth. Build the review UI as part of the POC -- it is not optional scaffolding, it is core infrastructure.

### Anti-Pattern 5: Coupling ETL Pipeline to Runtime System

**What people do:** Run extraction on-demand when a user asks about a model that does not have data yet, or mix ETL code into the agent pipeline.
**Why it is wrong:** Extraction is slow (PDF parsing + LLM calls + human review). Mixing it with runtime queries creates unpredictable latency. Failures in extraction should not affect query availability. The two systems have completely different reliability requirements.
**Do this instead:** Keep ETL as a separate offline pipeline. Runtime system reads only from verified data. If data does not exist for a model, the system should say "I don't have data for that model" rather than trying to extract it on the fly.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM Provider (Anthropic/OpenAI) | API key, langchain chat model abstraction | Used by agents for reasoning. Consider using different models for different agents (capable model for Specialist, fast model for Validator) |
| Manufacturer PDFs | File system / download + pdfplumber/Docling | ETL only. Parse offline, not at query time |
| Manufacturer Websites | Web scraper (requests/playwright) | ETL only. Check terms of service. Some sites may block scraping |
| Hosting Platform (deployment) | Docker compose or cloud provider | FastAPI + React both containerized |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend <-> API | HTTP REST + SSE | Clean API contract. Frontend is stateless. Session state lives in backend. |
| API <-> Agents | Python function calls (in-process for POC) | FastAPI endpoint calls LangGraph graph.ainvoke(). Same Python process. |
| Agents <-> MCP Server | MCP protocol (stdio transport for POC) | langchain-mcp-adapters loads tools from FastMCP server. Specialist agent calls tools by name. |
| MCP Server <-> Data | Python file I/O (JSON.load) | Simplest possible. MCP server reads JSON files from data/ directory. Swap to SQLAlchemy for PostgreSQL later. |
| ETL Pipeline <-> Data | Python file I/O (JSON.dump) | ETL writes to data/ directory after human approval. Same JSON schema the MCP server expects. |
| ETL Pipeline <-> Review UI | REST API (FastAPI endpoints) | Review queue exposed as REST endpoints. Frontend renders review dashboard. |

## Build Order and Dependencies

Understanding component dependencies is critical for phasing the roadmap correctly.

```
                    DEPENDENCY GRAPH

  JSON Schema ─────────────────────────────────────┐
  (defines data shape)                              │
       │                                            │
       ▼                                            ▼
  ETL Pipeline ──────► data/*.json ◄────── MCP Server Tools
  (populates data)     (ground truth)      (reads data)
                                                │
                                                ▼
                                      LangGraph Agents
                                      (use MCP tools)
                                                │
                                                ▼
                                        FastAPI Server
                                        (exposes agents)
                                                │
                                                ▼
                                      React Frontend
                                      (calls API)
```

**Suggested build order (bottom-up from data):**

1. **JSON Schema + Sample Data (first):** Define the canonical spec schema for all 10 categories. Create 2-3 sample JSON files by hand. This is the contract everything else depends on.

2. **MCP Server + Tools (second):** Build FastMCP tools that read from JSON files. Test with sample data. This is independently testable and the Specialist agent depends on it.

3. **LangGraph Agents (third):** Build agents one at a time. Specialist first (it has the MCP tools). Then Concierge (conversation management). Then Validator (quality checks). Wire into graph. Test with hardcoded messages.

4. **FastAPI Server (fourth):** Thin wrapper over LangGraph graph. SSE streaming endpoint. Health checks. Test end-to-end with curl/Postman.

5. **React Frontend (fifth):** Chat UI that calls the API. Can be built in parallel with steps 3-4 using mocked API responses.

6. **ETL Pipeline (can be parallel):** Does not depend on runtime system. Can be built alongside steps 2-5. But it does depend on the JSON Schema from step 1.

7. **ETL Review UI (last):** Depends on ETL pipeline producing review queue and on React frontend patterns being established.

**Key insight:** The JSON schema is the keystone. Define it first, then ETL and MCP server can be built in parallel since they both conform to the same schema.

## Sources

- [LangGraph Multi-Agent Orchestration Framework Guide](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025) - LangGraph architecture patterns and orchestration (MEDIUM confidence - blog source, verified against multiple sources)
- [LangGraph Official Site](https://www.langchain.com/langgraph) - Agent orchestration framework (HIGH confidence - official)
- [Choosing the Right Multi-Agent Architecture - LangChain Blog](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/) - Supervisor vs Router vs Handoffs tradeoffs (HIGH confidence - official LangChain blog)
- [langgraph-supervisor-py GitHub](https://github.com/langchain-ai/langgraph-supervisor-py) - Supervisor pattern implementation (HIGH confidence - official repo)
- [langchain-mcp-adapters GitHub](https://github.com/langchain-ai/langchain-mcp-adapters) - LangGraph + MCP integration (HIGH confidence - official repo)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25) - Model Context Protocol standard (HIGH confidence - official spec)
- [FastMCP 3.0 Release](https://www.jlowin.dev/blog/fastmcp-3) - FastMCP architecture primitives (HIGH confidence - library author)
- [FastMCP Updates](https://gofastmcp.com/updates) - FastMCP latest versions and features (HIGH confidence - official docs)
- [LLMs for Structured Data Extraction from PDFs](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/) - ETL extraction approaches (MEDIUM confidence - vendor blog but technically detailed)
- [Human-in-the-Loop for AI Document Processing](https://unstract.com/blog/human-in-the-loop-hitl-for-ai-document-processing/) - HITL validation patterns (MEDIUM confidence)
- [HITL Best Practices - Parseur](https://parseur.com/blog/hitl-best-practices) - Human review workflow design (MEDIUM confidence)
- [assistant-ui GitHub](https://github.com/assistant-ui/assistant-ui) - React AI chat library (HIGH confidence - official repo)
- [assistant-ui-langgraph-fastapi GitHub](https://github.com/Yonom/assistant-ui-langgraph-fastapi) - Reference architecture for LangGraph + FastAPI + React (MEDIUM confidence - community project by assistant-ui author)
- [FastAPI Full-Stack Template](https://github.com/fastapi/full-stack-fastapi-template) - FastAPI + React project structure (HIGH confidence - official FastAPI repo)
- [SSE with FastAPI, React, and LangGraph](https://www.softgrade.org/sse-with-fastapi-react-langgraph/) - Streaming architecture pattern (MEDIUM confidence - tutorial)
- [Deploy Streaming Agent APIs with FastAPI and WebSockets](https://www.decodingai.com/p/deploying-agents-as-real-time-apis) - Streaming deployment patterns (MEDIUM confidence)

---
*Architecture research for: Dex -- AI-powered technical knowledge assistant with multi-agent orchestration*
*Researched: 2026-02-14*
