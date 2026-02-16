"""Comprehensive MCP tool test suite for the Dex data server.

Tests all 3 MCP tools (get_spec_category, get_model_overview, list_models)
across all 19 spa models and 10 spec categories (190 combinations) using
FastMCP's in-memory Client. No network or filesystem access beyond initial
data store load.

Organized into 5 test groups:
  1. list_models -- count, filtering, sorting
  2. get_model_overview -- parametrized over all 19 models
  3. get_spec_category -- 190 parametrized model x category combinations
  4. Specific data verification -- real data assertions (not just structure)
  5. Not-found handling -- mismatched manufacturer/model
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from backend.src.mcp.server import mcp

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Yield a FastMCP in-memory client connected to the Dex MCP server."""
    async with Client(mcp) as c:
        yield c


def parse_result(result) -> dict:
    """Extract dict from FastMCP Client call_tool response.

    FastMCP 2.14 Client.call_tool() returns a CallToolResult whose
    .content is a list of TextContent blocks. The first block's .text
    is a JSON string representing the tool return value.

    Handles both CallToolResult and raw dict (future-proofing).
    """
    # CallToolResult with .content attribute
    if hasattr(result, "content"):
        text = result.content[0].text
        return json.loads(text)
    # Already a dict (hypothetical future FastMCP change)
    if isinstance(result, dict):
        return result
    # List of content blocks (legacy path)
    if isinstance(result, list) and len(result) > 0:
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        return json.loads(text)
    return json.loads(str(result))


# ---------------------------------------------------------------------------
# Model and category constants
# ---------------------------------------------------------------------------

ALL_MODELS = [
    ("sundance", "Altamar"),
    ("sundance", "Aspen"),
    ("sundance", "Cameo"),
    ("sundance", "Capris"),
    ("sundance", "Marin"),
    ("sundance", "Optima"),
    ("sundance", "Vistamar"),
    ("hotspring", "Aria"),
    ("hotspring", "Envoy"),
    ("hotspring", "Grandee"),
    ("hotspring", "Jetsetter"),
    ("hotspring", "Jetsetter LX"),
    ("hotspring", "Prodigy"),
    ("hotspring", "Sovereign"),
    ("hotspring", "Vanguard"),
    ("bullfrog", "M6"),
    ("bullfrog", "M7"),
    ("bullfrog", "M8"),
    ("bullfrog", "M9"),
]

CATEGORIES = [
    "jet_pumps",
    "circulation_pump",
    "spa_pak",
    "topside_control",
    "jets",
    "headrests",
    "filters",
    "heater",
    "lighting",
    "cover",
]


# ---------------------------------------------------------------------------
# Group 1: list_models
# ---------------------------------------------------------------------------


class TestListModels:
    """Tests for the list_models MCP tool."""

    async def test_list_all_models(self, client: Client) -> None:
        """list_models with no filter returns all 19 models."""
        result = parse_result(await client.call_tool("list_models", {}))
        assert result["success"] is True
        assert result["count"] == 19

    async def test_list_sundance_models(self, client: Client) -> None:
        """list_models filtered to Sundance returns 7 models."""
        result = parse_result(
            await client.call_tool("list_models", {"manufacturer": "sundance"})
        )
        assert result["success"] is True
        assert result["count"] == 7

    async def test_list_hotspring_models(self, client: Client) -> None:
        """list_models filtered to Hot Spring returns 8 models."""
        result = parse_result(
            await client.call_tool("list_models", {"manufacturer": "hotspring"})
        )
        assert result["success"] is True
        assert result["count"] == 8

    async def test_list_bullfrog_models(self, client: Client) -> None:
        """list_models filtered to Bullfrog returns 4 models."""
        result = parse_result(
            await client.call_tool("list_models", {"manufacturer": "bullfrog"})
        )
        assert result["success"] is True
        assert result["count"] == 4

    async def test_list_models_sorted(self, client: Client) -> None:
        """list_models returns models sorted by (manufacturer, model_name)."""
        result = parse_result(await client.call_tool("list_models", {}))
        models = result["models"]
        sort_keys = [(m["manufacturer"], m["model_name"]) for m in models]
        assert sort_keys == sorted(sort_keys)


# ---------------------------------------------------------------------------
# Group 2: get_model_overview (all 19 models)
# ---------------------------------------------------------------------------


class TestGetModelOverview:
    """Tests for the get_model_overview MCP tool across all 19 models."""

    @pytest.mark.parametrize(
        ("manufacturer", "model_name"),
        ALL_MODELS,
        ids=[f"{m}-{n}" for m, n in ALL_MODELS],
    )
    async def test_model_overview(
        self, client: Client, manufacturer: str, model_name: str
    ) -> None:
        """get_model_overview returns valid data for every model."""
        result = parse_result(
            await client.call_tool(
                "get_model_overview",
                {"manufacturer": manufacturer, "model_name": model_name},
            )
        )
        assert result["success"] is True
        assert result["manufacturer"] == manufacturer
        assert result["model_name"] == model_name
        assert isinstance(result["series"], str)
        assert isinstance(result["year"], int)

        # Dimensions must be a dict with required keys
        dims = result["dimensions"]
        assert isinstance(dims, dict)
        for key in ("length_inches", "width_inches", "height_inches"):
            assert key in dims

        # Categories
        assert isinstance(result["categories_available"], list)
        assert len(result["categories_available"]) > 0
        assert isinstance(result["categories_missing"], list)


# ---------------------------------------------------------------------------
# Group 3: get_spec_category (190 combinations)
# ---------------------------------------------------------------------------


class TestGetSpecCategory:
    """190 parametrized tests: every model x every category."""

    @pytest.mark.parametrize("category", CATEGORIES, ids=CATEGORIES)
    @pytest.mark.parametrize(
        ("manufacturer", "model_name"),
        ALL_MODELS,
        ids=[f"{m}-{n}" for m, n in ALL_MODELS],
    )
    async def test_all_models_all_categories(
        self,
        client: Client,
        manufacturer: str,
        model_name: str,
        category: str,
    ) -> None:
        """Every model-category combination returns a valid structured response."""
        result = parse_result(
            await client.call_tool(
                "get_spec_category",
                {
                    "manufacturer": manufacturer,
                    "model_name": model_name,
                    "category": category,
                },
            )
        )
        assert result["success"] is True
        assert result["manufacturer"] == manufacturer
        assert result["model_name"] == model_name
        assert result["category"] == category

        # If data is None, there must be an explanatory message
        if result["data"] is None:
            assert result.get("message") is not None
            assert len(result["message"]) > 0
        else:
            # Data present -- must be a dict
            assert isinstance(result["data"], dict)

        # source_documents must always be a list (may be empty for null categories)
        if result["data"] is not None:
            assert isinstance(result["source_documents"], list)


# ---------------------------------------------------------------------------
# Group 4: Specific data verification
# ---------------------------------------------------------------------------


class TestSpecificDataVerification:
    """Spot-check real data flows through the MCP layer (not just structure)."""

    async def test_aspen_jet_pumps_has_data(self, client: Client) -> None:
        """Sundance Aspen jet_pumps returns actual pump data."""
        result = parse_result(
            await client.call_tool(
                "get_spec_category",
                {
                    "manufacturer": "sundance",
                    "model_name": "Aspen",
                    "category": "jet_pumps",
                },
            )
        )
        assert result["success"] is True
        assert result["data"] is not None
        assert "pumps" in result["data"]
        pumps = result["data"]["pumps"]
        assert isinstance(pumps, list)
        assert len(pumps) >= 2

    async def test_aspen_jet_pumps_has_not_available_fields(
        self, client: Client
    ) -> None:
        """Sundance Aspen jet_pumps includes not_available_fields (many NA part numbers)."""
        result = parse_result(
            await client.call_tool(
                "get_spec_category",
                {
                    "manufacturer": "sundance",
                    "model_name": "Aspen",
                    "category": "jet_pumps",
                },
            )
        )
        assert result["success"] is True
        assert result["not_available_fields"] is not None
        assert isinstance(result["not_available_fields"], list)
        assert len(result["not_available_fields"]) > 0

    async def test_spec_category_includes_source_documents(
        self, client: Client
    ) -> None:
        """Source documents are present in get_spec_category responses."""
        result = parse_result(
            await client.call_tool(
                "get_spec_category",
                {
                    "manufacturer": "sundance",
                    "model_name": "Aspen",
                    "category": "jet_pumps",
                },
            )
        )
        assert result["success"] is True
        assert isinstance(result["source_documents"], list)
        assert len(result["source_documents"]) >= 1

        # Each source document should have basic structure
        doc = result["source_documents"][0]
        assert isinstance(doc, dict)

    async def test_grandee_overview_has_all_categories(
        self, client: Client
    ) -> None:
        """Hot Spring Grandee is a full-data model with all 10 categories."""
        result = parse_result(
            await client.call_tool(
                "get_model_overview",
                {"manufacturer": "hotspring", "model_name": "Grandee"},
            )
        )
        assert result["success"] is True
        assert len(result["categories_available"]) == 10
        assert len(result["categories_missing"]) == 0


# ---------------------------------------------------------------------------
# Group 5: Not-found handling
# ---------------------------------------------------------------------------


class TestNotFoundHandling:
    """Tests for invalid/mismatched model lookups."""

    async def test_not_found_handling_documented(self, client: Client) -> None:
        """FastMCP Literal types reject invalid model names at protocol level.

        Invalid manufacturer/model combinations that pass Literal validation
        but don't exist in the data store are handled by the tool returning
        success=False. Here we test a valid manufacturer + valid model name
        that are mismatched (Sundance manufacturer + Bullfrog model M9).
        """
        result = parse_result(
            await client.call_tool(
                "get_spec_category",
                {
                    "manufacturer": "sundance",
                    "model_name": "M9",
                    "category": "jet_pumps",
                },
            )
        )
        assert result["success"] is False
        assert "not found" in result["message"].lower()
