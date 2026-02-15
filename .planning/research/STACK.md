# Stack Research

**Domain:** AI Technical Knowledge Assistant (Structured Data Lookup, Multi-Agent, ETL)
**Researched:** 2026-02-14
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | 3.12 | Backend runtime | Sweet spot of compatibility: all key dependencies (LangGraph, FastMCP, Crawl4AI) require >=3.10. 3.12 offers performance improvements over 3.11 while avoiding 3.13 edge cases. LangGraph MCP adapters require >=3.11. |
| **LangGraph** | 1.0.8 | Multi-agent orchestration | Production-stable graph-based workflow engine. The Concierge/Specialist/Validator architecture maps directly to LangGraph's supervisor pattern with conditional routing. Fastest framework with lowest latency vs CrewAI, AutoGen, OpenAI Agents SDK. LangChain team recommends it for all new agent implementations. |
| **FastMCP** | 2.14.5 | MCP server for data access tools | High-level Pythonic API for building MCP servers. Provides tool decorators, automatic schema generation, and testing utilities. Pinned to v2 (`fastmcp<3`) because v3.0 is still RC. Eliminates boilerplate of raw MCP SDK. |
| **MCP Python SDK** | 1.26.0 | MCP protocol foundation | Official Anthropic SDK underpinning FastMCP. Implements full MCP spec (2025-11-25). Used indirectly via FastMCP but needed as a dependency. |
| **Claude Sonnet 4.5** | claude-sonnet-4-5-20250929 | LLM for agent reasoning | Best cost/performance ratio for tool-use agents: $3/$15 per MTok. Only 3.7% behind Opus on SWE-bench but 40% cheaper and 41% faster. Optimized for agentic behavior with reliable tool-use patterns. For a POC where latency and cost matter, this is the right model. Upgrade to Opus 4.6 only if accuracy issues arise. |
| **FastAPI** | 0.129.0 | HTTP API backend | Industry standard Python API framework. Native async, automatic OpenAPI docs, Pydantic integration, WebSocket support for streaming. Serves the React frontend and hosts agent endpoints. |
| **Pydantic** | 2.12.5 | Data validation & JSON schemas | Rust-powered validation core (5-50x faster than v1). Defines the structured spec schemas (pumps, jets, filters, etc.). Native JSON Schema export feeds MCP tool definitions. Every data model in the system passes through Pydantic. |
| **React** | 19.x | Frontend UI framework | Project requirement. Paired with Vite for fast dev. React 19 is stable with concurrent features. |
| **Vite** | 7.x | Frontend build tool | 40x faster builds than CRA. Hot Module Replacement for rapid iteration. Standard for React projects in 2026. `npm create vite@latest -- --template react-ts` to scaffold. |
| **TypeScript** | 5.7+ | Frontend type safety | Non-negotiable for any production React project. Catches data shape errors at compile time, critical when displaying part numbers where a typo means wrong parts. |

### ETL Pipeline Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pdfplumber** | 0.11.9 | PDF spec sheet extraction | Best balance of accuracy and flexibility for table extraction from manufacturer PDFs. Handles complex tables, nested structures, multi-page tables. More control than Camelot, more reliable than Tabula for varied PDF layouts. |
| **Crawl4AI** | 0.8.0 | Website spec scraping | Playwright-powered async crawler built for LLM workflows. Handles JavaScript-heavy manufacturer sites, auto-converts to structured Markdown. Supports LLM-driven extraction with schema generation. Replaces manual BeautifulSoup/Scrapy scripts. |
| **Claude Haiku 4.5** | claude-haiku-4-5-20250929 | AI-assisted extraction | $1/$5 per MTok -- cheapest option for batch extraction tasks. Good enough for identifying spec fields in extracted text. ETL is batch work where cost matters more than reasoning depth. Use Batch API for additional 50% discount. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **langchain-anthropic** | 1.3.3 | Claude + LangGraph integration | Wraps Claude models as LangGraph-compatible chat models via `ChatAnthropic`. Required bridge between LangGraph and Claude API. |
| **langchain-mcp-adapters** | 0.2.1 | MCP tools in LangGraph | Converts MCP tools into LangChain-compatible tools for LangGraph agents. Handles transport (stdio/HTTP). Critical for connecting Specialist agent to FastMCP server. |
| **langgraph-supervisor** | 0.0.31 | Prebuilt supervisor pattern | Optional shortcut for the Concierge supervisor pattern. Provides `create_supervisor` with handoff tools. Consider building custom supervisor if more control needed. |
| **anthropic** | 0.79.0 | Direct Claude API access | Used by langchain-anthropic under the hood. Also useful for direct API calls in ETL pipeline where LangGraph overhead is unnecessary. |
| **uvicorn** | latest | ASGI server | Production server for FastAPI. Use `uvicorn[standard]` for libuv event loop. |
| **shadcn/ui** | latest | React UI components | Copy-paste component library with Tailwind CSS. Provides Chat, Input, Button, Card components. Not an npm dependency -- components are copied into your project. |
| **shadcn-chat** | latest | Chat-specific UI components | Extends shadcn/ui with ChatBubble, ChatInput, expandable chat window. Purpose-built for AI chat interfaces. |
| **Tailwind CSS** | 4.x | Utility-first CSS | Required by shadcn/ui. Rapid styling without custom CSS. Industry standard for React projects in 2026. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Python package manager | 10-100x faster than pip. Replaces pip, pip-tools, pipx, poetry, pyenv, virtualenv in one tool. Written in Rust by Astral (ruff team). Use for all dependency management. |
| **ruff** | Python linting & formatting | Replaces flake8, black, isort. Single tool, Rust-powered, millisecond execution. Configure in `pyproject.toml`. |
| **pytest** | Python testing | Industry standard. Use pytest-asyncio for async agent tests, pytest-cov for coverage. |
| **ESLint + Prettier** | Frontend linting & formatting | Standard for TypeScript/React. Configure via eslint.config.js (flat config). |

## Installation

### Backend (Python)

```bash
# Initialize project with uv
uv init dex-backend
cd dex-backend

# Core agent framework
uv add langgraph langchain-anthropic langchain-mcp-adapters anthropic

# MCP server
uv add "fastmcp<3"

# API framework
uv add fastapi "uvicorn[standard]" pydantic

# ETL pipeline
uv add pdfplumber crawl4ai

# Optional: supervisor prebuilt
uv add langgraph-supervisor

# Dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov ruff
```

### Frontend (React/TypeScript)

```bash
# Scaffold project
npm create vite@latest dex-frontend -- --template react-ts
cd dex-frontend
npm install

# UI components (shadcn/ui setup)
npx shadcn@latest init
npx shadcn@latest add button input card scroll-area avatar

# Chat components
npx shadcn-chat@latest add chat-bubble chat-input

# HTTP client
npm install axios

# Dev dependencies
npm install -D @types/node
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **LangGraph** | **CrewAI** | If you want faster prototyping with role-based agents and less graph complexity. CrewAI is simpler but less flexible for conditional routing and human-in-the-loop patterns. Not recommended here because Dex needs precise control over agent handoffs and validation flow. |
| **LangGraph** | **OpenAI Agents SDK** | If you are locked into OpenAI models. Good for simple tool-calling agents. Lacks LangGraph's parallel execution, state management, and graph visualization. Not recommended because Dex uses Claude. |
| **LangGraph** | **Anthropic Agent SDK** | If you want minimal dependencies with direct Anthropic integration. Very new (early 2026). Less mature ecosystem, fewer patterns documented. Consider for future migration if LangGraph adds unnecessary overhead. |
| **FastMCP** | **Raw MCP Python SDK** | If you need protocol-level control or FastMCP abstractions don't fit. More boilerplate but more flexible. Not recommended because FastMCP's decorator pattern (`@mcp.tool()`) is perfect for defining spec lookup tools. |
| **Claude Sonnet 4.5** | **Claude Opus 4.6** | If Sonnet accuracy proves insufficient for complex queries. Opus at $5/$25 per MTok is only 67% more expensive than Sonnet. Switch per-agent: use Opus for Concierge reasoning, Sonnet for Specialist tool calls. |
| **Claude Sonnet 4.5** | **GPT-4o / GPT-5** | If you need OpenAI ecosystem compatibility. Not recommended because MCP is Anthropic-native, Claude has superior tool-use patterns, and the project charter specifies Claude. |
| **pdfplumber** | **Camelot** | If PDFs have simple, well-defined table borders. Camelot is faster for clean tables but struggles with complex layouts common in manufacturer spec sheets. |
| **pdfplumber** | **PyMuPDF (fitz)** | If you need raw speed for high-volume PDF processing. Faster extraction but requires building custom table detection logic. Consider as supplementary for text-only extraction. |
| **Crawl4AI** | **Scrapy + Playwright** | If manufacturer sites require complex multi-page crawl patterns with IP rotation. Scrapy is more mature for large-scale crawling. Overkill for 3 manufacturer websites. |
| **Crawl4AI** | **Firecrawl** | If you want a managed API instead of self-hosted. Firecrawl is cloud-based, handles anti-bot measures. Adds external dependency and cost. Not needed for 3 manufacturer sites. |
| **FastAPI** | **Flask** | Never for this project. Flask lacks native async, no automatic OpenAPI, no Pydantic integration. Legacy choice. |
| **Vite** | **Next.js** | If you need SSR/SSG for SEO. Internal staff tool needs neither. Next.js adds complexity (server components, routing conventions) without benefit for a single-page chat interface. |
| **uv** | **Poetry** | If your team already uses Poetry and migration cost is high. Poetry is mature and feature-complete but 10-100x slower. For a greenfield project, uv is the right choice. |
| **Railway** | **Render** | If you want managed Postgres included (future scope). Render has built-in database services. Railway is faster to deploy for POC with simpler billing. Both work well. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **RAG / Vector databases** | Project requirement: 100% accuracy. Vector similarity search returns "close enough" results, which means wrong part numbers. A part number one digit off ships the wrong physical part. Structured lookup via MCP tools guarantees exact matches. | MCP tools querying structured JSON/Pydantic models |
| **LangChain (without LangGraph)** | LangChain's chain/agent abstractions are legacy. LangChain team themselves recommends LangGraph for all new agent work. Using LangChain alone means fighting deprecated patterns. | LangGraph (uses langchain-core under the hood) |
| **Create React App (CRA)** | Deprecated, unmaintained. 40x slower builds than Vite. React team no longer recommends it. | Vite with react-ts template |
| **pip + requirements.txt** | Slow, no lock file, no virtual env management, no Python version management. Manual dependency resolution. | uv with pyproject.toml |
| **Pipenv** | Slow, abandoned by maintainer for long periods, complex lock resolution. Neither modern nor fast. | uv |
| **unittest** | Verbose, class-based, limited fixture system. pytest is the standard and runs unittest tests anyway. | pytest |
| **BeautifulSoup for ETL** | Manual HTML parsing without JavaScript rendering. Manufacturer sites use dynamic loading. Requires separate Playwright setup. | Crawl4AI (built on Playwright, outputs structured data) |
| **OpenAI models** | MCP is Anthropic-native. Claude has best-in-class tool use for agentic workflows. Project charter specifies Claude. | Claude Sonnet 4.5 / Opus 4.6 |
| **Streamlit for frontend** | Quick for demos but not production-quality. No component control, no TypeScript, poor UX for chat interfaces. Client (Adam/Stephen) needs to test a real product feel. | React + shadcn/ui + Vite |
| **FastMCP v3** | Still in RC (3.0.0rc2 as of 2026-02-14). Breaking API changes from v2. Not production-ready. | FastMCP 2.14.5 (`fastmcp<3`) |
| **LLM-only PDF extraction** | Sending raw PDFs to LLMs without structured extraction first leads to hallucinated specs. LLMs may "fill in" missing data. ETL must use deterministic extraction first, then LLM for field mapping, then human verification. | pdfplumber (extract) + Claude Haiku (map fields) + human review |

## Stack Patterns by Variant

**If accuracy issues arise with Sonnet 4.5:**
- Upgrade Concierge agent to Claude Opus 4.6 ($5/$25 MTok)
- Keep Specialist on Sonnet (tool calls are deterministic lookups, model quality matters less)
- Net cost increase is modest since Concierge does reasoning, Specialist does retrieval

**If PDF extraction is unreliable:**
- Add PyMuPDF as fallback extractor alongside pdfplumber
- Use ensemble approach: extract with both, compare results, flag discrepancies
- LLMWhisperer API as cloud fallback for particularly difficult PDFs

**If manufacturer sites block scraping:**
- Switch from Crawl4AI to manual data entry for 3 sites (POC scope is small)
- Or use Firecrawl managed API which handles anti-bot measures
- 19 models across 3 manufacturers is manageable by hand if automated scraping fails

**If deployment needs to scale beyond POC:**
- Move from local JSON to PostgreSQL with pgvector (for future semantic features)
- Add Redis for caching frequent spec lookups
- Move from Railway to AWS/GCP with proper infrastructure

**If React chat UX needs to be more sophisticated:**
- Consider assistant-ui library (Radix-style composable primitives)
- Or Vercel AI SDK with AI Elements for streaming-first components
- shadcn/ui chat components should be sufficient for POC

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| langgraph@1.0.8 | langchain-anthropic@1.3.3 | Both require Python >=3.10. LangGraph depends on langchain-core which langchain-anthropic also uses. |
| langchain-mcp-adapters@0.2.1 | langgraph@1.0.8, mcp@1.26.0 | Adapters bridge MCP tools into LangGraph. Requires Python >=3.11 (stricter than LangGraph's >=3.10). This is why Python 3.12 is recommended. |
| fastmcp@2.14.5 | mcp@1.26.0 | FastMCP wraps the MCP SDK. Pin `fastmcp<3` to avoid breaking changes. |
| pydantic@2.12.5 | fastapi@0.129.0 | FastAPI is built on Pydantic v2. Both use the same model definitions. |
| anthropic@0.79.0 | langchain-anthropic@1.3.3 | langchain-anthropic wraps the anthropic SDK. Version alignment is handled by pip/uv resolution. |
| crawl4ai@0.8.0 | Python 3.12 | Installs Playwright automatically during setup. Requires separate `playwright install` for browsers. |
| vite@7.x | React 19, TypeScript 5.7+ | Requires Node.js 20.19+ or 22.12+. Use `react-ts` template for TypeScript support. |

## Model Pricing Quick Reference

For budgeting the POC:

| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| Claude Sonnet 4.5 | $3/MTok | $15/MTok | Concierge + Specialist agents (primary) |
| Claude Opus 4.6 | $5/MTok | $25/MTok | Upgrade path if Sonnet accuracy insufficient |
| Claude Haiku 4.5 | $1/MTok | $5/MTok | ETL field extraction (batch, high volume) |
| Haiku 4.5 Batch | $0.50/MTok | $2.50/MTok | Bulk ETL processing with 50% batch discount |

**POC cost estimate:** 19 models x 10 spec categories = 190 spec lookups. At ~3,700 tokens per conversation (Anthropic's example), Sonnet costs ~$0.003 per query. Even at 1,000 test queries during development, total agent API cost is under $5.

## Sources

- [PyPI: langgraph 1.0.8](https://pypi.org/project/langgraph/) -- version verified 2026-02-14
- [PyPI: fastmcp 2.14.5](https://pypi.org/project/fastmcp/) -- version verified 2026-02-14
- [PyPI: mcp 1.26.0](https://pypi.org/project/mcp/) -- version verified 2026-02-14
- [PyPI: anthropic 0.79.0](https://pypi.org/project/anthropic/) -- version verified 2026-02-14
- [PyPI: fastapi 0.129.0](https://pypi.org/project/fastapi/) -- version verified 2026-02-14
- [PyPI: pydantic 2.12.5](https://pypi.org/project/pydantic/) -- version verified 2026-02-14
- [PyPI: pdfplumber 0.11.9](https://pypi.org/project/pdfplumber/) -- version verified 2026-02-14
- [PyPI: crawl4ai 0.8.0](https://pypi.org/project/Crawl4AI/) -- version verified 2026-02-14
- [PyPI: langchain-anthropic 1.3.3](https://pypi.org/project/langchain-anthropic/) -- version verified 2026-02-14
- [PyPI: langchain-mcp-adapters 0.2.1](https://pypi.org/project/langchain-mcp-adapters/) -- version verified 2026-02-14
- [PyPI: langgraph-supervisor 0.0.31](https://pypi.org/project/langgraph-supervisor/) -- version verified 2026-02-14
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) -- pricing verified 2026-02-14
- [FastMCP Updates](https://gofastmcp.com/updates) -- v3 RC status confirmed
- [LangChain MCP Adapters GitHub](https://github.com/langchain-ai/langchain-mcp-adapters) -- integration patterns
- [Vite Getting Started](https://vite.dev/guide/) -- v7.x confirmed current
- [shadcn/ui](https://ui.shadcn.com/) -- chat component patterns
- [uv documentation](https://docs.astral.sh/uv/) -- package manager recommendation

---
*Stack research for: Dex -- AI Technical Knowledge Assistant*
*Researched: 2026-02-14*
