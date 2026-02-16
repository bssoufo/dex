"""Not-available field identification and classification.

Identifies fields that are confirmed unavailable from any source document:
part numbers (not in PDFs or manufacturer websites), universally-null fields,
and manufacturer-specific gaps.

Usage:
    from backend.src.etl.verify.not_available import build_not_available_list
    from backend.src.etl.verify.checks import load_all_models

    models = load_all_models()
    for model in models:
        na_fields = build_not_available_list(model)
        print(f"{model.model_name}: {len(na_fields)} not-available fields")
"""

from __future__ import annotations

from backend.src.schema.models import SpaModel
from backend.src.schema.parts import PartReference

from .checks import _is_category_all_null


# Fields that are null across ALL 19 models -- confirmed not available
# from any source document (PDF or website).
UNIVERSAL_NULLS = [
    "jet_pumps.total_brake_horsepower",
    "circulation_pump.wattage",
    "jets.jetpak_options",
    "jets.therapy_jet_count",
    "jets.max_jet_count",
    "heater.material",
    "cover.thickness",
]


def build_not_available_list(model: SpaModel) -> list[str]:
    """Identify fields confirmed not available in any source document.

    Three categories:
    1. All part_number fields (confirmed not in PDFs or manufacturer websites)
    2. Universally-null fields (null across all 19 models in source docs)
    3. Manufacturer-specific gaps (e.g., Bullfrog heater specs not in manuals)

    Returns:
        Sorted list of dot-path field names that are not available.
    """
    not_available: list[str] = []

    # 1. Part number fields -- all confirmed unavailable from sources
    not_available.extend(_find_null_part_numbers(model))

    # 2. Universally null fields (not in ANY of the 19 models' sources)
    for field_path in UNIVERSAL_NULLS:
        if _is_null_at_path(model, field_path):
            not_available.append(field_path)

    # 3. Manufacturer-specific: Bullfrog heater (not in manuals)
    if model.manufacturer.value == "bullfrog" and model.heater is not None:
        if _is_all_null_simple(model.heater):
            not_available.append("heater.*")

    return sorted(set(not_available))


def _find_null_part_numbers(model: SpaModel) -> list[str]:
    """Walk the model tree and return field paths for all null PartReference fields.

    Checks:
    - Flat categories: circulation_pump, spa_pak, topside_control, heater, cover
      -> check category.part_number
    - List categories: jet_pumps.pumps, jets.jets_by_type, headrests.headrests,
      filters.filters, lighting.lights
      -> iterate list items and check each item.part_number
    """
    paths: list[str] = []

    # --- Flat categories with direct part_number ---
    _FLAT_CATEGORIES = [
        ("circulation_pump", "part_number"),
        ("spa_pak", "part_number"),
        ("topside_control", "part_number"),
        ("heater", "part_number"),
        ("cover", "part_number"),
    ]

    for cat_name, field_name in _FLAT_CATEGORIES:
        cat = getattr(model, cat_name, None)
        if cat is None:
            continue
        part_ref = getattr(cat, field_name, None)
        if part_ref is None:
            paths.append(f"{cat_name}.{field_name}")

    # --- List categories with indexed part_number ---
    _LIST_CATEGORIES = [
        ("jet_pumps", "pumps"),
        ("jets", "jets_by_type"),
        ("headrests", "headrests"),
        ("filters", "filters"),
        ("lighting", "lights"),
    ]

    for cat_name, list_field in _LIST_CATEGORIES:
        cat = getattr(model, cat_name, None)
        if cat is None:
            continue
        items = getattr(cat, list_field, [])
        for i, item in enumerate(items):
            part_ref = getattr(item, "part_number", None)
            if part_ref is None:
                paths.append(f"{cat_name}.{list_field}[{i}].part_number")

    return paths


def _is_null_at_path(model: SpaModel, field_path: str) -> bool:
    """Check if a dot-separated field path resolves to None on the model.

    Supports paths like "jet_pumps.total_brake_horsepower" and
    "circulation_pump.wattage".
    """
    parts = field_path.split(".")
    obj: object = model
    for part in parts:
        if obj is None:
            return True
        obj = getattr(obj, part, None)
    return obj is None


def _is_all_null_simple(category: object) -> bool:
    """Check if all non-boolean, non-default fields in a category are None/empty.

    Simpler version of _is_category_all_null for manufacturer-specific checks.
    """
    return _is_category_all_null(category)


def classify_null_fields(models: list[SpaModel]) -> dict:
    """Return classification of all null fields across all models.

    Returns dict with keys:
        'part_numbers': count of null part_number fields across all models
        'universal_nulls': count of universal null fields across all models
        'manufacturer_specific': count of manufacturer-specific gaps
        'total': total not-available fields across all models
    """
    part_numbers = 0
    universal_nulls = 0
    manufacturer_specific = 0

    for model in models:
        # Count part number nulls
        part_numbers += len(_find_null_part_numbers(model))

        # Count universal nulls
        for field_path in UNIVERSAL_NULLS:
            if _is_null_at_path(model, field_path):
                universal_nulls += 1

        # Count manufacturer-specific
        if model.manufacturer.value == "bullfrog" and model.heater is not None:
            if _is_all_null_simple(model.heater):
                manufacturer_specific += 1

    total = part_numbers + universal_nulls + manufacturer_specific
    return {
        "part_numbers": part_numbers,
        "universal_nulls": universal_nulls,
        "manufacturer_specific": manufacturer_specific,
        "total": total,
    }
