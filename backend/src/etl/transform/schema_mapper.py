"""Maps raw Claude extraction dicts to validated Pydantic SpaModel instances.

Takes the per-category ``CategoryExtraction`` results produced by
``claude_extractor.extract_model_specs`` and assembles them into a single
``SpaModel`` that conforms to the Phase 1 schema.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...schema.models import SpaModel
from ...schema.parts import SourceReference
from ..config import DATA_OUTPUT_DIR
from ..extract.claude_extractor import CategoryExtraction

logger = logging.getLogger(__name__)


def _get(
    extractions: dict[str, CategoryExtraction],
    key: str,
    fallback: Any = None,
) -> dict:
    """Safely retrieve the parsed data dict for a category extraction."""
    extraction = extractions.get(key)
    if extraction is None:
        return fallback if fallback is not None else {}
    return extraction.data or (fallback if fallback is not None else {})


def _find_in_data(
    extractions: dict[str, CategoryExtraction],
    field: str,
    search_categories: list[str] | None = None,
) -> Any:
    """Search multiple category extractions for a specific field value.

    Useful for fields like ``seating_capacity`` that might appear in
    different categories depending on the manufacturer's PDF layout.
    """
    categories = search_categories or list(extractions.keys())
    for cat in categories:
        data = _get(extractions, cat)
        if field in data and data[field] is not None:
            return data[field]
    return None


def map_to_spa_model(
    manufacturer: str,
    series: str,
    model_name: str,
    year: int,
    extractions: dict[str, CategoryExtraction],
    source_refs: list[SourceReference],
) -> SpaModel | None:
    """Assemble category extractions into a validated SpaModel.

    Args:
        manufacturer: Manufacturer key (e.g. ``"sundance"``).
        series: Series name (e.g. ``"880 Series"``).
        model_name: Model name (e.g. ``"Aspen"``).
        year: Model year (e.g. ``2026``).
        extractions: Dict mapping category names to their
            ``CategoryExtraction`` results.
        source_refs: Provenance references built from the extractions.

    Returns:
        A validated ``SpaModel`` instance, or ``None`` if validation
        fails.  On failure the raw data dict is saved as a ``-RAW.json``
        file for debugging.
    """
    # Look for seating_capacity across several likely categories
    seating = _find_in_data(
        extractions,
        "seating_capacity",
        ["dimensions", "general", "jet_pumps", "jets"],
    )

    # Look for top-level electrical data
    voltage = _find_in_data(
        extractions,
        "voltage",
        ["spa_pak", "heater", "general"],
    )
    amperage = _find_in_data(
        extractions,
        "amperage",
        ["spa_pak", "heater", "general"],
    )

    model_data: dict[str, Any] = {
        # Identity
        "manufacturer": manufacturer,
        "series": series,
        "model_name": model_name,
        "year": year,
        "seating_capacity": seating or 0,
        # 10 spec categories -- use extracted data or sensible defaults
        "jet_pumps": _get(extractions, "jet_pumps"),
        "circulation_pump": _get(extractions, "circulation_pump") or None,
        "spa_pak": _get(extractions, "spa_pak"),
        "topside_control": _get(extractions, "topside_control"),
        "jets": _get(extractions, "jets"),
        "headrests": _get(extractions, "headrests"),
        "filters": _get(extractions, "filters"),
        "heater": _get(extractions, "heater"),
        "lighting": _get(extractions, "lighting"),
        "cover": _get(extractions, "cover"),
        # Physical dimensions
        "dimensions": _get(extractions, "dimensions"),
        # Electrical
        "voltage": voltage or 240,
        "amperage": amperage,
        # Metadata
        "source_documents": [ref.model_dump() for ref in source_refs],
    }

    try:
        spa_model = SpaModel.model_validate(model_data)
        return spa_model
    except ValidationError as exc:
        logger.error(
            "Validation failed for %s %s %d:\n%s",
            manufacturer,
            model_name,
            year,
            exc,
        )

        # Save raw data for debugging
        try:
            from ..output.writer import write_raw_json

            output_dir = DATA_OUTPUT_DIR / manufacturer
            write_raw_json(model_name, year, model_data, output_dir)
        except Exception as write_exc:
            logger.warning("Could not write RAW debug file: %s", write_exc)

        return None
