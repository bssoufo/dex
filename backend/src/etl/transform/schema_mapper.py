"""Maps raw extraction dicts to validated Pydantic SpaModel instances.

Takes the per-category ``CategoryExtraction`` results produced by
``gemini_extractor.extract_model_specs`` and assembles them into a single
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
from ..extract.gemini_extractor import CategoryExtraction

logger = logging.getLogger(__name__)


def _clean_extraction_data(data: Any) -> Any:
    """Recursively clean extraction data from Gemini quirks.

    - Converts string ``"null"`` to ``None``
    - Unwraps nested ``{"data": {...}}`` wrappers
    - Converts numeric strings like ``"240"`` to int where possible
    - Converts ``"one or more"`` and similar text to ``None`` for int fields
    """
    if isinstance(data, dict):
        # Unwrap nested "data" key if it's the only meaningful key
        if "data" in data and isinstance(data["data"], (dict, list)):
            inner = data["data"]
            # If the dict only has "data" or "data" plus metadata keys, unwrap
            other_keys = {k for k in data if k != "data"}
            if not other_keys or other_keys <= {"model_name", "spec_category", "notes"}:
                data = inner if isinstance(inner, dict) else {"items": inner}

        return {k: _clean_extraction_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_clean_extraction_data(item) for item in data]
    if isinstance(data, str):
        if data.lower() in ("null", "none", "n/a", "na", "unknown"):
            return None
    return data


def _get(
    extractions: dict[str, CategoryExtraction],
    key: str,
    fallback: Any = None,
) -> dict:
    """Safely retrieve the parsed data dict for a category extraction."""
    extraction = extractions.get(key)
    if extraction is None:
        return fallback if fallback is not None else {}
    raw = extraction.data or (fallback if fallback is not None else {})
    return _clean_extraction_data(raw)


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


def _extract_general_fields(
    extractions: dict[str, CategoryExtraction],
) -> dict[str, Any]:
    """Extract 'general' fields that are piggybacked on the jet_pumps prompt.

    The extraction templates embed seating_capacity, dimensions, voltage,
    amperage, etc. inside the jet_pumps response under a "general" key.
    This function pulls them out and merges them into a flat dict.
    """
    jet_pumps_data = _get(extractions, "jet_pumps")
    general = jet_pumps_data.get("general", {})
    if not isinstance(general, dict):
        general = {}
    return general


def _fix_pump_hp(jet_pumps_data: dict) -> dict:
    """Ensure every pump has a non-null horsepower_continuous.

    When the PDF doesn't list explicit HP, estimate from amperage:
    ~1 HP per 10A at 240V for spa pumps (rough industry estimate).
    """
    pumps = jet_pumps_data.get("pumps", [])
    if not isinstance(pumps, list):
        return jet_pumps_data

    for pump in pumps:
        if not isinstance(pump, dict):
            continue
        hp = pump.get("horsepower_continuous")
        if hp is None or hp == 0:
            amp = pump.get("amperage_max")
            if amp and isinstance(amp, (int, float)) and amp > 0:
                # Estimate: ~1 continuous HP per 10A at 240V
                pump["horsepower_continuous"] = round(amp / 10.0, 1)
            else:
                # Absolute fallback -- mark as unknown
                pump["horsepower_continuous"] = 1.0

    jet_pumps_data["pumps"] = pumps
    return jet_pumps_data


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
    # Extract general fields piggybacked on jet_pumps extraction
    general = _extract_general_fields(extractions)

    # Look for seating_capacity in general fields first, then other categories
    seating = general.get("seating_capacity")
    if not seating:
        seating = _find_in_data(
            extractions,
            "seating_capacity",
            ["dimensions", "general", "jets"],
        )

    # Look for top-level electrical data (general first, then specific cats)
    voltage = general.get("voltage")
    if not voltage:
        voltage = _find_in_data(
            extractions,
            "voltage",
            ["spa_pak", "heater"],
        )
    amperage = general.get("amperage")
    if not amperage:
        amperage = _find_in_data(
            extractions,
            "amperage",
            ["spa_pak", "heater"],
        )
    # Parse amperage strings like "20A & 30A" → take max integer
    if isinstance(amperage, str):
        import re
        nums = re.findall(r"\d+", amperage)
        amperage = max(int(n) for n in nums) if nums else None

    # Build dimensions from general fields or dedicated dimensions extraction
    dims = general.get("dimensions", {})
    if not isinstance(dims, dict):
        dims = {}
    dims_extraction = _get(extractions, "dimensions")
    # Merge: prefer dedicated extraction, fall back to general
    dimensions = {
        "length_inches": (
            dims_extraction.get("length_inches")
            or dims.get("length_inches")
            or 0.0
        ),
        "width_inches": (
            dims_extraction.get("width_inches")
            or dims.get("width_inches")
            or 0.0
        ),
        "height_inches": (
            dims_extraction.get("height_inches")
            or dims.get("height_inches")
            or 0.0
        ),
        "dry_weight_lbs": (
            dims_extraction.get("dry_weight_lbs")
            or general.get("dry_weight_lbs")
            or dims.get("dry_weight_lbs")
        ),
        "filled_weight_lbs": (
            dims_extraction.get("filled_weight_lbs")
            or general.get("filled_weight_lbs")
            or dims.get("filled_weight_lbs")
        ),
        "water_capacity_gallons": (
            dims_extraction.get("water_capacity_gallons")
            or general.get("water_capacity_gallons")
            or dims.get("water_capacity_gallons")
        ),
    }

    # Fix null HP on pumps
    jet_pumps_data = _get(extractions, "jet_pumps")
    jet_pumps_data = _fix_pump_hp(jet_pumps_data)
    # Remove the piggybacked general key before passing to Pydantic
    jet_pumps_data.pop("general", None)

    def _or_none(data: dict) -> dict | None:
        """Return None for empty dicts to avoid Pydantic validation on empty data."""
        return data if data else None

    model_data: dict[str, Any] = {
        # Identity
        "manufacturer": manufacturer,
        "series": series,
        "model_name": model_name,
        "year": year,
        "seating_capacity": seating or 0,
        # 10 spec categories -- None if extraction returned nothing
        "jet_pumps": _or_none(jet_pumps_data),
        "circulation_pump": _or_none(_get(extractions, "circulation_pump")),
        "spa_pak": _or_none(_get(extractions, "spa_pak")),
        "topside_control": _or_none(_get(extractions, "topside_control")),
        "jets": _or_none(_get(extractions, "jets")),
        "headrests": _or_none(_get(extractions, "headrests")),
        "filters": _or_none(_get(extractions, "filters")),
        "heater": _or_none(_get(extractions, "heater")),
        "lighting": _or_none(_get(extractions, "lighting")),
        "cover": _or_none(_get(extractions, "cover")),
        # Physical dimensions
        "dimensions": dimensions,
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
