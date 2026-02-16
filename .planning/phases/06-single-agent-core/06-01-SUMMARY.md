---
phase: 06-single-agent-core
plan: 01
subsystem: agent
tags: [langgraph, react-agent, mcp-adapters, gemini-flash, system-prompt, anti-hallucination]

# Dependency graph
requires:
  - phase: 05-mcp-data-access-layer
    plan: 01
    provides: FastMCP server with 3 enum-constrained tools (get_spec_category, get_model_overview, list_models)
  - phase: 05-mcp-data-access-layer
    plan: 02
    provides: 219 integration tests validating all MCP tool behavior
provides:
  - Agent package (backend/src/agent/) with create_dex_agent() factory
  - System prompt with anti-hallucination rules, 19-model mapping, not-available handling
  - LangGraph ReAct agent wired to MCP tools via stdio transport
  - 25 unit tests validating prompt content and model configuration
affects:
  - 06-02 (FastAPI endpoint wraps create_dex_agent for HTTP access)
  - 06-03 (Integration tests exercise agent with real LLM + MCP tools)
  - 07 (Multi-agent split refactors this single agent into Concierge/Specialist/Validator)

# Tech tracking
tech-stack:
  added: [langgraph-1.0.8, langchain-mcp-adapters-0.2.1, langchain-google-genai-4.2.0, langchain-core-1.2.13]
  patterns: [react-agent-with-mcp-tools, anti-hallucination-system-prompt, sys-executable-for-subprocess, monkeypatch-env-in-tests]

key-files:
  created:
    - backend/src/agent/__init__.py
    - backend/src/agent/prompts.py
    - backend/src/agent/graph.py
    - backend/tests/test_agent.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "Gemini 2.5 Flash for agent LLM -- already has API key, sub-500ms TTFT, temperature=0 for deterministic"
  - "sys.executable for MCP subprocess command -- works on both Windows (python.exe) and Linux (python3)"
  - "MultiServerMCPClient creates new session per tool call -- no persistent connection management needed"
  - "monkeypatch.setenv for GEMINI_API_KEY in unit tests -- avoids requiring real key for prompt/config tests"

patterns-established:
  - "Anti-hallucination system prompt: NEVER fabricate + ALWAYS use tools + not_available_fields interpretation"
  - "Agent factory pattern: async create_dex_agent() returns (agent, client) tuple"
  - "Manufacturer-model mapping in prompt: prevents agent from guessing wrong manufacturer for a model"

# Metrics
duration: 7min
completed: 2026-02-16
---

# Phase 6 Plan 01: Agent Package and System Prompt Summary

**LangGraph ReAct agent with Gemini 2.5 Flash, anti-hallucination system prompt, and MCP stdio tool connection for 19 spa models across 3 manufacturers**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-16T13:53:30Z
- **Completed:** 2026-02-16T14:00:49Z
- **Tasks:** 2/2 (both auto)
- **Files created:** 4 (3 agent package files + 1 test file)
- **Files modified:** 2 (pyproject.toml + uv.lock)

## Accomplishments

- Installed langgraph 1.0.8, langchain-mcp-adapters 0.2.1, langchain-google-genai 4.2.0 (+ 14 transitive deps)
- Created agent package (backend/src/agent/) with __init__.py exporting create_dex_agent
- Created SYSTEM_PROMPT (2444 chars) with 5 sections: identity, critical rules (5 numbered), not-available handling, out-of-scope handling, response format
- System prompt contains explicit manufacturer-model mapping (Sundance 7, Hot Spring 8, Bullfrog 4) for disambiguation
- Created graph.py with _create_model() (Gemini 2.5 Flash, temp=0, 1024 max tokens), _create_mcp_client() (stdio transport with sys.executable), and async create_dex_agent() factory
- Created 25 unit tests: 19 parametrized model name checks, 4 prompt structure tests, 2 model configuration tests
- All 25 new tests pass, all 219 existing MCP tests unbroken

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create agent package with system prompt** - `e20b8e0` (feat)
2. **Task 2: Create LangGraph ReAct agent with MCP tools and unit tests** - `e06aa03` (feat)

## Files Created/Modified

- `backend/src/agent/__init__.py` - Package init, exports create_dex_agent
- `backend/src/agent/prompts.py` - SYSTEM_PROMPT with anti-hallucination rules and model mapping
- `backend/src/agent/graph.py` - LangGraph ReAct agent: _create_model(), _create_mcp_client(), create_dex_agent()
- `backend/tests/test_agent.py` - 25 unit tests for prompt content and model configuration
- `backend/pyproject.toml` - Added langgraph, langchain-mcp-adapters, langchain-google-genai
- `backend/uv.lock` - Updated lock file

## Verification Results

| Check | Result |
|-------|--------|
| Agent package exists (__init__.py, prompts.py, graph.py) | PASS |
| SYSTEM_PROMPT contains "NEVER fabricate" | PASS |
| SYSTEM_PROMPT contains "ALWAYS use tools" | PASS |
| SYSTEM_PROMPT lists all 3 manufacturers | PASS |
| SYSTEM_PROMPT lists all 19 model names | PASS (parametrized) |
| SYSTEM_PROMPT contains not_available_fields handling | PASS |
| SYSTEM_PROMPT contains out-of-scope/pricing handling | PASS |
| _create_model() returns ChatGoogleGenerativeAI | PASS |
| _create_model() uses gemini-2.5-flash | PASS |
| _create_model() temperature == 0 | PASS |
| Import: from backend.src.agent import create_dex_agent | PASS |
| Existing 219 MCP tests still pass | PASS |

## Decisions Made

- [06-01]: Gemini 2.5 Flash as agent LLM -- project already has GEMINI_API_KEY, sub-500ms TTFT for 3s target, temperature=0 for deterministic spec lookups
- [06-01]: sys.executable for MCP subprocess command instead of hardcoded "python" -- resolves to correct Python binary on both Windows and Linux/Mac
- [06-01]: MultiServerMCPClient creates new stdio session per tool call -- no close() needed, simplifies lifecycle management
- [06-01]: monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key") in model creation tests -- allows unit tests to run without real API key

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MCP subprocess command portability**

- **Found during:** Task 2
- **Issue:** Plan specified hardcoded "python" for MCP subprocess command, which may not resolve correctly on all platforms
- **Fix:** Used `sys.executable` instead, which always resolves to the current Python interpreter
- **Files modified:** backend/src/agent/graph.py
- **Commit:** e06aa03

**2. [Rule 3 - Blocking] Model creation tests fail without API key**

- **Found during:** Task 2
- **Issue:** ChatGoogleGenerativeAI validation requires a non-None google_api_key. Unit tests running without backend/.env fail with ValidationError.
- **Fix:** Added monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key") to both model creation tests
- **Files modified:** backend/tests/test_agent.py
- **Commit:** e06aa03

## Issues Encountered

- ChatGoogleGenerativeAI requires a non-None API key at instantiation time (Pydantic validation), even if you don't plan to make any API calls. This means unit tests that test model configuration must provide a dummy key. Real API calls happen in integration tests (Plan 03).
- The `__init__.py` imports from `graph.py`, so importing the package before graph.py exists causes ImportError. The test file imports `SYSTEM_PROMPT` directly from `prompts.py` to avoid this coupling.

## User Setup Required

None. All dependencies installed via uv. GEMINI_API_KEY in backend/.env is only needed for integration tests (Plan 03), not these unit tests.

## Next Phase Readiness

- Agent package is complete and importable: `from backend.src.agent import create_dex_agent`
- Ready for Plan 02: FastAPI endpoint wrapping the agent for HTTP access
- Ready for Plan 03: Integration tests with real Gemini LLM and MCP tools
- System prompt is designed to minimize tool calls (manufacturer-model mapping in prompt) for the 3-second target

---
*Phase: 06-single-agent-core*
*Completed: 2026-02-16*
