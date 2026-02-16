# Phase 7: Multi-Agent Orchestration - Research

**Researched:** 2026-02-16
**Domain:** LangGraph multi-agent supervisor pattern with Gemini 2.5 Flash
**Confidence:** MEDIUM (Gemini compatibility needs validation; core patterns well-documented)

## Summary

Phase 7 transforms the single ReAct agent (Phase 6) into a Concierge/Specialist/Validator pipeline using LangGraph's supervisor pattern. The existing `create_react_agent` with MCP tools becomes the Specialist node, while Concierge (intent clarification, disambiguation) and Validator (response completeness checking) are added as new agents/nodes in a supervisor graph.

The standard approach uses the `langgraph-supervisor` package (v0.0.31, requires `langgraph>=1.0.2`) which provides `create_supervisor()` to orchestrate multiple `create_react_agent()` workers with tool-based handoffs. However, there is a critical Gemini compatibility concern: Gemini does not support the `name` attribute on AI messages that other providers use. The `include_agent_name="inline"` parameter on `create_supervisor()` solves this by embedding agent names in XML-style tags within the content field. Multi-turn conversation support comes from LangGraph's checkpointer system -- `InMemorySaver` for development, with `thread_id` passed in config to maintain conversation state across follow-up questions.

An important architectural decision: the Validator should NOT be an LLM-based agent making a third sequential LLM call. It should be a deterministic Python function that inspects the Specialist's response for completeness (checks for null/not-available fields, verifies tool calls were made, confirms the answer references actual data). This avoids the 3x latency concern flagged in STATE.md and keeps validation predictable.

**Primary recommendation:** Use `langgraph-supervisor` with `create_react_agent` workers. Set `include_agent_name="inline"` for Gemini compatibility. Make the Validator a deterministic `post_model_hook` or graph node (not an LLM agent). Use `InMemorySaver` checkpointer with `thread_id` for multi-turn conversation context.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=1.0.8 (already installed) | Agent orchestration framework | Foundation for all agent graphs |
| langgraph-supervisor | 0.0.31 | Hierarchical multi-agent supervisor | Official LangGraph library for supervisor pattern, `create_supervisor()` |
| langgraph-prebuilt | >=1.0.7 (already installed) | `create_react_agent` | Creates ReAct agents used as worker nodes |
| langchain-google-genai | >=4.2 (already installed) | Gemini 2.5 Flash LLM | Already used in Phase 6 single agent |
| langgraph-checkpoint | >=4.0.0 (already installed) | InMemorySaver checkpointer | Multi-turn conversation persistence via thread_id |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langgraph-checkpoint-sqlite | latest | SqliteSaver for persistent conversations | If conversation memory must survive server restarts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `langgraph-supervisor` | Manual `StateGraph` assembly | More control but more boilerplate; maintainers recommend starting with `create_supervisor` then migrating if needed |
| LLM-based Validator agent | Deterministic Python function | Function is faster, predictable, no hallucination risk -- strongly preferred for this use case |
| `InMemorySaver` | `SqliteSaver` | SQLite persists across restarts but adds disk dependency; InMemory is fine for POC |

**Installation:**
```bash
pip install langgraph-supervisor>=0.0.31
```

Note: `langgraph-supervisor` v0.0.31 requires `langgraph>=1.0.2,<2.0.0` and `langchain-core>=1.0.0,<2.0.0`. The project already has compatible versions installed (`langgraph 1.0.8`, `langchain-core 1.2.13`).

## Architecture Patterns

### Recommended Project Structure
```
backend/src/agent/
  graph.py            # MODIFY: multi-agent supervisor graph (replaces single agent)
  prompts.py          # MODIFY: split into per-agent prompts (concierge, specialist, validator)
  validator.py        # NEW: deterministic validation function
  config.py           # NEW: shared configuration (model factory, MCP client factory)

backend/src/api/
  app.py              # MODIFY: add thread_id support for multi-turn, checkpointer in lifespan
  models.py           # MODIFY: add conversation_id to request/response
```

### Pattern 1: Supervisor with create_react_agent Workers
**What:** A supervisor agent routes queries to specialized worker agents. Each worker is a `create_react_agent` with its own prompt and tools.
**When to use:** When agents have distinct roles with different tool access.
**Example:**
```python
# Source: langgraph-supervisor GitHub README + API reference
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.memory import InMemorySaver

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_output_tokens=1024,
)

# Concierge agent: intent clarification, no MCP tools
concierge = create_react_agent(
    model=model,
    tools=[],  # No data tools -- concierge only clarifies
    name="concierge",
    prompt="You are the Concierge for Dex...",
)

# Specialist agent: has MCP tools for data lookup
specialist = create_react_agent(
    model=model,
    tools=mcp_tools,  # The 3 MCP tools from Phase 5
    name="specialist",
    prompt="You are the Specialist for Dex...",
)

# Supervisor orchestrates routing
workflow = create_supervisor(
    agents=[concierge, specialist],
    model=model,
    prompt="You are the Dex supervisor...",
    # CRITICAL for Gemini: inline agent names since Gemini
    # doesn't support the name attribute on AI messages
    include_agent_name="inline",
    output_mode="last_message",
)

checkpointer = InMemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Invoke with thread_id for multi-turn
config = {"configurable": {"thread_id": "session-123"}}
result = app.invoke(
    {"messages": [{"role": "user", "content": "What pump does the Aspen use?"}]},
    config=config,
)
```

### Pattern 2: Deterministic Validator as Graph Node (Not LLM Agent)
**What:** After the Specialist responds, a Python function inspects the response for completeness rather than using an LLM.
**When to use:** When validation logic is deterministic (checking for null fields, verifying tool calls were made).
**Why:** Avoids a third LLM call, eliminates hallucination risk in validation, keeps latency down.
**Example:**
```python
# Source: LangGraph post_model_hook pattern + project-specific logic
def validate_response(state: dict) -> dict:
    """Deterministic validator -- no LLM call.

    Checks:
    1. Did the specialist make at least one tool call?
    2. Does the answer mention 'not available' for null fields?
    3. Is the answer substantive (not empty or trivially short)?
    """
    messages = state["messages"]
    ai_messages = [m for m in messages if hasattr(m, "type") and m.type == "ai"]
    tool_messages = [m for m in messages if hasattr(m, "type") and m.type == "tool"]

    warnings = []

    # Check tool usage
    if not tool_messages:
        warnings.append("No tool calls detected -- response may be fabricated")

    # Check answer length
    if ai_messages:
        last_ai = ai_messages[-1]
        content = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content)
        if len(content) < 20:
            warnings.append("Response too short -- may be incomplete")

    # Return warnings as metadata (not a new LLM message)
    return {"validation_warnings": warnings}
```

### Pattern 3: Multi-Turn Conversation with thread_id
**What:** The checkpointer saves full conversation state (all messages). Follow-up questions reuse the same `thread_id` so the agent sees prior context.
**When to use:** Always for multi-turn conversations.
**Example:**
```python
# Source: LangGraph persistence docs
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# First turn
config = {"configurable": {"thread_id": "session-abc"}}
result1 = app.invoke(
    {"messages": [{"role": "user", "content": "What pump does the Aspen use?"}]},
    config=config,
)

# Follow-up turn -- same thread_id, context maintained
result2 = app.invoke(
    {"messages": [{"role": "user", "content": "What about the filter for that model?"}]},
    config=config,
)
# The agent sees the full history: user asked about Aspen pump,
# now asks about filter -- no need to re-specify "Sundance Aspen"
```

### Pattern 4: FastAPI Integration with Conversation Sessions
**What:** The API endpoint accepts a `conversation_id` from the client. This becomes the `thread_id` for the checkpointer.
**When to use:** Always for the REST API.
**Example:**
```python
# Source: LangGraph + FastAPI integration pattern
from uuid import uuid4

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: str | None = Field(
        default=None,
        description="Session ID for multi-turn. Omit to start new conversation.",
    )

class QueryResponse(BaseModel):
    answer: str
    conversation_id: str  # Always returned so client can continue
    tool_calls: list[dict] | None = None

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    conv_id = request.conversation_id or str(uuid4())
    config = {"configurable": {"thread_id": conv_id}}

    result = await _agent.ainvoke(
        {"messages": [{"role": "user", "content": request.question}]},
        config=config,
    )
    # ... extract answer ...
    return QueryResponse(answer=answer_text, conversation_id=conv_id)
```

### Anti-Patterns to Avoid
- **LLM Validator agent for deterministic checks:** Using an LLM to check if fields are null is wasteful and unreliable. Use a Python function.
- **Passing full message history to every agent:** Use `output_mode="last_message"` on the supervisor to keep worker context lean. Full history balloons token usage.
- **Three sequential LLM calls for every query:** The Concierge should only activate when the query is ambiguous. Clear queries should route directly to the Specialist.
- **Separate MCP connections per agent:** Share the same MCP tools across all agents that need them. The MCP client is created once at startup.
- **Empty tools list causing Gemini errors:** Gemini may error with empty function declarations. If an agent has no tools, ensure the library handles this (or use a minimal no-op tool).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Supervisor routing | Custom StateGraph with conditional edges | `langgraph-supervisor.create_supervisor()` | Handles handoff tools, message passing, output modes |
| Conversation memory | Custom message list management | `InMemorySaver` checkpointer + `thread_id` | Built-in, handles state serialization and thread isolation |
| Agent handoff tools | Custom tool functions for delegation | `create_handoff_tool()` from langgraph-supervisor | Standard pattern, handles message forwarding correctly |
| Thread-safe graph sharing | Request-scoped agent instances | LangGraph compiled graph (thread-safe by design) | Confirmed safe for concurrent FastAPI requests |

**Key insight:** LangGraph's compiled graphs are thread-safe. A single compiled graph instance can be shared across all FastAPI requests. The `thread_id` in config is what isolates conversation state, not separate graph instances.

## Common Pitfalls

### Pitfall 1: Gemini Does Not Support `name` on AI Messages
**What goes wrong:** Supervisor handoffs fail with "Unknown / unsupported author" errors because Gemini doesn't support the `name` field that OpenAI/Anthropic use on AI messages.
**Why it happens:** The `langgraph-supervisor` library by default uses the `name` attribute to identify which agent produced a message.
**How to avoid:** Always set `include_agent_name="inline"` on `create_supervisor()`. This embeds agent identity in XML-style content tags instead: `<name>specialist</name><content>The pump is...</content>`
**Warning signs:** Errors mentioning "unsupported author" or agent names not being recognized.

### Pitfall 2: Three Sequential LLM Calls Exceeding Latency Budget
**What goes wrong:** Concierge LLM call + Specialist LLM call(s) + Validator LLM call = 3x the single-agent latency (currently 8-15s per call).
**Why it happens:** Each agent is an independent LLM invocation.
**How to avoid:** (1) Make Validator deterministic (Python function, not LLM). (2) Short-circuit Concierge for clear queries -- only invoke it for genuinely ambiguous ones. (3) The supervisor routing LLM call is unavoidable but should be fast with a focused prompt.
**Warning signs:** Response time consistently over 20 seconds.

### Pitfall 3: Gemini Errors with Empty Tool Schemas
**What goes wrong:** If an agent (like Concierge) has no tools, Gemini may reject the request because of empty `function_declarations`.
**Why it happens:** Gemini API requires non-empty properties for OBJECT type function parameters.
**How to avoid:** Either (1) don't pass `tools=[]` to Concierge -- use a simple LLM call node instead of `create_react_agent`, or (2) give Concierge a minimal tool (like `list_models`) that doesn't cause the empty schema issue.
**Warning signs:** Errors about "should be non-empty for OBJECT type".

### Pitfall 4: Message History Explosion in Multi-Turn
**What goes wrong:** Each turn adds all intermediate messages (tool calls, tool results, agent reasoning) to the conversation history. After 5-10 turns, the context window overflows.
**Why it happens:** The checkpointer saves ALL messages, including internal tool call/response pairs.
**How to avoid:** Use `output_mode="last_message"` on the supervisor so only the final answer is appended to the thread's history. Optionally implement a `pre_model_hook` to trim old messages.
**Warning signs:** Token count growing rapidly, responses slowing down after several turns.

### Pitfall 5: Losing Regression Compatibility
**What goes wrong:** The multi-agent system fails queries that the single agent handled correctly.
**Why it happens:** The Concierge may add unnecessary disambiguation steps, or the supervisor may route incorrectly.
**How to avoid:** Run the exact same integration test matrix from Phase 6 (test_agent_integration.py) against the new multi-agent graph. Every test that passed before must still pass.
**Warning signs:** Any of the 15 integration tests failing after the multi-agent refactor.

### Pitfall 6: Conversation ID Not Returned to Client
**What goes wrong:** The client cannot send follow-up questions because it doesn't know its conversation_id.
**Why it happens:** The API response doesn't include the conversation_id/thread_id.
**How to avoid:** Always return `conversation_id` in the QueryResponse. Generate a UUID if the client didn't provide one.
**Warning signs:** Follow-up questions start fresh conversations instead of continuing.

## Code Examples

### Complete Supervisor Graph Setup
```python
# Source: langgraph-supervisor README + API reference + Gemini adaptation
from __future__ import annotations

import os
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.memory import InMemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

def _create_model() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,
        max_output_tokens=1024,
    )

async def create_multi_agent(mcp_tools):
    model = _create_model()

    concierge = create_react_agent(
        model=model,
        tools=[mcp_tools[0]],  # list_models only for disambiguation
        name="concierge",
        prompt=CONCIERGE_PROMPT,
    )

    specialist = create_react_agent(
        model=model,
        tools=mcp_tools,  # All 3 MCP tools
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
    return workflow.compile(checkpointer=checkpointer)
```

### Supervisor Prompt Design
```python
SUPERVISOR_PROMPT = """\
You are the Dex routing supervisor. Route user queries to the right agent:

- Route to `concierge` ONLY when the query is ambiguous:
  - User mentions "the pump" without specifying a model
  - User asks about a category without specifying manufacturer/model
  - User's follow-up question lacks context that isn't in conversation history

- Route to `specialist` for ALL clear queries:
  - "What pump does the Sundance Aspen use?" -> specialist
  - "What filter does the Cameo use?" -> specialist
  - Any query where model and category are identifiable -> specialist

IMPORTANT: Most queries should go directly to specialist. Only use concierge
for genuinely ambiguous queries where disambiguation is needed.
"""
```

### Concierge Prompt Design
```python
CONCIERGE_PROMPT = """\
You are the Dex Concierge. Your ONLY job is to clarify ambiguous queries.

When a user query is ambiguous:
1. Identify what's missing (model name, manufacturer, spec category)
2. Ask a focused clarification question
3. Use list_models if you need to help the user identify their model

You cover 19 models across 3 manufacturers:
- Sundance (880 Series): Altamar, Aspen, Cameo, Capris, Marin, Optima, Vistamar
- Hot Spring (Highlife): Aria, Envoy, Grandee, Jetsetter, Jetsetter LX, Prodigy, Sovereign, Vanguard
- Bullfrog (M Series): M6, M7, M8, M9

NEVER answer spec questions yourself. NEVER fabricate data.
Your only output is a clarification question or a restated clear query.
"""
```

### FastAPI Lifespan with Checkpointer
```python
# Source: LangGraph + FastAPI integration pattern
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _mcp_client

    _mcp_client = _create_mcp_client()
    tools = await _mcp_client.get_tools()
    _agent = await create_multi_agent(tools)

    yield

    _agent = None
    _mcp_client = None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `langgraph.prebuilt.create_react_agent` | Still valid but deprecated in favor of `langchain.agents.create_agent` | Late 2025 | Deprecation warning but `create_react_agent` still works in langgraph 1.0.x; no need to migrate yet |
| Manual StateGraph supervisor | `langgraph-supervisor` package | Feb 2025 | Simplifies supervisor creation; recommended as starting point |
| Full message history between agents | `output_mode="last_message"` | 2025 | Reduces token usage, keeps worker contexts lean |
| Agent name via message `name` field | `include_agent_name="inline"` with XML tags | May 2025 | Gemini compatibility fix |
| LLM-based validation agents | Deterministic `post_model_hook` or graph node | 2025 best practice | Faster, more reliable, no hallucination risk |

**Deprecated/outdated:**
- `langgraph.prebuilt.create_react_agent` has a deprecation warning pointing to `langchain.agents.create_agent`, but the migration path is still unstable (the `create_agent` function was not available in some langchain versions). **Recommendation:** Continue using `langgraph.prebuilt.create_react_agent` for now since it works in the installed version (1.0.7) and `langgraph-supervisor` uses it internally.
- Older `langgraph-supervisor` versions (<0.0.29) are incompatible with `langgraph>=1.0.0`. Version 0.0.31 is compatible.

## Open Questions

1. **Gemini + langgraph-supervisor Python compatibility**
   - What we know: The JS version had known issues with Gemini (empty schemas, name attribute). Python v0.0.31 claims `langgraph>=1.0.2` compatibility and has `include_agent_name="inline"` support.
   - What's unclear: Whether Gemini-specific edge cases (empty tool schemas for tool-less agents, consecutive system messages) have been fully resolved in the Python package.
   - Recommendation: Build with `langgraph-supervisor` first. If Gemini errors occur, fall back to manual StateGraph assembly. Test early with a minimal 2-agent setup before building the full pipeline.

2. **Concierge agent with no/minimal tools**
   - What we know: Gemini may error on agents with empty function declarations.
   - What's unclear: Whether `create_react_agent(tools=[])` works with Gemini in langgraph-supervisor.
   - Recommendation: Give Concierge the `list_models` tool (useful for disambiguation anyway). If it still errors, implement Concierge as a plain LLM node in the graph instead of a `create_react_agent`.

3. **Latency impact of supervisor routing**
   - What we know: Single agent is 8-15s. Supervisor adds at least one more LLM call for routing.
   - What's unclear: Exact overhead of the supervisor routing call with Gemini 2.5 Flash.
   - Recommendation: Accept that multi-agent will be slower. Optimize by (1) deterministic Validator, (2) short-circuiting Concierge for clear queries, (3) keeping supervisor prompt minimal. Log timing at each stage.

4. **Validator as separate agent vs graph node vs post_model_hook**
   - What we know: `post_model_hook` is only available on `create_react_agent` v2, and only runs after the agent's own LLM call. A graph node runs after the entire agent subgraph completes.
   - What's unclear: Whether `post_model_hook` on the Specialist agent is sufficient, or whether validation needs to be a separate node in the supervisor graph that runs after the Specialist returns.
   - Recommendation: Implement Validator as a separate deterministic node in the supervisor graph (after Specialist, before returning to supervisor). This gives full access to the Specialist's complete output including all tool call results.

## Sources

### Primary (HIGH confidence)
- [LangGraph Supervisor API Reference](https://reference.langchain.com/python/langgraph/supervisor/) - `create_supervisor` full signature, `include_agent_name` parameter, `OutputMode` values
- [LangGraph Agents API Reference](https://reference.langchain.com/python/langgraph/agents/) - `create_react_agent` full signature with `name`, `checkpointer`, `post_model_hook` params
- [langgraph-supervisor PyPI](https://pypi.org/project/langgraph-supervisor/) - v0.0.31, Python>=3.10, dependencies
- [langgraph-supervisor GitHub](https://github.com/langchain-ai/langgraph-supervisor-py) - Installation, examples, pyproject.toml deps (`langgraph>=1.0.2,<2.0.0`)
- [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence) - `InMemorySaver`, `thread_id` config, checkpointer compilation

### Secondary (MEDIUM confidence)
- [LangGraph Multi-Agent Workflows Blog](https://blog.langchain.com/langgraph-multi-agent-workflows/) - Supervisor vs collaboration vs hierarchical patterns
- [LangGraph Supervisor Announcement](https://changelog.langchain.com/announcements/langgraph-supervisor-a-library-for-hierarchical-multi-agent-systems) - Design rationale, features
- [AI Agent Latency Blog](https://blog.langchain.com/how-do-i-speed-up-my-agent/) - Optimization strategies: parallelize, reduce LLM calls, use faster models
- [KINTO Tech Blog: Building Multi-Agent with Supervisor](https://blog.kinto-technologies.com/posts/2025-02-28-building-Multi-Agent-system-by-using-langgraph-supervisor/) - create_react_agent + create_supervisor working example
- [LangChain Forum: StateGraph vs createSupervisor](https://forum.langchain.com/t/stategraph-vs-createsupervisor-for-multi-agent-application/1096) - Start with createSupervisor, migrate to StateGraph when needed
- [LangChain Forum: Checkpointer with Supervisor](https://forum.langchain.com/t/can-create-supervisor-create-react-agent-use-checkpointer-and-store-for-across-thread-memory/1779) - Pass checkpointer at compile time

### Tertiary (LOW confidence)
- [GitHub Issue #6404: create_react_agent deprecation](https://github.com/langchain-ai/langgraph/issues/6404) - Deprecation message confusion; `create_react_agent` still works
- [GitHub Issue #33622: langgraph-supervisor dependency conflict](https://github.com/langchain-ai/langchain/issues/33622) - Was for older versions; v0.0.31 pyproject.toml shows compatible range
- [LangGraphJS Issue #1051: Gemini supervisor errors](https://github.com/langchain-ai/langgraphjs/issues/1051) - JS-specific but illustrates Gemini name/schema issues that also apply to Python
- [GitHub Discussion #19808: Gemini as supervisor](https://github.com/langchain-ai/langchain/discussions/19808) - Gemini consecutive system messages issue

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - `langgraph-supervisor` well-documented, version compatibility verified against installed packages
- Architecture (supervisor pattern): HIGH - Multiple official sources describe the same pattern consistently
- Architecture (Validator as function): MEDIUM - Best practice from multiple sources but no official Dex-specific validation example
- Gemini compatibility: MEDIUM - `include_agent_name="inline"` documented in API reference, but Python+Gemini+supervisor integration not extensively documented (JS had issues that were fixed)
- Multi-turn conversation: HIGH - Checkpointer/thread_id pattern is well-documented with clear API
- Pitfalls: MEDIUM - Assembled from multiple sources; Gemini-specific issues extrapolated from JS to Python

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (30 days -- langgraph ecosystem moves fast; check for new releases)
