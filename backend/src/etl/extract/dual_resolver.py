"""Field-level merge of Gemini extraction and OpenAI review.

Gemini extracts → OpenAI reviews → field-level merge produces the final
result with a detailed change report.

Data flow:
    gemini_data, review_data → merge_reviewed()
        → review_data is the base (primary result)
        → _walk_and_diff() builds change report
        → missing keys in review fall back to gemini
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Keys used for stable sorting of list-of-dicts before comparison
_SORT_KEYS = ("position", "jet_type", "type", "location", "filter_type")

# Scalar top-level fields (not categories or dimensions)
_SCALAR_FIELDS = ("seating_capacity", "voltage", "amperage")


@dataclass
class FieldChange:
    """A single field-level change between Gemini and review."""

    category: str
    field_path: str
    gemini_value: object
    review_value: object
    change_type: str  # "confirmed", "corrected", "filled", "nulled"


@dataclass
class ReviewReport:
    """Summary of field-level merge for a single model."""

    model_name: str
    confirmed: int = 0
    corrected: int = 0
    filled: int = 0
    nulled: int = 0
    changes: list[FieldChange] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalization helpers (kept from v1)
# ---------------------------------------------------------------------------

def normalize_for_comparison(value):
    """Normalize a value for deep comparison.

    - Lowercase strings
    - Round floats to 1 decimal
    - Convert "null"/"None"/"n/a" strings → None
    - Treat [] and None as equivalent
    - Sort list-of-dicts by stable key
    """
    if value is None:
        return None

    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("null", "none", "n/a", ""):
            return None
        return lower

    if isinstance(value, float):
        return round(value, 1)

    if isinstance(value, int):
        return value

    if isinstance(value, bool):
        return value

    if isinstance(value, list):
        if len(value) == 0:
            return None  # [] equivalent to None
        normalized = [normalize_for_comparison(item) for item in value]
        # Sort list-of-dicts by stable key if applicable
        if all(isinstance(item, dict) for item in normalized):
            normalized = _sort_dict_list(normalized)
        return normalized

    if isinstance(value, dict):
        return {k: normalize_for_comparison(v) for k, v in value.items()}

    return value


def _sort_dict_list(items: list[dict]) -> list[dict]:
    """Sort a list of dicts by the first available stable key."""
    for key in _SORT_KEYS:
        if any(key in item for item in items):
            return sorted(items, key=lambda d: str(d.get(key, "")))
    return items


# ---------------------------------------------------------------------------
# Category comparison
# ---------------------------------------------------------------------------

def categories_match(cat_a, cat_b) -> bool:
    """Deep compare two category values after normalization."""
    norm_a = normalize_for_comparison(cat_a)
    norm_b = normalize_for_comparison(cat_b)
    return norm_a == norm_b


# ---------------------------------------------------------------------------
# Field-level merge
# ---------------------------------------------------------------------------

def _walk_and_diff(
    gemini: object,
    review: object,
    path: str,
    category: str,
    report: ReviewReport,
) -> None:
    """Recursively walk two structures and record field-level changes."""
    # Both are dicts → recurse into keys
    if isinstance(gemini, dict) and isinstance(review, dict):
        all_keys = set(list(gemini.keys()) + list(review.keys()))
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            g_val = gemini.get(key)
            r_val = review.get(key)
            _walk_and_diff(g_val, r_val, child_path, category, report)
        return

    # At a leaf — classify the change
    if categories_match(gemini, review):
        report.confirmed += 1
    elif gemini is None and review is not None:
        report.filled += 1
        report.changes.append(FieldChange(category, path, gemini, review, "filled"))
    elif gemini is not None and review is None:
        report.nulled += 1
        report.changes.append(FieldChange(category, path, gemini, review, "nulled"))
    else:
        report.corrected += 1
        report.changes.append(FieldChange(category, path, gemini, review, "corrected"))


def merge_reviewed(
    gemini_data: dict,
    review_data: dict,
    model_name: str,
) -> tuple[dict, ReviewReport]:
    """Merge Gemini extraction with OpenAI review at field level.

    The review_data is the primary result. If the review is missing a
    top-level key that Gemini has, we fall back to Gemini's value.

    Returns:
        (merged_dict, report)
    """
    report = ReviewReport(model_name=model_name)
    merged = {}

    # Union of all top-level keys
    all_keys = set(list(gemini_data.keys()) + list(review_data.keys()))

    for key in all_keys:
        g_val = gemini_data.get(key)
        r_val = review_data.get(key)

        if key in review_data:
            merged[key] = r_val
        else:
            # Review missing this key entirely → fall back to Gemini
            merged[key] = g_val
            logger.info("Review missing key '%s', falling back to Gemini", key)

        # Build the diff report
        category = key if key not in _SCALAR_FIELDS and key != "dimensions" else key
        _walk_and_diff(g_val, r_val, key, category, report)

    return merged, report
