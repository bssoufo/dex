"""Merge scraped web data into existing JSON model files.

Enforces the critical rule: web data ONLY fills null/None/0 fields.
NEVER overwrites a non-null value from PDF extraction. PDF is the
authoritative source; web data is supplementary.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

from src.etl.config import DATA_OUTPUT_DIR
from src.etl.scrape.parsers.base import ScrapedSpecs

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a series/model name to a filesystem-safe slug.

    Matches the slugify logic in ``backend/src/etl/output/writer.py``.

    Examples::

        >>> _slugify("880 Series")
        '880-series'
        >>> _slugify("Jetsetter LX")
        'jetsetter-lx'
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def resolve_json_path(
    manufacturer: str,
    series: str,
    model_name: str,
    year: int = 2026,
) -> Path:
    """Resolve the expected JSON file path for a spa model.

    Uses the same directory layout as ``output.writer.write_model_json``:
    ``DATA_OUTPUT_DIR / manufacturer / slugify(series) / slugify(model)-year.json``

    Args:
        manufacturer: Manufacturer key (e.g. "sundance").
        series: Series name (e.g. "880 Series").
        model_name: Model name (e.g. "Aspen").
        year: Model year. Defaults to 2026.

    Returns:
        Path to the JSON file (may not exist).
    """
    return (
        DATA_OUTPUT_DIR
        / manufacturer
        / _slugify(series)
        / f"{_slugify(model_name)}-{year}.json"
    )


# Field mappings from ScrapedSpecs attributes to JSON paths.
# Each entry: (scraped_attr, json_path_parts, nested_section)
# json_path_parts is a list of keys to traverse the JSON dict.
_FIELD_MAPPINGS: list[tuple[str, list[str]]] = [
    ("length_inches", ["dimensions", "length_inches"]),
    ("width_inches", ["dimensions", "width_inches"]),
    ("height_inches", ["dimensions", "height_inches"]),
    ("dry_weight_lbs", ["dimensions", "dry_weight_lbs"]),
    ("filled_weight_lbs", ["dimensions", "filled_weight_lbs"]),
    ("water_capacity_gallons", ["dimensions", "water_capacity_gallons"]),
    ("seating_capacity", ["seating_capacity"]),
    ("total_jet_count", ["jets", "total_jet_count"]),
    ("filtration_area_sqft", ["filters", "filters", 0, "filtration_area_sqft"]),
    ("heater_wattage", ["heater", "wattage"]),
    ("electrical_volts", ["voltage"]),
    ("electrical_amps", ["amperage"]),
    ("diverter_valves", ["jet_pumps", "diverter_valves"]),
]


def _get_nested(data: dict, path: list) -> object:
    """Safely traverse a nested dict/list by path keys.

    Returns the value at the path, or a sentinel ``_MISSING`` if any
    intermediate key is missing or the container is None.
    """
    current = data
    for key in path[:-1]:
        if current is None:
            return _MISSING
        if isinstance(key, int):
            if not isinstance(current, list) or key >= len(current):
                return _MISSING
            current = current[key]
        else:
            if not isinstance(current, dict) or key not in current:
                return _MISSING
            current = current[key]

    if current is None:
        return _MISSING

    final_key = path[-1]
    if isinstance(final_key, int):
        if not isinstance(current, list) or final_key >= len(current):
            return _MISSING
        return current[final_key]
    if not isinstance(current, dict):
        return _MISSING
    return current.get(final_key, _MISSING)


def _set_nested(data: dict, path: list, value: object) -> None:
    """Set a value in a nested dict/list by path keys.

    Assumes all intermediate containers already exist (they should,
    since the JSON was produced by Pydantic serialization).
    """
    current = data
    for key in path[:-1]:
        if isinstance(key, int):
            current = current[key]
        else:
            current = current[key]

    final_key = path[-1]
    if isinstance(final_key, int):
        current[final_key] = value
    else:
        current[final_key] = value


class _MissingSentinel:
    """Sentinel indicating a path does not exist in the JSON."""

    def __repr__(self) -> str:
        return "<MISSING>"


_MISSING = _MissingSentinel()


def _is_empty(value: object) -> bool:
    """Check if a value should be considered 'empty' (eligible to fill).

    Empty means None, 0, or 0.0. These are fields the PDF extraction
    could not populate.
    """
    if value is None or value is _MISSING:
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False


def _field_path_str(path: list) -> str:
    """Convert a JSON path list to a dot-separated string for logging."""
    return ".".join(str(p) for p in path)


def merge_scraped_into_model(
    json_path: Path,
    scraped: ScrapedSpecs,
) -> dict:
    """Merge scraped web data into an existing model JSON file.

    CRITICAL RULE: Web data ONLY fills null/None/0 fields. NEVER
    overwrites a non-null, non-zero value from PDF extraction.

    Args:
        json_path: Path to the existing JSON file.
        scraped: ScrapedSpecs instance with web-extracted data.

    Returns:
        A report dict with keys: model_name, fields_updated,
        fields_kept, fields_missing, source_url.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    model_name = data.get("model_name", json_path.stem)
    fields_updated: list[str] = []
    fields_kept: list[str] = []
    fields_missing: list[str] = []

    for scraped_attr, json_path_parts in _FIELD_MAPPINGS:
        scraped_value = getattr(scraped, scraped_attr)
        field_key = _field_path_str(json_path_parts)

        # No scraped value available
        if scraped_value is None:
            existing = _get_nested(data, json_path_parts)
            if _is_empty(existing):
                fields_missing.append(field_key)
            # If existing has data but scraped is None, nothing to do
            continue

        # Check if the nested path exists in the JSON
        existing = _get_nested(data, json_path_parts)
        if isinstance(existing, _MissingSentinel):
            # The section does not exist in the JSON (e.g. no jets section)
            logger.debug(
                "SKIPPED %s: section not present in JSON for %s",
                field_key,
                model_name,
            )
            fields_missing.append(field_key)
            continue

        # Existing has non-null, non-zero data -- preserve it
        if not _is_empty(existing):
            logger.info(
                "KEPT existing %s=%s (web had %s) for %s",
                field_key,
                existing,
                scraped_value,
                model_name,
            )
            fields_kept.append(field_key)
            continue

        # Existing is null/0 -- fill with scraped value
        _set_nested(data, json_path_parts, scraped_value)
        logger.info(
            "FILLED %s=%s (was %s) for %s",
            field_key,
            scraped_value,
            existing,
            model_name,
        )
        fields_updated.append(field_key)

    # If any fields were updated, append a website SourceReference
    if fields_updated:
        source_ref = {
            "source_type": "website",
            "url": scraped.source_url,
            "document_name": None,
            "page_number": None,
            "section": None,
            "accessed_date": date.today().isoformat(),
            "verified_by": None,
            "verified_date": None,
        }
        source_docs = data.setdefault("source_documents", [])
        source_docs.append(source_ref)

        # Write updated JSON back
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

        logger.info(
            "Updated %s: %d fields filled, %d kept, %d missing",
            model_name,
            len(fields_updated),
            len(fields_kept),
            len(fields_missing),
        )
    else:
        logger.info(
            "No updates for %s: %d kept, %d missing",
            model_name,
            len(fields_kept),
            len(fields_missing),
        )

    return {
        "model_name": model_name,
        "fields_updated": fields_updated,
        "fields_kept": fields_kept,
        "fields_missing": fields_missing,
        "source_url": scraped.source_url,
    }
