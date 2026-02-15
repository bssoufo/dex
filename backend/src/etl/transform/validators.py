"""Post-extraction sanity checks for Claude extraction results.

These are *warnings*, not hard blockers.  The pipeline logs them and
continues -- the goal is to flag implausible values, low-confidence
extractions, and missing data so a human can prioritise review.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..extract.claude_extractor import CategoryExtraction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plausible value ranges for spa specifications
# ---------------------------------------------------------------------------

_RANGES: dict[str, tuple[float, float]] = {
    "horsepower": (0.5, 10.0),
    "jet_count": (5, 200),
    "length_inches": (40.0, 150.0),
    "width_inches": (40.0, 150.0),
    "height_inches": (20.0, 60.0),
    "wattage": (1000, 6000),
    "seating_capacity": (2, 10),
    "filter_area_sqft": (10.0, 500.0),
    "water_capacity_gallons": (100.0, 600.0),
}


def _check_range(
    value: Any,
    field: str,
    low: float,
    high: float,
    context: str,
) -> str | None:
    """Return a warning string if *value* is outside [low, high]."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num < low or num > high:
        return (
            f"[range] {context}: {field}={num} outside "
            f"plausible range [{low}, {high}]"
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_extraction(
    model_name: str,
    extractions: dict[str, CategoryExtraction],
) -> list[str]:
    """Run sanity checks on a set of category extractions.

    Args:
        model_name: Spa model name (for log context).
        extractions: Dict mapping category name to
            ``CategoryExtraction``.

    Returns:
        List of human-readable warning strings.  Empty list means
        all checks passed.
    """
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Confidence check
    # ------------------------------------------------------------------
    for cat_name, extraction in extractions.items():
        if extraction.confidence == "low":
            warnings.append(
                f"[confidence] {model_name}/{cat_name}: "
                f"low confidence extraction"
            )

    # ------------------------------------------------------------------
    # 2. Completeness check -- flag categories with no data
    # ------------------------------------------------------------------
    expected_categories = {
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
    }
    present = set(extractions.keys())
    missing = expected_categories - present
    for cat in sorted(missing):
        warnings.append(
            f"[missing] {model_name}/{cat}: category not extracted"
        )

    for cat_name, extraction in extractions.items():
        data = extraction.data
        if not data or all(v is None for v in data.values()):
            warnings.append(
                f"[empty] {model_name}/{cat_name}: "
                f"extraction returned no useful data"
            )

    # ------------------------------------------------------------------
    # 3. Range validation on known numeric fields
    # ------------------------------------------------------------------
    _range_checks = [
        ("jet_pumps", "horsepower_continuous", "horsepower"),
        ("jet_pumps", "total_brake_horsepower", "horsepower"),
        ("jets", "total_jet_count", "jet_count"),
        ("dimensions", "length_inches", "length_inches"),
        ("dimensions", "width_inches", "width_inches"),
        ("dimensions", "height_inches", "height_inches"),
        ("dimensions", "water_capacity_gallons", "water_capacity_gallons"),
        ("heater", "wattage", "wattage"),
        ("filters", "filtration_area_sqft", "filter_area_sqft"),
    ]

    for cat_name, field, range_key in _range_checks:
        extraction = extractions.get(cat_name)
        if extraction is None:
            continue
        data = extraction.data

        # For jet_pumps, check inside nested pumps list
        if cat_name == "jet_pumps" and field == "horsepower_continuous":
            pumps = data.get("pumps", [])
            if isinstance(pumps, list):
                for i, pump in enumerate(pumps):
                    if isinstance(pump, dict):
                        lo, hi = _RANGES[range_key]
                        w = _check_range(
                            pump.get(field),
                            field,
                            lo,
                            hi,
                            f"{model_name}/{cat_name}/pump[{i}]",
                        )
                        if w:
                            warnings.append(w)
            continue

        value = data.get(field)
        if value is not None:
            lo, hi = _RANGES[range_key]
            w = _check_range(
                value, field, lo, hi, f"{model_name}/{cat_name}"
            )
            if w:
                warnings.append(w)

    # ------------------------------------------------------------------
    # 4. Cross-category consistency (detect copy-paste errors)
    # ------------------------------------------------------------------
    if len(extractions) >= 3:
        data_strings = set()
        for extraction in extractions.values():
            data_strings.add(json.dumps(extraction.data, sort_keys=True))
        if len(data_strings) == 1 and len(extractions) > 1:
            warnings.append(
                f"[duplicate] {model_name}: all {len(extractions)} "
                f"categories returned identical data -- "
                f"possible copy-paste extraction error"
            )

    return warnings
