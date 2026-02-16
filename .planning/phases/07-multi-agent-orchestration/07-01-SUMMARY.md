---
phase: 07-multi-agent-orchestration
plan: 01
subsystem: agent
tags: [langgraph-supervisor, multi-agent, concierge, specialist, validator, checkpointer]

dependency_graph:
  requires: [06-01, 06-02, 06-03]
  provides: [multi-agent-supervisor-graph, deterministic-validator, per-agent-prompts, shared-config]
  affects: [07-02, 08]

tech_stack:
  added: [langgraph-supervisor-0.0.31]
  patterns: [supervisor-routing, inline-agent-names, deterministic-validation, InMemorySaver-checkpointer]

key_files:
  created:
    - backend/src/agent/config.py
    - backend/src/agent/validator.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/src/agent/graph.py
    - backend/src/agent/prompts.py
    - backend/src/agent/__init__.py
    - backend/tests/test_agent.py

decisions:
  - id: "07-01-01"
    decision: "Concierge gets list_models tool (not empty tools list) to avoid Gemini empty schema errors"
    rationale: "Gemini rejects empty function_declarations; list_models is useful for disambiguation anyway"
  - id: "07-01-02"
    decision: "Validator is pure Python function called by API layer, NOT a LangGraph node"
    rationale: "Avoids third LLM call, keeps validation deterministic and predictable"
  - id: "07-01-03"
    decision: "include_agent_name='inline' on create_supervisor for Gemini compatibility"
    rationale: "Gemini does not support the name attribute on AI messages; inline embeds names in XML tags"
  - id: "07-01-04"
    decision: "output_mode='last_message' on create_supervisor to keep history lean"
    rationale: "Prevents message history explosion in multi-turn; only final answer appended to thread"
  - id: "07-01-05"
    decision: "create_dex_agent kept as deprecated wrapper for backward compatibility"
    rationale: "Allows gradual migration of callers (app.py) in Plan 07-02"

metrics:
  duration: 9 min
  completed: 2026-02-16
---

# Phase 7 Plan 1: Multi-Agent Supervisor Architecture Summary

**One-liner:** langgraph-supervisor multi-agent graph with Concierge (list_models tool), Specialist (all MCP tools), deterministic Validator, and InMemorySaver checkpointer.

## What Was Done

### Task 1: Install langgraph-supervisor and create agent config, prompts, and validator
- Added `langgraph-supervisor>=0.0.31` to dependencies; `uv sync` installed cleanly
- Created `config.py` with `create_model()` and `create_mcp_client()` factories extracted from graph.py
- Rewrote `prompts.py` with 3 role-specific prompts:
  - **SUPERVISOR_PROMPT**: Routes to concierge (ambiguous) or specialist (clear queries)
  - **CONCIERGE_PROMPT**: Clarification only, lists all 19 models, NEVER answers specs
  - **SPECIALIST_PROMPT**: Full anti-hallucination rules, tool instructions, not-available handling
- Created `validator.py` with `validate_response()` -- pure Python function (no LLM imports) that checks: (a) tool calls exist, (b) answer length >20 chars, (c) no standalone "null" in response

### Task 2: Rewrite graph.py as multi-agent supervisor and update unit tests
- Rewrote `graph.py` with `create_multi_agent()` factory:
  - Creates Concierge agent with `list_models` tool only
  - Creates Specialist agent with all 3 MCP tools
  - Creates supervisor via `create_supervisor()` with `include_agent_name="inline"` and `output_mode="last_message"`
  - Compiles with `InMemorySaver` checkpointer for multi-turn conversation
  - Returns `(compiled_graph, mcp_client_or_none)` tuple
- Kept `create_dex_agent()` as deprecated backward-compat wrapper
- Updated `__init__.py` to export `create_multi_agent`, `create_dex_agent`, and `validate_response`
- Rewrote `test_agent.py` with 62 unit tests:
  - 24 specialist prompt tests (anti-hallucination, 19 models, tools, scope, not-available)
  - 2 supervisor prompt tests (routing, specialist preference)
  - 23 concierge prompt tests (never answers, never fabricates, 19 models, list_models)
  - 7 validator tests (no tools, short answer, null, clean, empty, missing key, false positive)
  - 2 model creation tests (Gemini instance, temperature=0)
  - 4 graph structure tests (no validator import, exports verification)

## Verification Results

- `uv sync` installs langgraph-supervisor without conflicts
- All imports succeed: `create_multi_agent`, `validate_response`, config factories, prompts
- 62/62 agent unit tests pass
- 291/291 total non-integration tests pass (zero regressions from Phase 6's 269)

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Concierge gets list_models tool** -- Gemini errors on empty function declarations. The list_models tool is both safe and useful for disambiguation.
2. **Validator is API-layer function** -- NOT a LangGraph node. Called by app.py after ainvoke(), keeping the graph pure LangGraph and validation pure Python.
3. **include_agent_name="inline"** -- Required for Gemini compatibility since Gemini does not support the `name` attribute on AI messages.
4. **output_mode="last_message"** -- Keeps conversation history lean; only the final answer is appended to the thread.
5. **Deprecated wrapper kept** -- `create_dex_agent()` wraps `create_multi_agent()` for backward compatibility during migration.

## Next Phase Readiness

- **07-02 ready**: The multi-agent graph is built and testable. Plan 07-02 wires `create_multi_agent` into `app.py`, adds `conversation_id` to the API, and integrates `validate_response` into the `/query` endpoint.
- **Integration tests**: The existing `test_agent_integration.py` (15 tests) still references `create_dex_agent` which now wraps `create_multi_agent`. These tests will be updated in 07-02.
- **No blockers**: All imports clean, all tests pass, checkpointer ready for multi-turn.
