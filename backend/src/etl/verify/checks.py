"""Automated verification checks for spa model data.

Runs a suite of consistency, completeness, and plausibility checks
against validated SpaModel instances. Designed to flag anomalies for
targeted human review rather than requiring manual review of all fields.

Usage:
    from backend.src.etl.verify.checks import load_all_models, run_all_checks

    models = load_all_models()
    for model in models:
        result = run_all_checks(model)
        for a in result.anomalies:
            print(f"[{a.severity}] {a.model_name}/{a.category}: {a.message}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...schema.models import (
    CoverSpec,
    HeaterSpec,
    JetPumpSpecs,
    SpaModel,
    SpaPakSpec,
)

# ---------------------------------------------------------------------------
# Extraction-time cross-field checks (operate on raw dicts, pre-Pydantic)
# ---------------------------------------------------------------------------


@dataclass
class ExtractionError:
    """An error found during post-extraction cross-field validation."""

    category: str
    message: str


def check_jet_sum_consistency(data: dict) -> list[ExtractionError]:
    """Error if sum of jets_by_type quantities differs from total by > 2."""
    errors: list[ExtractionError] = []
    jets = data.get("jets")
    if not isinstance(jets, dict):
        return errors

    total = jets.get("total_jet_count")
    by_type = jets.get("jets_by_type")
    if total is None or not isinstance(by_type, list) or not by_type:
        return errors

    type_sum = sum(j.get("quantity") or 0 for j in by_type if isinstance(j, dict))
    if abs(total - type_sum) > 2:
        errors.append(ExtractionError(
            category="jets",
            message=(
                f"Jet count mismatch: total_jet_count={total} but "
                f"sum of jets_by_type={type_sum} (diff={abs(total - type_sum)})"
            ),
        ))
    return errors


def check_pump_count_reasonable(data: dict) -> list[ExtractionError]:
    """Error if pump count is outside 1-4 range."""
    errors: list[ExtractionError] = []
    pumps_data = data.get("jet_pumps")
    if not isinstance(pumps_data, dict):
        return errors

    pumps = pumps_data.get("pumps")
    if not isinstance(pumps, list):
        return errors

    count = len(pumps)
    if count < 1 or count > 4:
        errors.append(ExtractionError(
            category="jet_pumps",
            message=f"Pump count {count} outside reasonable range 1-4",
        ))
    return errors


def check_dimension_ranges(data: dict) -> list[ExtractionError]:
    """Error if dimensions are outside plausible ranges."""
    errors: list[ExtractionError] = []
    dims = data.get("dimensions")
    if not isinstance(dims, dict):
        return errors

    checks = [
        ("length_inches", 40.0, 150.0),
        ("width_inches", 40.0, 150.0),
        ("height_inches", 20.0, 60.0),
    ]
    for field, lo, hi in checks:
        val = dims.get(field)
        if val is not None and (val < lo or val > hi):
            errors.append(ExtractionError(
                category="dimensions",
                message=f"{field}={val} outside range [{lo}, {hi}]",
            ))
    return errors


def check_jet_count_range(data: dict) -> list[ExtractionError]:
    """Error if total jet count is outside 5-100 (catches hallucinations)."""
    errors: list[ExtractionError] = []
    jets = data.get("jets")
    if not isinstance(jets, dict):
        return errors

    total = jets.get("total_jet_count")
    if total is not None and (total < 5 or total > 100):
        errors.append(ExtractionError(
            category="jets",
            message=f"total_jet_count={total} outside plausible range [5, 100]",
        ))
    return errors


def get_extraction_errors(data: dict) -> list[ExtractionError]:
    """Run all cross-field checks and return error-severity issues.

    These errors are used by the pipeline to trigger targeted re-extraction
    of failing categories with explicit error context.
    """
    errors: list[ExtractionError] = []
    errors.extend(check_jet_sum_consistency(data))
    errors.extend(check_pump_count_reasonable(data))
    errors.extend(check_dimension_ranges(data))
    errors.extend(check_jet_count_range(data))
    return errors


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class Anomaly:
    """A single anomaly found during verification."""

    model_name: str
    category: str
    check_name: str
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass
class VerificationResult:
    """Result of running all verification checks on a single model."""

    model_name: str
    manufacturer: str
    checks_passed: int = 0
    checks_failed: int = 0
    anomalies: list[Anomaly] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Plausible value ranges (inline, not imported from validators.py which
# expects CategoryExtraction, not SpaModel)
# ---------------------------------------------------------------------------

_RANGES: dict[str, tuple[float, float]] = {
    "seating_capacity": (2, 10),
    "length_inches": (40.0, 150.0),
    "width_inches": (40.0, 150.0),
    "height_inches": (20.0, 60.0),
    "horsepower": (0.5, 10.0),
    "jet_count": (5, 200),
    "wattage": (1000, 6000),
}


# ---------------------------------------------------------------------------
# Check Functions (each takes SpaModel, returns list[Anomaly])
# ---------------------------------------------------------------------------


def check_voltage_consistency(model: SpaModel) -> list[Anomaly]:
    """Compare top-level voltage, spa_pak.voltage, and heater.voltage.

    If any differ, return anomaly with severity="error".
    Expected to flag: Jetsetter LX, Prodigy (spa_pak 115V vs 230V top-level).
    """
    anomalies: list[Anomaly] = []

    top_v = model.voltage
    spa_pak_v = model.spa_pak.voltage if model.spa_pak else None
    heater_v = model.heater.voltage if model.heater else None

    voltages = {v for v in [top_v, spa_pak_v, heater_v] if v is not None}
    if len(voltages) > 1:
        anomalies.append(
            Anomaly(
                model_name=model.model_name,
                category="electrical",
                check_name="voltage_consistency",
                severity="error",
                message=(
                    f"Voltage mismatch: top-level={top_v}, "
                    f"spa_pak={spa_pak_v}, heater={heater_v}"
                ),
            )
        )

    return anomalies


def check_cover_dimensions(model: SpaModel) -> list[Anomaly]:
    """Check if cover dimensions appear swapped relative to spa dimensions.

    If cover length matches spa width AND cover width matches spa length
    (within 1 inch), flag as "dimensions appear swapped" with severity="error".
    Expected to flag: M6, M9.
    """
    anomalies: list[Anomaly] = []

    if model.cover is None or model.dimensions is None:
        return anomalies

    cover_l = model.cover.length_inches
    cover_w = model.cover.width_inches
    spa_l = model.dimensions.length_inches
    spa_w = model.dimensions.width_inches

    if cover_l is None or cover_w is None:
        return anomalies

    # Check if cover dims are swapped: cover_l ~ spa_w AND cover_w ~ spa_l
    # AND they are actually different from the spa dims (not just equal)
    l_matches_w = abs(cover_l - spa_w) < 1.0
    w_matches_l = abs(cover_w - spa_l) < 1.0
    is_swapped = abs(cover_l - spa_l) > 1.0 or abs(cover_w - spa_w) > 1.0

    if l_matches_w and w_matches_l and is_swapped:
        anomalies.append(
            Anomaly(
                model_name=model.model_name,
                category="cover",
                check_name="cover_dimensions",
                severity="error",
                message=(
                    f"Cover dimensions ({cover_l}x{cover_w}) appear swapped "
                    f"vs spa dimensions ({spa_l}x{spa_w})"
                ),
            )
        )

    return anomalies


def check_jet_counts(model: SpaModel) -> list[Anomaly]:
    """Compare total_jet_count to sum of jets_by_type quantities.

    If total != sum, flag with severity="warning" (may be legitimate
    counting differences between primary jets and all jet types).
    Expected to flag: Envoy, Grandee, Jetsetter, Altamar, Aspen, Cameo.
    """
    anomalies: list[Anomaly] = []

    if model.jets is None:
        return anomalies

    total = model.jets.total_jet_count
    jets_by_type = model.jets.jets_by_type

    if total is None or not jets_by_type:
        return anomalies

    sum_by_type = sum(j.quantity for j in jets_by_type)

    if total != sum_by_type:
        anomalies.append(
            Anomaly(
                model_name=model.model_name,
                category="jets",
                check_name="jet_counts",
                severity="warning",
                message=(
                    f"Jet count mismatch: total_jet_count={total} "
                    f"vs sum of jets_by_type={sum_by_type}"
                ),
            )
        )

    return anomalies


def _is_category_all_null(category: object) -> bool:
    """Check if a category model has all meaningful fields as None/empty.

    Skips boolean fields (shared_with_series, is_dedicated) and focuses on
    string, numeric, and PartReference fields. For list fields (pumps,
    filters, headrests, lights, jets_by_type, features), empty list counts
    as "empty".
    """
    if category is None:
        return True

    # Fields to skip in nullity check (boolean flags with defaults)
    _SKIP_FIELDS = {
        "shared_with_series",
        "is_dedicated",
        "requires_gfci",
        "jet_system_type",  # has default value FIXED
        "frequency_hz",  # has default 60
    }

    for field_name, value in category.__dict__.items():
        if field_name.startswith("_"):
            continue
        if field_name in _SKIP_FIELDS:
            continue

        # Check if the value is "meaningful" (non-null, non-empty)
        if value is None:
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if isinstance(value, bool):
            continue

        # Found a non-null, non-empty, non-boolean field
        return False

    return True


def check_missing_categories(model: SpaModel) -> list[Anomaly]:
    """Check all 10 category fields on SpaModel for completeness.

    - If a category is None: severity="warning" with "category entirely missing"
    - If a category exists but all meaningful fields are None/empty:
      severity="info" with "category present but all fields null"

    Expected NULL: Marin filters, Jetsetter LX lighting
    Expected EMPTY: M6/M7/M8/M9 heater, M8/M9 spa_pak
    """
    anomalies: list[Anomaly] = []

    categories = {
        "jet_pumps": model.jet_pumps,
        "circulation_pump": model.circulation_pump,
        "spa_pak": model.spa_pak,
        "topside_control": model.topside_control,
        "jets": model.jets,
        "headrests": model.headrests,
        "filters": model.filters,
        "heater": model.heater,
        "lighting": model.lighting,
        "cover": model.cover,
    }

    for cat_name, cat_value in categories.items():
        if cat_value is None:
            anomalies.append(
                Anomaly(
                    model_name=model.model_name,
                    category=cat_name,
                    check_name="missing_categories",
                    severity="warning",
                    message="Category entirely missing (None)",
                )
            )
        elif _is_category_all_null(cat_value):
            anomalies.append(
                Anomaly(
                    model_name=model.model_name,
                    category=cat_name,
                    check_name="missing_categories",
                    severity="info",
                    message="Category present but all fields null/empty",
                )
            )

    return anomalies


def check_source_tracking(model: SpaModel) -> list[Anomaly]:
    """Check source document coverage and verification status.

    - If source_documents is empty: severity="error"
    - If all source_documents have verified_by=None: severity="info"
      (expected pre-verification)
    """
    anomalies: list[Anomaly] = []

    if not model.source_documents:
        anomalies.append(
            Anomaly(
                model_name=model.model_name,
                category="source_documents",
                check_name="source_tracking",
                severity="error",
                message="No source documents recorded",
            )
        )
        return anomalies

    all_unverified = all(
        src.verified_by is None for src in model.source_documents
    )
    if all_unverified:
        anomalies.append(
            Anomaly(
                model_name=model.model_name,
                category="source_documents",
                check_name="source_tracking",
                severity="info",
                message=(
                    f"All {len(model.source_documents)} source documents "
                    f"unverified (verified_by is None)"
                ),
            )
        )

    return anomalies


def check_ranges(model: SpaModel) -> list[Anomaly]:
    """Check numeric values against plausible ranges.

    Ranges: seating_capacity (2-10), dimensions (40-150 L/W, 20-60 H),
    horsepower (0.5-10), jet_count (5-200), wattage (1000-6000).
    """
    anomalies: list[Anomaly] = []

    def _check(
        value: float | int | None,
        field: str,
        range_key: str,
        context: str,
    ) -> None:
        if value is None:
            return
        lo, hi = _RANGES[range_key]
        num = float(value)
        if num < lo or num > hi:
            anomalies.append(
                Anomaly(
                    model_name=model.model_name,
                    category=context,
                    check_name="ranges",
                    severity="warning",
                    message=(
                        f"{field}={num} outside plausible range "
                        f"[{lo}, {hi}]"
                    ),
                )
            )

    # Seating capacity
    _check(model.seating_capacity, "seating_capacity", "seating_capacity", "identity")

    # Dimensions
    if model.dimensions:
        _check(model.dimensions.length_inches, "length_inches", "length_inches", "dimensions")
        _check(model.dimensions.width_inches, "width_inches", "width_inches", "dimensions")
        _check(model.dimensions.height_inches, "height_inches", "height_inches", "dimensions")

    # Jet pump horsepower
    if model.jet_pumps and model.jet_pumps.pumps:
        for pump in model.jet_pumps.pumps:
            if pump.horsepower_continuous is not None:
                _check(
                    pump.horsepower_continuous,
                    f"pump[{pump.position}].horsepower_continuous",
                    "horsepower",
                    "jet_pumps",
                )

    # Jet count
    if model.jets and model.jets.total_jet_count is not None:
        _check(model.jets.total_jet_count, "total_jet_count", "jet_count", "jets")

    # Heater wattage
    if model.heater and model.heater.wattage is not None:
        _check(model.heater.wattage, "wattage", "wattage", "heater")

    return anomalies


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_all_checks(model: SpaModel) -> VerificationResult:
    """Run all verification checks against a single model."""
    result = VerificationResult(
        model_name=model.model_name,
        manufacturer=model.manufacturer.value,
    )
    all_checks = [
        check_voltage_consistency,
        check_cover_dimensions,
        check_jet_counts,
        check_missing_categories,
        check_source_tracking,
        check_ranges,
    ]
    for check_fn in all_checks:
        found = check_fn(model)
        if found:
            result.checks_failed += 1
            result.anomalies.extend(found)
        else:
            result.checks_passed += 1
    return result


# ---------------------------------------------------------------------------
# Loader utility
# ---------------------------------------------------------------------------


def load_all_models() -> list[SpaModel]:
    """Load and validate all 19 JSON data files."""
    data_dir = Path(__file__).resolve().parents[2] / "data"
    models: list[SpaModel] = []
    for f in sorted(data_dir.rglob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        models.append(SpaModel.model_validate(data))
    return models
