# Project Research Summary

**Project:** Dex -- AI Technical Knowledge Assistant for Spa Parts Lookup
**Domain:** AI-powered structured data retrieval with multi-agent orchestration, ETL pipeline, and React frontend
**Researched:** 2026-02-14
**Confidence:** HIGH

## Executive Summary

Dex is an internal staff tool that answers natural language questions about spa parts with 100% accuracy. The domain demands deterministic data retrieval, not probabilistic search -- a part number off by one digit ships the wrong physical component. The expert approach for this class of problem is to bypass RAG/vector search entirely and use structured JSON data accessed through typed MCP tools, with an LLM layer that handles only intent parsing and response formatting, never data generation. The recommended stack is Python 3.12 with LangGraph for multi-agent orchestration, FastMCP for deterministic data access tools, Claude Sonnet 4.5 for agent reasoning, FastAPI for the backend, and React + Vite for the frontend. All of these technologies are current, well-documented, and version-compatible.

The recommended architecture uses three specialized agents (Concierge for conversation management, Specialist for data queries via MCP, Validator for completeness checks) orchestrated by LangGraph's supervisor-with-handoffs pattern. However, research strongly recommends starting with a single monolithic agent first, proving accuracy, and then splitting into the three-agent design. An offline ETL pipeline using pdfplumber and Claude Haiku extracts specs from manufacturer PDFs into structured JSON, with mandatory human verification before any data enters the production dataset. The POC scope is 19 models across 3 manufacturers (Sundance, Hot Spring, Bullfrog) with 10 spec categories each, yielding 190 data points that all require extraction, verification, and query testing.

The two most dangerous risks are (1) the LLM hallucinating plausible-looking part numbers when structured lookup returns no result, and (2) silent data corruption during PDF extraction that appears correct on spot-check but contains transposed digits or shifted column values. Both risks are mitigated architecturally: the LLM never generates part data (only retrieves it via MCP tools), and every extracted data point undergoes human verification before entering the data store. A third significant risk is premature multi-agent complexity -- the three-agent design should be reached by refactoring a working single agent, not designed from scratch. The JSON schema is the keystone of the entire system: it must be designed before ETL begins and before MCP tools are built, because getting it wrong means re-extracting all data.

## Key Findings

### Recommended Stack

The stack is Python-centric with a React frontend. Every dependency has been version-verified and compatibility-checked. The critical constraint is Python >= 3.12 (required by langchain-mcp-adapters >= 3.11, with 3.12 chosen for performance). FastMCP is pinned to v2 (`fastmcp<3`) because v3 is still release candidate. All package management uses `uv` (10-100x faster than pip, replaces the entire pip/poetry/pyenv toolchain).

**Core technologies:**
- **LangGraph 1.0.8:** Multi-agent orchestration -- production-stable graph-based workflow engine, fastest framework with lowest latency, supports supervisor pattern with conditional routing
- **FastMCP 2.14.5:** MCP server for data access tools -- Pythonic decorator API, automatic schema generation, deterministic tool execution with zero LLM involvement in data layer
- **Claude Sonnet 4.5:** LLM for agent reasoning -- best cost/performance for tool-use agents ($3/$15 MTok), 40% cheaper and 41% faster than Opus with only 3.7% accuracy gap
- **Claude Haiku 4.5:** ETL batch extraction -- cheapest option ($1/$5 MTok, 50% batch discount) for high-volume field extraction tasks
- **FastAPI 0.129.0:** HTTP API backend -- native async, automatic OpenAPI docs, Pydantic integration, SSE streaming
- **Pydantic 2.12.5:** Data validation and JSON schemas -- defines structured spec schemas, 5-50x faster than v1, native JSON Schema export feeds MCP tool definitions
- **React 19 + Vite 7 + TypeScript 5.7+:** Frontend -- project requirement, paired with shadcn/ui and shadcn-chat for chat components
- **pdfplumber 0.11.9:** PDF spec extraction -- best accuracy/flexibility balance for table extraction from varied manufacturer PDF layouts
- **Crawl4AI 0.8.0:** Website scraping -- Playwright-powered async crawler built for LLM workflows, handles JavaScript-heavy manufacturer sites

**Critical version constraints:**
- Pin `fastmcp<3` (v3 RC, not production-ready)
- Python 3.12 minimum (langchain-mcp-adapters requires >= 3.11)
- Node.js 20.19+ or 22.12+ (required by Vite 7.x)

**Explicitly avoided:** RAG/vector databases (similarity search = wrong part numbers), LangChain without LangGraph (legacy patterns), Streamlit (not production-quality), LLM-only PDF extraction (hallucinated specs without deterministic extraction first)

### Expected Features

**Must have (table stakes -- P1):**
- Natural language query input with model/series/manufacturer disambiguation
- Exact part number retrieval via structured MCP tool lookup (NOT vector search)
- Coverage of all 10 spec categories across 19 models
- Source attribution on every response (which PDF, which page)
- "I don't know" honesty when data is missing (never hallucinate)
- Multi-turn conversation context (staff can ask follow-ups without re-specifying model)
- Fast response time (< 3 seconds for structured lookup)
- Clean, scannable response format (part numbers prominent, not buried in prose)
- Three-agent validation pipeline (Concierge + Specialist + Validator)
- ETL pipeline: PDF extraction, structured JSON schema, human verification workflow

**Should have (differentiators -- P2):**
- Compatibility and cross-reference notes ("also fits Optima")
- Guided disambiguation flow (walks staff through clarification)
- Confidence indicators on responses (HIGH/LOW confidence flags)
- Bulk query mode (all pump specs for a series in one table)
- Query analytics and usage pattern tracking
- Data completeness dashboard (190 data points tracked)

**Defer (v2+):**
- Expanded model coverage beyond 19 POC models
- PostgreSQL data storage (JSON works for 19 models)
- Pricing integration (separate system, separate validation)
- ETL diff detection / version tracking
- Voice input / phone integration
- End-customer access (different UX, different trust model)

**Anti-features (explicitly avoid):**
- RAG / vector similarity search (wrong part numbers)
- Free-form AI-generated spec descriptions (hallucination risk)
- Auto-updating from manufacturer websites without human review
- General-purpose chatbot personality (wastes staff time on calls)
- Full-text PDF search fallback (bypasses structured data guarantee)

### Architecture Approach

The system is organized into five clean layers: Presentation (React), API (FastAPI), Orchestration (LangGraph agents), Data Access (FastMCP), and Data (structured JSON). The ETL pipeline operates completely offline and never runs during user queries. The critical architectural boundary is the MCP server: it contains zero LLM logic, executes deterministic queries, and is the sole gateway to ground-truth data. The JSON schema is the keystone -- it must be designed first because both the ETL pipeline (writes to it) and the MCP server (reads from it) depend on it.

**Major components:**
1. **React Frontend** -- Chat panel for Q&A, ETL review dashboard for human verification
2. **FastAPI Server** -- HTTP API with SSE streaming for real-time chat, REST endpoints for ETL review
3. **Concierge Agent** -- Clarifies user intent, manages conversation flow, formats final responses; no data tool access
4. **Specialist (Dex) Agent** -- Executes precise MCP tool calls for structured data queries; the only agent with tool access
5. **Validator Agent** -- Checks response completeness, flags missing fields, verifies all spec values trace to data store; no tool access
6. **FastMCP Server** -- Deterministic data access layer; tools with strongly-typed parameters return exact JSON from verified data files
7. **Structured JSON Data** -- Ground truth organized by manufacturer/series/model; schema enforced by Pydantic
8. **ETL Pipeline** -- Offline batch extraction from PDFs/websites, LLM-assisted transformation, human review queue, validated JSON output

**Key architectural patterns:**
- Supervisor-with-Handoffs for agent orchestration (Concierge decides routing)
- Deterministic Data Access via MCP (zero-hallucination layer)
- SSE Streaming for real-time chat (simpler than WebSockets for unidirectional streaming)
- Offline ETL with Human-in-the-Loop validation (completely separated from runtime)

### Critical Pitfalls

1. **LLM hallucinating part numbers when lookup fails** -- The LLM will confidently generate plausible-looking part numbers when data is missing. Prevention: part numbers must ONLY come from MCP tool responses; implement hard "no data" responses; Validator verifies every value traces to the data store. This must be baked into the architecture from day one.

2. **Silent PDF extraction corruption** -- Extraction appears correct on spot-check but contains transposed digits, shifted column values, or wrong unit attributions. Prevention: 100% human verification of every extracted field against source PDF; build a side-by-side verification UI; manufacturer-specific extraction templates (not one universal parser).

3. **Multi-agent debugging nightmare** -- Three agents passing state create hard-to-diagnose error propagation (Concierge misinterprets model name, Specialist looks up wrong model, Validator confirms wrong data as valid). Prevention: start with single monolithic agent, prove accuracy, then split into three agents; log every hand-off; make agent boundaries deterministic with typed schemas.

4. **"Demo works" false confidence** -- POC appears done after testing 10 queries when the real space is 190+ data points with ambiguous query variations. Prevention: build systematic 19x10 test matrix with automated pass/fail; include adversarial queries (misspelled names, missing context, out-of-scope models); let Adam and Stephen define their top 20 test questions.

5. **Schema does not fit relational complexity** -- Spa parts data has multi-pump positions, series-level shared specs, supersession chains, and conditional compatibility notes that flat JSON loses. Prevention: design schema BEFORE extraction by mapping actual data relationships across all 3 manufacturers; validate against 3 pilot models before bulk extraction.

6. **MCP tool design leaks LLM judgment into retrieval** -- Broad tool interfaces like `search_parts(query: str)` reintroduce hallucination risk. Prevention: use strongly-typed enumerated parameters; enumerate valid manufacturers, model names, and spec categories; return explicit "not found" responses.

## Implications for Roadmap

Based on research, the build order is dictated by data dependencies: nothing works without verified data, and verified data requires a well-designed schema. The suggested structure is 5 phases.

### Phase 1: Data Foundation (Schema + ETL + Sample Data)
**Rationale:** The JSON schema is the keystone that everything else depends on. ETL cannot begin without a target schema. MCP tools cannot be built without knowing the data shape. Agents cannot be tested without real data. This phase must come first.
**Delivers:** Canonical JSON schema for all 10 spec categories; ETL extraction pipeline for PDFs; human verification workflow; 19 verified model data files (190 data points)
**Addresses features:** PDF extraction pipeline (P1), structured JSON schema (P1), human verification workflow (P1), data completeness tracking (P2)
**Avoids pitfalls:** Silent PDF extraction errors (mandatory human verification); schema does not fit relational complexity (design schema first, validate against 3 pilot models); flat JSON loses relational data (explicit relational modeling)
**Stack used:** pdfplumber, Claude Haiku 4.5 (batch extraction), Pydantic (schema definition), Crawl4AI (if needed for web sources)

### Phase 2: Data Access Layer (MCP Server + Tools)
**Rationale:** MCP tools are the sole gateway to ground-truth data and must exist before any agent can answer questions. They are independently testable against the verified data from Phase 1.
**Delivers:** FastMCP server with typed tools (lookup_part, get_specs, list_models, search_by_attribute); deterministic query execution; comprehensive tool tests against all 190 data points
**Addresses features:** Exact part number retrieval (P1), spec category coverage (P1), "I don't know" for missing data (P1)
**Avoids pitfalls:** MCP tool design leaks LLM judgment (strongly-typed parameters, enumerated valid values, explicit not-found responses); LLM hallucination (zero LLM logic in data layer)
**Stack used:** FastMCP 2.14.5, Pydantic, Python 3.12
**Implements architecture:** Deterministic Data Access via MCP pattern

### Phase 3: Agent System (Single Agent First, Then Multi-Agent)
**Rationale:** Research strongly recommends starting with a single monolithic agent that does intent parsing + data lookup + response formatting. Prove accuracy across all 190 data points. Only then split into Concierge/Specialist/Validator with full tracing in place. This avoids the multi-agent debugging nightmare pitfall.
**Delivers:** Working agent system that answers all 10 spec category questions for all 19 models; disambiguation for ambiguous queries; source attribution; conversation context; validated response completeness
**Addresses features:** Natural language query (P1), disambiguation (P1), multi-turn context (P1), source attribution (P1), multi-agent validation pipeline (P1), clean response format (P1), fast response time (P1)
**Avoids pitfalls:** Multi-agent debugging complexity (single agent first, then split); LLM hallucinating part numbers (Validator catches untraced values); "demo works" false confidence (test matrix from Phase 1 data)
**Stack used:** LangGraph 1.0.8, langchain-anthropic, langchain-mcp-adapters, Claude Sonnet 4.5
**Implements architecture:** Supervisor-with-Handoffs pattern, agent graph with typed state

### Phase 4: Frontend + API Integration
**Rationale:** The frontend is the demo surface for Adam and Stephen. It depends on the agent system (Phase 3) being functional. FastAPI wraps the LangGraph graph; React renders the chat interface. Can be partially developed in parallel with Phase 3 using mock API responses.
**Delivers:** React chat interface with SSE streaming; FastAPI endpoints for chat and health; clean scannable response format; ETL review dashboard (for ongoing data verification)
**Addresses features:** React chat interface (P1), fast response display, unsupported query handling (P1)
**Avoids pitfalls:** Overly chatty responses (professional, concise tone); raw JSON output (formatted response templates)
**Stack used:** FastAPI, React 19, Vite 7, TypeScript, shadcn/ui, shadcn-chat, Tailwind CSS, SSE streaming
**Implements architecture:** SSE Streaming pattern, Presentation + API layers

### Phase 5: Deployment + Testing + Hardening
**Rationale:** Deployment is the final gate. Adam and Stephen need remote access. The full 190-cell test matrix must pass. Security (auth, data protection) must be in place. This phase validates the entire system end-to-end.
**Delivers:** Hosted deployment accessible to client; 190-cell automated test suite passing; authentication on all endpoints; error handling for API downtime, MCP crashes, malformed data
**Addresses features:** Hosted deployment (P1), error handling for unsupported queries (P1)
**Avoids pitfalls:** "Demo works" false confidence (full test matrix + adversarial tests); deployment security gaps (auth, data not in public repo, API keys server-side); no regression testing (automated suite runs on every change)
**Stack used:** Railway or Render, Docker, pytest, pytest-asyncio

### Phase Ordering Rationale

- **Data before tools before agents:** The dependency graph is strict. MCP tools read from verified JSON data. Agents call MCP tools. The frontend calls agents. Inverting this order means building on assumptions rather than verified foundations.
- **Schema before extraction:** Getting the schema wrong means re-extracting all 190 data points. Three pilot models (one per manufacturer) validate the schema before bulk extraction.
- **Single agent before multi-agent:** Research identifies multi-agent debugging as a critical pitfall. The single-agent approach proves core accuracy first, then the refactor into three agents is a controlled architectural improvement, not a leap of faith.
- **Frontend partially parallel:** React development can begin in Phase 3 with mock API responses, but integration testing waits for Phase 4.
- **ETL review UI in Phase 4:** The verification workflow in Phase 1 can be manual (spreadsheet review). The review dashboard is built when the React patterns are established.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (ETL):** PDF extraction is the highest-complexity work. Each manufacturer has different document formats. Needs specific investigation of Sundance, Hot Spring, and Bullfrog PDF layouts before committing to extraction approach. Research-phase recommended.
- **Phase 3 (Agents):** The single-to-multi-agent refactoring path needs careful planning. LangGraph supervisor pattern details, handoff mechanics, and state schema design benefit from deeper research. Research-phase recommended.

Phases with standard patterns (skip research-phase):
- **Phase 2 (MCP Server):** FastMCP tool definitions are well-documented with decorator patterns. The tool interface is straightforward once the schema exists.
- **Phase 4 (Frontend + API):** React + FastAPI + SSE is a well-established pattern with multiple reference implementations. shadcn/ui provides ready-made components.
- **Phase 5 (Deployment):** Standard deployment patterns. Railway/Render have documented deployment flows for FastAPI + React.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified on PyPI/npm on 2026-02-14. Compatibility matrix checked. Pricing verified against Anthropic docs. |
| Features | HIGH (core) / MEDIUM (differentiators) | Table stakes well-defined by domain analysis and competitor comparison. Differentiator priority depends on client feedback after POC. |
| Architecture | HIGH (core patterns) / MEDIUM (integration details) | Supervisor-with-handoffs and MCP patterns well-documented in official repos. SSE streaming has multiple reference implementations. Specific LangGraph + FastMCP + FastAPI integration is less documented. |
| Pitfalls | HIGH | Multiple verified sources per pitfall. Domain-specific analysis (hallucinated part numbers, PDF extraction corruption) grounded in concrete failure scenarios. Recovery strategies included. |

**Overall confidence:** HIGH

### Gaps to Address

- **Manufacturer PDF format analysis:** No actual Sundance, Hot Spring, or Bullfrog PDFs have been analyzed yet. The extraction approach is based on general PDF extraction research. Validate with real documents in Phase 1 before committing to extraction strategy.
- **LangGraph + FastMCP in-process integration:** Most documentation shows MCP servers as separate processes. Running FastMCP in-process within the same Python application as LangGraph agents (via stdio transport) has fewer documented examples. May need experimentation in Phase 2.
- **Conversation state management under concurrent users:** POC scale (1-5 users) should not hit this, but the session isolation strategy needs explicit design if multiple staff use the system simultaneously.
- **Exact response latency budget:** Three sequential LLM calls (Concierge + Specialist + Validator) at ~1-2s each means 4-8s total, which exceeds the < 3s target. May need to use a faster model for Validator (Haiku) or run Validator in parallel where possible. Needs validation in Phase 3.
- **POC cost projection validation:** Estimated under $5 for 1,000 test queries at Sonnet pricing. Verify this holds with actual conversation lengths once agents are built.

## Sources

### Primary (HIGH confidence)
- [PyPI package versions](https://pypi.org/) -- all package versions verified 2026-02-14
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) -- model pricing verified 2026-02-14
- [LangGraph Official](https://www.langchain.com/langgraph) -- orchestration framework
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- protocol standard
- [FastMCP Documentation](https://gofastmcp.com/updates) -- MCP server library
- [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters) -- LangGraph + MCP integration
- [langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py) -- supervisor pattern
- [LangChain Blog: Multi-Agent Architecture](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/) -- architecture patterns

### Secondary (MEDIUM confidence)
- [Latenode: LangGraph Multi-Agent Guide](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/) -- orchestration patterns (blog, verified against multiple sources)
- [Unstract: LLMs for PDF Extraction](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/) -- ETL approach comparison
- [Parseur: HITL Best Practices](https://parseur.com/blog/hitl-best-practices) -- human verification workflow design
- [Softgrade: SSE with FastAPI + React + LangGraph](https://www.softgrade.org/sse-with-fastapi-react-langgraph/) -- streaming architecture
- [Circuitry.AI Parts Aidvisor](https://circuitry.ai/intelligent-parts-lookup-with-parts-aidvisor) -- AI parts lookup features
- [Squirro: Deterministic AI Accuracy](https://squirro.com/squirro-blog/graphrag-deterministic-ai-accuracy) -- structured vs vector retrieval
- [Smile.eu: Retrieval for Structured Data](https://smile.eu/en/publications-and-events/retrieval-structured-data-precision-first-alternative-vector-only-rag-excel) -- why vector search fails for exact matches

### Tertiary (needs validation)
- [Gartner: 30% of GenAI projects abandoned after POC](https://www.gartner.com/en/newsroom/press-releases/2024-07-29-gartner-predicts-30-percent-of-generative-ai-projects-will-be-abandoned-after-proof-of-concept-by-end-of-2025) -- industry context
- [CIO: 88% of AI pilots fail to reach production](https://www.cio.com/article/3850763/88-of-ai-pilots-fail-to-reach-production-but-thats-not-all-on-it.html) -- industry context

---
*Research completed: 2026-02-14*
*Ready for roadmap: yes*
