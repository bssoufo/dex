"""MCP-specific enumerated types for tool parameter constraints.

SpecCategory maps to the 10 spec category fields on SpaModel.
ModelName is a Literal type constraining valid model name inputs
so LLM agents cannot invent non-existent model names.
"""

from __future__ import annotations

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


# Literal type with exactly 19 valid model names (canonical capitalization from JSON files).
# FastMCP auto-generates JSON Schema with enum constraint from this type.
ModelName = Literal[
    # Sundance (7)
    "Altamar",
    "Aspen",
    "Cameo",
    "Capris",
    "Marin",
    "Optima",
    "Vistamar",
    # Hot Spring (8)
    "Aria",
    "Envoy",
    "Grandee",
    "Jetsetter",
    "Jetsetter LX",
    "Prodigy",
    "Sovereign",
    "Vanguard",
    # Bullfrog (4)
    "M6",
    "M7",
    "M8",
    "M9",
]
