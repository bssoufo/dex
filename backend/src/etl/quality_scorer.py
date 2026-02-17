"""Data quality scorer for spa model JSON files.

Reads each extracted JSON, calculates completeness scores for key spec
categories, and writes the data_quality field back to the file.

Usage:
    uv run python -m src.etl.quality_scorer
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import DATA_OUTPUT_DIR

# Key fields per category that we consider "important" for completeness scoring.
# Part numbers are excluded (not on manufacturer websites).
SCORED_FIELDS: dict[str, list[str]] = {
    "top_level": [
        "seating_capacity",
        "voltage",
        "amperage",
    ],
    "dimensions": [
        "length_inches",
        "width_inches",
        "height_inches",
        "dry_weight_lbs",
        "filled_weight_lbs",
        "water_capacity_gallons",
    ],
    "jet_pumps": [
        "pumps",  # list non-empty
    ],
    "circulation_pump": [
        "model_name",
        "is_dedicated",
    ],
    "jets": [
        "total_jet_count",
        "jet_system_type",
    ],
    "heater": [
        "wattage",
        "voltage",
    ],
    "filters": [
        "filters",  # list non-empty
    ],
    "lighting": [
        "lights",  # list non-empty
    ],
    "cover": [],  # Optional, low weight
    "spa_pak": [
        "voltage",
    ],
}


def _is_populated(value: object) -> bool:
    """Check if a value is meaningfully populated (not null, not 0, not empty)."""
    if value is None:
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    return True


def score_model(data: dict) -> dict:
    """Calculate data quality metrics for a spa model.

    Returns a DataQuality-compatible dict with:
    - completeness_pct: 0-100 score of key fields populated
    - not_available_fields: list of key fields that are null/empty
    - verification_date: today's date
    - verified_by: "web_extraction_pipeline"
    """
    total_fields = 0
    populated_fields = 0
    missing_fields: list[str] = []

    # Top-level fields
    for field in SCORED_FIELDS["top_level"]:
        total_fields += 1
        if _is_populated(data.get(field)):
            populated_fields += 1
        else:
            missing_fields.append(field)

    # Dimensions
    dims = data.get("dimensions", {})
    if isinstance(dims, dict):
        for field in SCORED_FIELDS["dimensions"]:
            total_fields += 1
            if _is_populated(dims.get(field)):
                populated_fields += 1
            else:
                missing_fields.append(f"dimensions.{field}")

    # Nested categories
    for category in ["jet_pumps", "circulation_pump", "jets", "heater",
                     "filters", "lighting", "spa_pak"]:
        cat_data = data.get(category)
        if not isinstance(cat_data, dict):
            for field in SCORED_FIELDS.get(category, []):
                total_fields += 1
                missing_fields.append(f"{category}.{field}")
            continue

        for field in SCORED_FIELDS.get(category, []):
            total_fields += 1
            if _is_populated(cat_data.get(field)):
                populated_fields += 1
            else:
                missing_fields.append(f"{category}.{field}")

    # Pump detail bonus: check if pumps have HP data
    pumps = (data.get("jet_pumps") or {}).get("pumps", [])
    if pumps:
        total_fields += 1
        has_hp = any(
            p.get("horsepower_continuous") is not None
            for p in pumps if isinstance(p, dict)
        )
        if has_hp:
            populated_fields += 1
        else:
            missing_fields.append("jet_pumps.pumps[].horsepower_continuous")

    completeness = round((populated_fields / total_fields * 100), 1) if total_fields > 0 else 0.0

    return {
        "verification_date": date.today().isoformat(),
        "verified_by": "web_extraction_pipeline",
        "not_available_fields": missing_fields,
        "anomalies_reviewed": [],
        "completeness_pct": completeness,
    }


def run_quality_scoring() -> dict[str, float]:
    """Score all JSON files in the data directory.

    Returns a dict mapping model file names to their completeness scores.
    """
    scores: dict[str, float] = {}

    for json_file in sorted(DATA_OUTPUT_DIR.rglob("*.json")):
        if json_file.name.endswith("-RAW.json"):
            continue

        data = json.loads(json_file.read_text(encoding="utf-8"))
        quality = score_model(data)
        data["data_quality"] = quality

        json_file.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

        model_name = data.get("model_name", json_file.stem)
        mfr = data.get("manufacturer", "unknown")
        scores[f"{mfr}/{model_name}"] = quality["completeness_pct"]
        print(
            f"  {mfr:12s} {model_name:15s}: "
            f"{quality['completeness_pct']:5.1f}% "
            f"({len(quality['not_available_fields'])} gaps)"
        )

    return scores


if __name__ == "__main__":
    print("DEX Data Quality Scoring")
    print("=" * 60)
    scores = run_quality_scoring()
    print(f"\n{'=' * 60}")
    avg = sum(scores.values()) / len(scores) if scores else 0
    print(f"Average completeness: {avg:.1f}%")
    print(f"Models scored: {len(scores)}")
