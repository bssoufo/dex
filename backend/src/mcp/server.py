"""Dex MCP data server -- FastMCP instance and tool definitions.

Four tools provide deterministic lookup of spa technical specifications:
  - get_spec_category: Get one spec category for one model
  - get_model_overview: Get identity/dimensions/available categories
  - list_models: List all models, optionally filtered by manufacturer
  - find_cross_references: Find models sharing identical component specs

Tool parameters accept flexible string inputs (case-insensitive, with
common aliases) and normalize them internally, so LLM agents don't need
to match exact enum values.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from backend.src.mcp.data_store import get_model, get_store, find_cross_references as _find_xref
from backend.src.mcp.enums import SpecCategory

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="DexDataServer",
    instructions=(
        "Dex data server provides deterministic lookup of spa technical "
        "specifications. Use get_spec_category for specific data, "
        "get_model_overview for model summaries, and list_models for discovery."
    ),
)

# ---------------------------------------------------------------------------
# Input normalization helpers
# ---------------------------------------------------------------------------

# Manufacturer aliases: map common variations to canonical values
_MANUFACTURER_ALIASES: dict[str, str] = {
    "sundance": "sundance",
    "sundance spas": "sundance",
    "hot spring": "hotspring",
    "hotspring": "hotspring",
    "hot spring spas": "hotspring",
    "bullfrog": "bullfrog",
    "bullfrog spas": "bullfrog",
}

# Canonical model names keyed by lowercase
_MODEL_NAMES: dict[str, str] = {
    "altamar": "Altamar",
    "aspen": "Aspen",
    "cameo": "Cameo",
    "capris": "Capris",
    "capri": "Capris",
    "marin": "Marin",
    "optima": "Optima",
    "vistamar": "Vistamar",
    "aria": "Aria",
    "envoy": "Envoy",
    "grandee": "Grandee",
    "jetsetter": "Jetsetter",
    "jetsetter lx": "Jetsetter LX",
    "prodigy": "Prodigy",
    "sovereign": "Sovereign",
    "vanguard": "Vanguard",
    "m6": "M6",
    "m7": "M7",
    "m8": "M8",
    "m9": "M9",
}

# Category aliases: map common variations to canonical SpecCategory values
_CATEGORY_ALIASES: dict[str, str] = {
    "jet_pumps": "jet_pumps",
    "jet pumps": "jet_pumps",
    "jetpumps": "jet_pumps",
    "pumps": "jet_pumps",
    "jet pump": "jet_pumps",
    "circulation_pump": "circulation_pump",
    "circulation pump": "circulation_pump",
    "circ pump": "circulation_pump",
    "circpump": "circulation_pump",
    "spa_pak": "spa_pak",
    "spa pak": "spa_pak",
    "spapak": "spa_pak",
    "spa pack": "spa_pak",
    "topside_control": "topside_control",
    "topside control": "topside_control",
    "topside": "topside_control",
    "control panel": "topside_control",
    "jets": "jets",
    "headrests": "headrests",
    "headrest": "headrests",
    "pillows": "headrests",
    "filters": "filters",
    "filter": "filters",
    "filtration": "filters",
    "heater": "heater",
    "heater element": "heater",
    "heating": "heater",
    "lighting": "lighting",
    "lights": "lighting",
    "light": "lighting",
    "light bulb": "lighting",
    "cover": "cover",
    "spa cover": "cover",
    "covers": "cover",
}

_VALID_MANUFACTURERS = ["sundance", "hotspring", "bullfrog"]
_VALID_MODELS = sorted(set(_MODEL_NAMES.values()))
_VALID_CATEGORIES = [c.value for c in SpecCategory]


def _resolve_manufacturer(raw: str) -> str | None:
    """Resolve a raw manufacturer string to a canonical value.

    Returns the canonical manufacturer string, or None if not matched.
    """
    cleaned = raw.strip().lower()
    return _MANUFACTURER_ALIASES.get(cleaned)


def _resolve_model_name(raw: str) -> str | None:
    """Resolve a raw model name string to a canonical value.

    Handles case-insensitive matching and strips manufacturer prefixes
    (e.g., 'Sundance Aspen' -> 'Aspen', 'Hot Spring Grandee' -> 'Grandee').

    Returns the canonical model name string, or None if not matched.
    """
    cleaned = raw.strip().lower()

    # Direct match
    if cleaned in _MODEL_NAMES:
        return _MODEL_NAMES[cleaned]

    # Strip manufacturer prefix (e.g., "sundance aspen" -> "aspen")
    for prefix in _MANUFACTURER_ALIASES:
        if cleaned.startswith(prefix + " "):
            remainder = cleaned[len(prefix) + 1:].strip()
            if remainder in _MODEL_NAMES:
                return _MODEL_NAMES[remainder]

    # Strip year suffix (e.g., "aspen 2026" -> "aspen")
    parts = cleaned.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit():
        if parts[0] in _MODEL_NAMES:
            return _MODEL_NAMES[parts[0]]

    # Strip both manufacturer and year (e.g., "sundance aspen 2026")
    for prefix in _MANUFACTURER_ALIASES:
        if cleaned.startswith(prefix + " "):
            remainder = cleaned[len(prefix) + 1:].strip()
            r_parts = remainder.rsplit(" ", 1)
            if len(r_parts) == 2 and r_parts[1].isdigit():
                if r_parts[0] in _MODEL_NAMES:
                    return _MODEL_NAMES[r_parts[0]]

    return None


def _resolve_category(raw: str) -> str | None:
    """Resolve a raw category string to a canonical SpecCategory value.

    Returns the canonical category string, or None if not matched.
    """
    cleaned = raw.strip().lower()
    return _CATEGORY_ALIASES.get(cleaned)


def _error_manufacturer(raw: str) -> dict:
    """Return a helpful error for unrecognized manufacturer."""
    return {
        "success": False,
        "message": (
            f"Manufacturer '{raw}' not recognized. "
            f"Valid manufacturers: {', '.join(_VALID_MANUFACTURERS)}"
        ),
    }


def _error_model(raw: str) -> dict:
    """Return a helpful error for unrecognized model name."""
    return {
        "success": False,
        "message": (
            f"Model '{raw}' not recognized. "
            f"Valid model names: {', '.join(_VALID_MODELS)}"
        ),
    }


def _error_category(raw: str) -> dict:
    """Return a helpful error for unrecognized category."""
    return {
        "success": False,
        "message": (
            f"Category '{raw}' not recognized. "
            f"Valid categories: {', '.join(_VALID_CATEGORIES)}"
        ),
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool
def get_spec_category(
    manufacturer: Annotated[str, Field(description="Manufacturer: sundance, hotspring, or bullfrog")],
    model_name: Annotated[str, Field(description="Model name (e.g., Aspen, Grandee, M9)")],
    category: Annotated[str, Field(description="Spec category: jet_pumps, circulation_pump, spa_pak, topside_control, jets, headrests, filters, heater, lighting, or cover")],
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
    mfr = _resolve_manufacturer(manufacturer)
    if mfr is None:
        return _error_manufacturer(manufacturer)

    name = _resolve_model_name(model_name)
    if name is None:
        return _error_model(model_name)

    cat = _resolve_category(category)
    if cat is None:
        return _error_category(category)

    logger.info("get_spec_category: %s %s -> %s", mfr, name, cat)

    model = get_model(mfr, name)
    if model is None:
        logger.warning("get_spec_category: model not found %s/%s", mfr, name)
        return {
            "success": False,
            "message": f"Model '{name}' not found for manufacturer '{mfr}'",
        }

    dq = model.data_quality
    logger.info(
        "get_spec_category: serving %s %s (verified=%s, completeness=%s%%)",
        mfr, name,
        dq.verification_date if dq else "N/A",
        dq.completeness_pct if dq else "N/A",
    )

    category_data = getattr(model, cat, None)
    if category_data is None:
        return {
            "success": True,
            "manufacturer": mfr,
            "model_name": name,
            "category": cat,
            "data": None,
            "message": f"No {cat} data available for {name}",
        }

    # Extract not_available_fields scoped to this category
    na_fields: list[str] = []
    if model.data_quality and model.data_quality.not_available_fields:
        prefix = cat + "."
        na_fields = [
            f.removeprefix(prefix)
            for f in model.data_quality.not_available_fields
            if f.startswith(prefix)
        ]

    return {
        "success": True,
        "manufacturer": mfr,
        "model_name": name,
        "category": cat,
        "data": category_data.model_dump(),
        "not_available_fields": na_fields if na_fields else None,
        "source_documents": [s.model_dump() for s in model.source_documents],
    }


@mcp.tool
def get_model_overview(
    manufacturer: Annotated[str, Field(description="Manufacturer: sundance, hotspring, or bullfrog")],
    model_name: Annotated[str, Field(description="Model name (e.g., Aspen, Grandee, M9)")],
) -> dict:
    """Get an overview of a spa model including identity, dimensions,
    and which spec categories have data available.

    Use this to understand what data exists for a model before querying
    specific categories with get_spec_category.
    """
    mfr = _resolve_manufacturer(manufacturer)
    if mfr is None:
        return _error_manufacturer(manufacturer)

    name = _resolve_model_name(model_name)
    if name is None:
        return _error_model(model_name)

    logger.info("get_model_overview: %s %s", mfr, name)

    model = get_model(mfr, name)
    if model is None:
        logger.warning("get_model_overview: model not found %s/%s", mfr, name)
        return {
            "success": False,
            "message": f"Model '{name}' not found for manufacturer '{mfr}'",
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
        "manufacturer": mfr,
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
    manufacturer: Annotated[str | None, Field(description="Filter by manufacturer: sundance, hotspring, or bullfrog (optional)")] = None,
) -> dict:
    """List all available spa models in the data store.

    Optionally filter by manufacturer. Returns model identity info
    for each model (manufacturer, series, model name, year, seating capacity).
    Use this for discovery before querying specific models.
    """
    mfr = None
    if manufacturer:
        mfr = _resolve_manufacturer(manufacturer)
        if mfr is None:
            return _error_manufacturer(manufacturer)

    logger.info("list_models: manufacturer=%s", mfr or "all")

    store = get_store()
    models: list[dict] = []
    for spa_model in store.values():
        if mfr and spa_model.manufacturer.value != mfr:
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
    manufacturer: Annotated[str, Field(description="Manufacturer: sundance, hotspring, or bullfrog")],
    model_name: Annotated[str, Field(description="Model name (e.g., Aspen, Grandee, M9)")],
    category: Annotated[str, Field(description="Spec category: jet_pumps, circulation_pump, spa_pak, topside_control, jets, headrests, filters, heater, lighting, or cover")],
) -> dict:
    """Find other models that share the same component specs for a given category.

    Compares the target model's category data against all other models from the
    same manufacturer. Useful for answering 'What other models use this same
    pump/heater/filter?' Returns the list of matching model names and the total
    count of models from that manufacturer for context.
    """
    mfr = _resolve_manufacturer(manufacturer)
    if mfr is None:
        return _error_manufacturer(manufacturer)

    name = _resolve_model_name(model_name)
    if name is None:
        return _error_model(model_name)

    cat = _resolve_category(category)
    if cat is None:
        return _error_category(category)

    logger.info("find_cross_references: %s %s -> %s", mfr, name, cat)

    matches = _find_xref(mfr, name, cat)

    # Count total models for this manufacturer
    store = get_store()
    total = sum(1 for (store_mfr, _) in store if store_mfr == mfr)

    return {
        "success": True,
        "manufacturer": mfr,
        "model_name": name,
        "category": cat,
        "matching_models": matches,
        "match_count": len(matches),
        "total_manufacturer_models": total,
    }
