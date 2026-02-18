"""Dex MCP data server -- FastMCP instance and tool definitions.

Four tools provide deterministic lookup of spa technical specifications:
  - get_spec_category: Get one spec category for one model
  - get_model_overview: Get identity/dimensions/available categories
  - list_models: List all models, optionally filtered by manufacturer
  - find_cross_references: Find models sharing identical component specs

All tool parameters are constrained by enums/Literal types so LLM agents
cannot invent invalid model names or category names.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from backend.src.mcp.data_store import get_model, get_store, find_cross_references as _find_xref
from backend.src.mcp.enums import ModelName, SpecCategory
from backend.src.schema.enums import Manufacturer

logger = logging.getLogger(__name__)

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

    Includes not_available_fields listing which fields within the category
    are confirmed unavailable from manufacturer documentation, and
    source_documents for provenance tracking.
    """
    logger.info("get_spec_category: %s %s -> %s", manufacturer.value, model_name, category.value)

    model = get_model(manufacturer.value, model_name)
    if model is None:
        logger.warning("get_spec_category: model not found %s/%s", manufacturer.value, model_name)
        return {
            "success": False,
            "message": (
                f"Model '{model_name}' not found for "
                f"manufacturer '{manufacturer.value}'"
            ),
        }

    dq = model.data_quality
    logger.info(
        "get_spec_category: serving %s %s (verified=%s, completeness=%s%%)",
        manufacturer.value,
        model_name,
        dq.verification_date if dq else "N/A",
        dq.completeness_pct if dq else "N/A",
    )

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

    # Extract not_available_fields scoped to this category
    na_fields: list[str] = []
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
        "source_documents": [s.model_dump() for s in model.source_documents],
    }


@mcp.tool
def get_model_overview(
    manufacturer: Manufacturer,
    model_name: Annotated[ModelName, Field(description="Spa model name")],
) -> dict:
    """Get an overview of a spa model including identity, dimensions,
    and which spec categories have data available.

    Use this to understand what data exists for a model before querying
    specific categories with get_spec_category.
    """
    logger.info("get_model_overview: %s %s", manufacturer.value, model_name)

    model = get_model(manufacturer.value, model_name)
    if model is None:
        logger.warning("get_model_overview: model not found %s/%s", manufacturer.value, model_name)
        return {
            "success": False,
            "message": (
                f"Model '{model_name}' not found for "
                f"manufacturer '{manufacturer.value}'"
            ),
        }

    categories_available: list[str] = []
    categories_missing: list[str] = []
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
        "source_documents": [s.model_dump() for s in model.source_documents],
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
    for each model (manufacturer, series, model name, year, seating capacity).
    Use this for discovery before querying specific models.
    """
    logger.info("list_models: manufacturer=%s", manufacturer.value if manufacturer else "all")

    store = get_store()
    models: list[dict] = []
    for spa_model in store.values():
        if manufacturer and spa_model.manufacturer != manufacturer:
            continue
        models.append(
            {
                "manufacturer": spa_model.manufacturer.value,
                "series": spa_model.series,
                "model_name": spa_model.model_name,
                "year": spa_model.year,
                "seating_capacity": spa_model.seating_capacity,
            }
        )

    return {
        "success": True,
        "count": len(models),
        "models": sorted(
            models, key=lambda m: (m["manufacturer"], m["model_name"])
        ),
    }


@mcp.tool
def find_cross_references(
    manufacturer: Manufacturer,
    model_name: Annotated[ModelName, Field(description="Spa model name")],
    category: Annotated[SpecCategory, Field(description="Spec category to cross-reference")],
) -> dict:
    """Find other models that share the same component specs for a given category.

    Compares the target model's category data against all other models from the
    same manufacturer. Useful for answering 'What other models use this same
    pump/heater/filter?' Returns the list of matching model names and the total
    count of models from that manufacturer for context.
    """
    logger.info("find_cross_references: %s %s -> %s", manufacturer.value, model_name, category.value)

    matches = _find_xref(manufacturer.value, model_name, category.value)

    # Count total models for this manufacturer
    store = get_store()
    total = sum(1 for (mfr, _) in store if mfr == manufacturer.value)

    return {
        "success": True,
        "manufacturer": manufacturer.value,
        "model_name": model_name,
        "category": category.value,
        "matching_models": matches,
        "match_count": len(matches),
        "total_manufacturer_models": total,
    }
