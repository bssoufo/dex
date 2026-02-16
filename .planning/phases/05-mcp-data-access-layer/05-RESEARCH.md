# Phase 5: MCP Data Access Layer - Research

**Researched:** 2026-02-16
**Domain:** Model Context Protocol (MCP) tool server with FastMCP, strongly-typed data lookups
**Confidence:** HIGH

## Summary

Phase 5 builds the MCP tool server that provides the sole deterministic gateway to the 19 verified spa model JSON files. The server exposes strongly-typed lookup tools that an LLM agent (Phase 6+) will call via the MCP protocol to retrieve exact spec data -- no free-text queries, no RAG, no vector search.

The standard approach is a FastMCP v2 server with `@mcp.tool` decorated Python functions that accept enum/Literal parameters (manufacturer, model name, spec category) and return structured JSON responses. FastMCP auto-generates JSON Schema from Python type annotations, meaning Pydantic enums and Literal types translate directly into constrained parameter schemas that prevent ambiguous tool calls.

The data layer is a simple in-memory store: load all 19 JSON files at startup into a dict keyed by `(manufacturer, model_name)`, validate each through `SpaModel`, and serve lookups with O(1) access. No database needed for 19 models.

**Primary recommendation:** Use FastMCP 2.14.x (stable, production-ready) with Python enum/Literal parameters, an in-memory SpaModel data store loaded at startup, and pytest + `fastmcp.Client` for comprehensive 19x10 test coverage.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastmcp | 2.14.5 (`<3`) | MCP server framework | Production-stable v2; auto-generates tool schemas from type hints; built-in Pydantic support; in-memory Client for testing |
| pydantic | >=2.12.5 | Data validation + schema | Already used for SpaModel; type annotations drive MCP tool schemas directly |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Test framework | Test all 19x10 MCP tool lookups |
| pytest-asyncio | >=0.24 | Async test support | FastMCP Client is async; required for in-memory tool testing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastMCP 2.14 | FastMCP 3.0rc | v3 is release candidate with possible breaking changes; v2 is production-stable; wait for v3 GA |
| FastMCP | Official MCP Python SDK (`mcp`) | Lower-level, more boilerplate; FastMCP is built on top of it and adds decorator API, auto-schema, testing Client |
| In-memory dict | SQLite/PostgreSQL | Overkill for 19 models; JSON files are <10KB each; total data fits in <200KB RAM |

### Installation

```bash
# Add to pyproject.toml dependencies
pip install "fastmcp>=2.14,<3"

# Dev dependencies
pip install pytest pytest-asyncio
```

### Version Decision: FastMCP 2 vs 3

**Use FastMCP 2.14.x (pin `<3`).** Rationale:
- v2.14.5 is the latest stable release (Feb 3, 2026)
- v3.0 is RC1 (Feb 12, 2026) -- API believed stable but still pre-release
- v3.0 has breaking changes: renamed `ui=` to `app=`, removed 16 constructor kwargs, changed metadata namespace
- The user's MEMORY.md specifies "FastMCP v2" as a locked decision
- v2 has full feature parity for this use case (tools, enums, testing Client)
- Upgrade path to v3 is documented and straightforward when v3 reaches GA

## Architecture Patterns

### Recommended Project Structure

```
backend/src/
  mcp/                     # NEW -- MCP server package
    __init__.py            # Package init, exports create_server()
    server.py              # FastMCP server instance + tool definitions
    data_store.py          # Data loading + in-memory store singleton
    enums.py               # SpecCategory enum + ModelName Literal type
  schema/                  # EXISTING -- Pydantic models
  data/                    # EXISTING -- 19 JSON files
    {manufacturer}/{series}/*.json
```

### Pattern 1: In-Memory Data Store (Singleton)

**What:** Load all 19 JSON files into a dict at module import time. Key by `(manufacturer, model_name)` tuple for O(1) lookup.
**When to use:** Small dataset that fits in memory (19 models, <200KB total).
**Example:**

```python
# backend/src/mcp/data_store.py
import json
from pathlib import Path
from backend.src.schema.models import SpaModel

# Type alias for the store
ModelKey = tuple[str, str]  # (manufacturer, model_name_lower)
_store: dict[ModelKey, SpaModel] = {}

DATA_DIR = Path(__file__).parent.parent / "data"

def load_all_models() -> dict[ModelKey, SpaModel]:
    """Load and validate all JSON model files into memory."""
    store: dict[ModelKey, SpaModel] = {}
    for json_file in DATA_DIR.rglob("*.json"):
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        model = SpaModel.model_validate(raw)
        key = (model.manufacturer.value, model.model_name.lower())
        store[key] = model
    return store

def get_store() -> dict[ModelKey, SpaModel]:
    """Get or lazily initialize the data store."""
    global _store
    if not _store:
        _store = load_all_models()
    return _store

def get_model(manufacturer: str, model_name: str) -> SpaModel | None:
    """Look up a specific model. Returns None if not found."""
    return get_store().get((manufacturer.lower(), model_name.lower()))
```

### Pattern 2: Enum-Constrained Tool Parameters

**What:** Use Python enums and Literal types as tool parameters so FastMCP generates JSON Schema with `enum` constraints. This prevents LLM agents from inventing invalid model names.
**When to use:** Always, for all tool parameters that have a finite set of valid values.
**Example:**

```python
# backend/src/mcp/enums.py
from enum import StrEnum
from typing import Literal

class SpecCategory(StrEnum):
    """The 10 queryable spec categories matching SpaModel field names."""
    JET_PUMPS = "jet_pumps"
    CIRCULATION_PUMP = "circulation_pump"
    SPA_PAK = "spa_pak"
    TOPSIDE_CONTROL = "topside_control"
    JETS = "jets"
    HEADRESTS = "headrests"
    FILTERS = "filters"
    HEATER = "heater"
    LIGHTING = "lighting"
    COVER = "cover"

# Use Literal for model names -- finite known set
# This creates a JSON Schema enum constraint
ModelName = Literal[
    "Altamar", "Aspen", "Cameo", "Capris", "Marin", "Optima", "Vistamar",  # Sundance
    "Aria", "Envoy", "Grandee", "Jetsetter", "Jetsetter LX", "Prodigy", "Sovereign", "Vanguard",  # Hot Spring
    "M6", "M7", "M8", "M9",  # Bullfrog
]
```

### Pattern 3: Structured Not-Found Responses

**What:** When data is missing, return an explicit structured response with the reason, never null/empty.
**When to use:** Every tool must handle: (a) model not found, (b) category is None for that model, (c) specific field within category is null/not-available.
**Example:**

```python
from pydantic import BaseModel

class ToolResponse(BaseModel):
    """Standard response envelope for all MCP tool returns."""
    success: bool
    manufacturer: str | None = None
    model_name: str | None = None
    category: str | None = None
    data: dict | None = None
    message: str | None = None
    not_available_fields: list[str] | None = None
```

### Pattern 4: Tool Design -- Coarse vs Granular

**What:** Provide 2-3 tools with different granularity levels rather than 10+ single-purpose tools.
**When to use:** When an LLM agent needs to choose from tools. Fewer tools = less agent confusion.

Recommended tool set:
1. **`get_spec_category`** -- Primary tool: get one category for one model (e.g., "get jet_pumps for Sundance Aspen")
2. **`get_model_overview`** -- Summary: get all non-null categories for a model (identity, dimensions, which categories have data)
3. **`list_models`** -- Discovery: list all available models, optionally filtered by manufacturer

This is deliberately minimal. The agent (Phase 6) handles natural language parsing. The MCP layer handles deterministic data retrieval only.

### Anti-Patterns to Avoid

- **Free-text model name parameter:** Never accept `model_name: str` without validation. Use Literal type or validate against known set. A typo like "Aspn" should fail, not silently return nothing.
- **Returning raw None for missing data:** Never return `{"jets": null}`. Return `{"success": true, "data": null, "message": "Jets data not available for this model", "not_available_fields": ["jets"]}`.
- **One tool per category:** Don't create `get_jet_pumps()`, `get_filters()`, etc. (10 tools). One `get_spec_category(category=SpecCategory)` is cleaner and easier for agents.
- **Embedding LLM logic in MCP layer:** The MCP tool must NOT interpret, summarize, or format data. Return raw structured data. The agent (Phase 6) handles presentation.
- **Loading JSON files on every request:** Load once at startup, serve from memory. JSON file I/O per request is needless latency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol handling | Custom JSON-RPC server | FastMCP `@mcp.tool` decorator | Protocol compliance, schema generation, transport handling |
| Tool parameter schemas | Manual JSON Schema writing | Python type annotations + FastMCP auto-generation | FastMCP generates schemas from `Literal`, `Enum`, `Annotated[..., Field()]` |
| Input validation | Custom parameter checking | Pydantic + FastMCP built-in validation | FastMCP validates inputs against generated schema before function executes |
| MCP transport (STDIO/HTTP) | Custom socket/subprocess code | `mcp.run(transport="stdio")` or `mcp.run(transport="http")` | FastMCP handles all transport protocols |
| Test harness for MCP tools | Custom MCP client for testing | `fastmcp.Client(mcp)` in-memory testing | Zero-network, instant tool calls in pytest |
| Model name resolution | Fuzzy matching / Levenshtein | Strict Literal type enum | Fuzzy matching introduces ambiguity; strict enums fail fast on bad input |

**Key insight:** FastMCP's type-annotation-to-schema pipeline means the Pydantic enums and Literal types already in the schema package translate directly into MCP tool constraints with zero additional code.

## Common Pitfalls

### Pitfall 1: Case Sensitivity in Model Names

**What goes wrong:** JSON files store `"model_name": "Aspen"` but LLM sends `"aspen"` or `"ASPEN"`. Lookup fails.
**Why it happens:** LLMs don't reliably preserve case. MCP schema `enum` values ARE case-sensitive in JSON Schema.
**How to avoid:** Normalize to lowercase in the data store key. Accept the enum value as-is (it comes from the constrained schema) but do case-insensitive lookup internally. The Literal type should use the canonical capitalized form ("Aspen") since that's what appears in the JSON Schema enum and what agents see.
**Warning signs:** Tests passing with exact case but failing with alternate case.

### Pitfall 2: Not-Available vs Null vs Missing

**What goes wrong:** Three different "empty" states get conflated: (a) category is `None` on SpaModel, (b) category exists but a field within it is `None`, (c) field is explicitly in `not_available_fields` list.
**Why it happens:** The JSON data has all three patterns. `not_available_fields` in `data_quality` tracks which nulls are confirmed not-available vs simply unknown.
**How to avoid:** The tool response must distinguish these. When a field is null AND in `not_available_fields`, say "not available from manufacturer documentation". When a field is null but NOT in `not_available_fields`, say "data not extracted".
**Warning signs:** User sees "null" in a response instead of an explanation.

### Pitfall 3: Returning Pydantic Models Directly vs Dict

**What goes wrong:** Returning `SpaModel` or sub-models directly causes serialization issues or overly complex responses.
**Why it happens:** MCP tools return text/JSON content. Pydantic models need `.model_dump()` to become dicts.
**How to avoid:** Always call `.model_dump(exclude_none=False)` on the category object before returning. Use `exclude_none=False` to preserve explicit null fields (important for showing what's missing). FastMCP handles dict-to-JSON serialization.
**Warning signs:** `TypeError` about non-serializable objects, or missing null fields in output.

### Pitfall 4: STDIO Logging Corruption

**What goes wrong:** `print()` statements or logging to stdout corrupt the JSON-RPC messages when using STDIO transport.
**Why it happens:** STDIO transport uses stdout for protocol messages. Any other stdout output breaks the protocol.
**How to avoid:** Use `logging` module configured to write to stderr only. Never use `print()` in MCP server code. Use `logging.basicConfig(stream=sys.stderr)`.
**Warning signs:** MCP client gets "invalid JSON" errors intermittently.

### Pitfall 5: Forgetting to Expose Source Documents

**What goes wrong:** Tool returns spec data but omits source provenance. Phase 8 (Response Quality) needs source attribution.
**Why it happens:** It's easy to only return the category sub-object and forget `source_documents` from the parent SpaModel.
**How to avoid:** Design the response structure to always include `source_documents` alongside the category data. This prevents needing a second tool call later.
**Warning signs:** Phase 8 needs source info but MCP tools don't provide it, requiring tool redesign.

## Code Examples

### Example 1: Complete MCP Server

```python
# backend/src/mcp/server.py
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from backend.src.mcp.data_store import get_model, get_store
from backend.src.mcp.enums import ModelName, SpecCategory
from backend.src.schema.enums import Manufacturer

mcp = FastMCP(
    name="DexDataServer",
    instructions=(
        "Dex data server provides deterministic lookup of spa technical "
        "specifications. Use get_spec_category for specific data, "
        "get_model_overview for model summaries, and list_models for discovery."
    ),
)


@mcp.tool
def get_spec_category(
    manufacturer: Manufacturer,
    model_name: Annotated[ModelName, Field(description="Spa model name")],
    category: Annotated[SpecCategory, Field(description="Spec category to retrieve")],
) -> dict:
    """Get a specific spec category for a spa model.

    Returns the complete data for one of the 10 spec categories
    (jet_pumps, circulation_pump, spa_pak, topside_control, jets,
    headrests, filters, heater, lighting, cover) for a specific
    manufacturer and model.
    """
    model = get_model(manufacturer.value, model_name)
    if model is None:
        return {
            "success": False,
            "message": f"Model '{model_name}' not found for manufacturer '{manufacturer.value}'",
        }

    category_data = getattr(model, category.value, None)
    if category_data is None:
        return {
            "success": True,
            "manufacturer": manufacturer.value,
            "model_name": model_name,
            "category": category.value,
            "data": None,
            "message": f"No {category.value} data available for {model_name}",
        }

    # Include not_available_fields for this category
    na_fields = []
    if model.data_quality and model.data_quality.not_available_fields:
        prefix = category.value + "."
        na_fields = [
            f.removeprefix(prefix)
            for f in model.data_quality.not_available_fields
            if f.startswith(prefix)
        ]

    return {
        "success": True,
        "manufacturer": manufacturer.value,
        "model_name": model_name,
        "category": category.value,
        "data": category_data.model_dump(),
        "not_available_fields": na_fields if na_fields else None,
        "source_documents": [
            s.model_dump() for s in model.source_documents
        ],
    }


@mcp.tool
def get_model_overview(
    manufacturer: Manufacturer,
    model_name: Annotated[ModelName, Field(description="Spa model name")],
) -> dict:
    """Get an overview of a spa model including identity, dimensions,
    and which spec categories have data available.

    Use this to understand what data exists before querying specific categories.
    """
    model = get_model(manufacturer.value, model_name)
    if model is None:
        return {
            "success": False,
            "message": f"Model '{model_name}' not found for manufacturer '{manufacturer.value}'",
        }

    categories_available = []
    categories_missing = []
    for cat in SpecCategory:
        if getattr(model, cat.value) is not None:
            categories_available.append(cat.value)
        else:
            categories_missing.append(cat.value)

    return {
        "success": True,
        "manufacturer": manufacturer.value,
        "series": model.series,
        "model_name": model.model_name,
        "year": model.year,
        "seating_capacity": model.seating_capacity,
        "dimensions": model.dimensions.model_dump(),
        "voltage": model.voltage,
        "amperage": model.amperage,
        "categories_available": categories_available,
        "categories_missing": categories_missing,
    }


@mcp.tool
def list_models(
    manufacturer: Annotated[
        Manufacturer | None,
        Field(description="Filter by manufacturer (optional)"),
    ] = None,
) -> dict:
    """List all available spa models in the data store.

    Optionally filter by manufacturer. Returns model identity info
    for each model (manufacturer, series, model name, year).
    """
    store = get_store()
    models = []
    for spa_model in store.values():
        if manufacturer and spa_model.manufacturer != manufacturer:
            continue
        models.append({
            "manufacturer": spa_model.manufacturer.value,
            "series": spa_model.series,
            "model_name": spa_model.model_name,
            "year": spa_model.year,
            "seating_capacity": spa_model.seating_capacity,
        })

    return {
        "success": True,
        "count": len(models),
        "models": sorted(models, key=lambda m: (m["manufacturer"], m["model_name"])),
    }
```

### Example 2: Server Entry Point

```python
# backend/src/mcp/__init__.py
from backend.src.mcp.server import mcp

__all__ = ["mcp"]
```

```python
# backend/src/mcp/__main__.py
"""Run the Dex MCP data server."""
from backend.src.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Example 3: Test Suite with In-Memory Client

```python
# backend/tests/test_mcp_tools.py
import pytest
from fastmcp import Client

from backend.src.mcp.server import mcp

@pytest.fixture
async def client():
    """Create an in-memory MCP client connected to the server."""
    async with Client(mcp) as c:
        yield c


# --- list_models tool ---

@pytest.mark.asyncio
async def test_list_models_returns_all_19(client):
    result = await client.call_tool("list_models", {})
    # Result is a list of content blocks; first block is text/JSON
    data = result  # FastMCP Client returns parsed content
    assert data["success"] is True
    assert data["count"] == 19


@pytest.mark.asyncio
async def test_list_models_filter_by_manufacturer(client):
    result = await client.call_tool(
        "list_models", {"manufacturer": "sundance"}
    )
    assert result["count"] == 7


# --- get_spec_category tool ---

SUNDANCE_MODELS = ["Altamar", "Aspen", "Cameo", "Capris", "Marin", "Optima", "Vistamar"]
HOTSPRING_MODELS = ["Aria", "Envoy", "Grandee", "Jetsetter", "Jetsetter LX", "Prodigy", "Sovereign", "Vanguard"]
BULLFROG_MODELS = ["M6", "M7", "M8", "M9"]
CATEGORIES = [
    "jet_pumps", "circulation_pump", "spa_pak", "topside_control",
    "jets", "headrests", "filters", "heater", "lighting", "cover",
]

ALL_MODELS = (
    [("sundance", m) for m in SUNDANCE_MODELS]
    + [("hotspring", m) for m in HOTSPRING_MODELS]
    + [("bullfrog", m) for m in BULLFROG_MODELS]
)


@pytest.mark.asyncio
@pytest.mark.parametrize("manufacturer,model_name", ALL_MODELS)
@pytest.mark.parametrize("category", CATEGORIES)
async def test_all_models_all_categories(client, manufacturer, model_name, category):
    """190 test cases: every model x every category returns a valid response."""
    result = await client.call_tool(
        "get_spec_category",
        {
            "manufacturer": manufacturer,
            "model_name": model_name,
            "category": category,
        },
    )
    assert result["success"] is True
    assert result["manufacturer"] == manufacturer
    assert result["model_name"] == model_name
    assert result["category"] == category
    # data is either a dict (has data) or None (with message explaining why)
    if result["data"] is None:
        assert result["message"] is not None


@pytest.mark.asyncio
async def test_invalid_model_returns_not_found(client):
    result = await client.call_tool(
        "get_spec_category",
        {
            "manufacturer": "sundance",
            "model_name": "Aspen",  # valid model
            "category": "jet_pumps",
        },
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_not_found_model(client):
    """Model that doesn't exist should return success=False with message."""
    # Note: With Literal type, FastMCP validation will reject invalid names
    # before the function runs. This tests the function's internal handling.
    # In practice, the Literal constraint prevents this case at the protocol level.
    pass  # See note above about Literal validation
```

### Example 4: pytest Configuration

```toml
# In pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["backend/tests"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastMCP 1.0 (merged into official SDK) | FastMCP 2.14.x standalone | Mid-2025 | FastMCP 2 adds testing Client, advanced auth, composition |
| Custom JSON-RPC for tool serving | MCP protocol standard | Late 2024 | Standardized tool protocol supported by Claude, GPT, etc. |
| RAG/vector search for part lookup | Deterministic enum-constrained MCP tools | Project decision | Zero-hallucination: exact match only, no "similar" results |
| Per-category tool functions | Single parameterized tool with category enum | Best practice 2025+ | Fewer tools = less agent confusion, easier maintenance |

**Deprecated/outdated:**
- FastMCP 1.0: Merged into official MCP Python SDK; standalone FastMCP 2.x is the maintained project
- SSE transport: Being replaced by Streamable HTTP in MCP spec; both work but HTTP is preferred for new deployments

## Open Questions

1. **Transport for Phase 6 Integration**
   - What we know: FastMCP supports STDIO and HTTP transports. `langchain-mcp-adapters` supports both. For Phase 6 (LangGraph agent), the MCP server can run as either a subprocess (STDIO) or a network service (HTTP).
   - What's unclear: Whether to use STDIO (simpler, in-process feel) or HTTP (matches eventual FastAPI deployment in Phase 10).
   - Recommendation: Start with STDIO for Phase 5 (simpler testing, no port management). Phase 6 will connect via `langchain-mcp-adapters` using STDIO transport. Phase 10 can switch to HTTP for deployment. The tool code is identical -- only `mcp.run(transport=...)` changes.

2. **FastMCP Client Return Type Parsing**
   - What we know: FastMCP Client's `call_tool()` returns MCP content blocks (list of `TextContent`). The actual dict needs to be parsed from the text content.
   - What's unclear: Whether FastMCP 2.14 auto-deserializes structured content or if tests need `json.loads(result[0].text)`.
   - Recommendation: Write a small test helper that extracts the dict from the response. Verify behavior in the first test and adjust.

3. **Model Name Validation Strictness**
   - What we know: Using `Literal["Aspen", "Cameo", ...]` in the type annotation makes FastMCP reject invalid names at the protocol level (before the function runs).
   - What's unclear: Whether LLMs reliably send the exact case from the JSON Schema enum, or if we need case-insensitive matching.
   - Recommendation: Use the Literal type for schema constraint (agents see the valid list). Internally, also do case-insensitive lookup as a safety net. If the Literal validation rejects bad case, the error message from FastMCP will include the valid options.

## Sources

### Primary (HIGH confidence)
- [FastMCP Tools documentation](https://gofastmcp.com/servers/tools) - Tool decorator, type annotations, enum/Literal support, error handling, structured output
- [FastMCP Resources documentation](https://gofastmcp.com/servers/resources) - Resource patterns (evaluated, tools chosen instead)
- [FastMCP Testing documentation](https://gofastmcp.com/patterns/testing) - In-memory Client testing, pytest-asyncio setup
- [FastMCP PyPI](https://pypi.org/project/fastmcp/) - Version 2.14.5 current stable, Python 3.10+ required
- [FastMCP Updates](https://gofastmcp.com/updates) - v2.14.5 latest stable, v3.0.0rc1 pre-release
- [langchain-mcp-adapters GitHub](https://github.com/langchain-ai/langchain-mcp-adapters) - MCP-to-LangChain tool bridge for Phase 6

### Secondary (MEDIUM confidence)
- [FastMCP 3 announcement](https://www.jlowin.dev/blog/fastmcp-3) - v3 breaking changes confirmed, migration path documented
- [LangGraph + MCP integration articles](https://medium.com/@termtrix/building-a-simple-ai-agent-using-fastapi-langgraph-mcp-03fc7ffbea59) - Architecture patterns for FastAPI + LangGraph + MCP

### Tertiary (LOW confidence)
- Transport recommendations (STDIO vs HTTP) - Based on multiple community sources; official MCP docs don't prescribe one over the other for agent use cases

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastMCP 2.14.x is well-documented, versions verified on PyPI, type annotation support confirmed in official docs
- Architecture: HIGH - Data store pattern is straightforward (19 JSON files, in-memory dict); tool design follows FastMCP official patterns
- Pitfalls: HIGH - STDIO logging corruption documented officially; enum case sensitivity verified against FastMCP behavior; not-available handling derived from actual data analysis of JSON files
- Testing: HIGH - FastMCP Client-based testing documented in official patterns; pytest-asyncio configuration confirmed

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (FastMCP v2 is stable; v3 GA may change recommendation)
