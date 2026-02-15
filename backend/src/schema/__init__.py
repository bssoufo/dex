"""Dex spa specification schema package.

Public API for the schema used by ETL (writes) and MCP tools (reads).
"""

from __future__ import annotations

from .enums import JetSystemType, Manufacturer, PumpSpeed
from .parts import DimensionsSpec, PartReference, SourceReference

# SpaModel and category models will be added in Task 2
# from .models import SpaModel

__all__ = [
    "DimensionsSpec",
    "JetSystemType",
    "Manufacturer",
    "PartReference",
    "PumpSpeed",
    "SourceReference",
]
