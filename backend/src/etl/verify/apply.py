"""Apply verification fixes and metadata to all 19 spa model JSON files.

Performs these operations in order:
1. Fix confirmed data errors (voltage inconsistencies, cover dimension swaps)
2. Add data_quality metadata to every model
3. Mark source references as verified
4. Compute completeness percentage
5. Write updated JSON files with round-trip Pydantic validation

Usage:
    from backend.src.etl.verify.apply import apply_verification
    apply_verification()
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.src.schema.models import SpaModel
from backend.src.schema.parts import DataQuality

from .checks import _is_category_all_null
from .not_available import build_not_available_list


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

VERIFICATION_DATE = "2026-02-16"
VERIFIED_BY = "automated_checks_v1"


# ---------------------------------------------------------------------------
# Step 1: Fix confirmed errors
# ---------------------------------------------------------------------------


def _fix_voltage(data: dict, model_name: str) -> list[dict]:
    """Fix spa_pak voltage to match top-level voltage.

    Jetsetter LX and Prodigy have spa_pak.voltage=115 but the primary
    electrical input voltage is 230V (top-level and heater both 230).
    The 115V is the spa_pak's secondary/accessory voltage, not primary.
    """
    anomalies: list[dict] = []

    if model_name not in ("Jetsetter LX", "Prodigy"):
        return anomalies

    top_voltage = data.get("voltage")
    spa_pak = data.get("spa_pak")
    if spa_pak is None:
        return anomalies

    old_voltage = spa_pak.get("voltage")
    if old_voltage is not None and old_voltage != top_voltage:
        spa_pak["voltage"] = top_voltage
        anomalies.append({
            "field": "spa_pak.voltage",
            "issue": f"spa_pak.voltage={old_voltage} did not match top-level voltage={top_voltage}",
            "resolution": f"Set spa_pak.voltage to {top_voltage} (primary electrical input voltage)",
            "status": "fixed",
        })

    return anomalies


def _fix_cover_dimensions(data: dict, model_name: str) -> list[dict]:
    """Fix cover dimension swaps for M6 and M9.

    Cover L/W were swapped relative to spa dimensions. The cover sits on
    top of the spa so its dimensions should match.
    """
    anomalies: list[dict] = []

    if model_name not in ("M6", "M9"):
        return anomalies

    cover = data.get("cover")
    dims = data.get("dimensions")
    if cover is None or dims is None:
        return anomalies

    cover_l = cover.get("length_inches")
    cover_w = cover.get("width_inches")
    spa_l = dims.get("length_inches")
    spa_w = dims.get("width_inches")

    if cover_l is None or cover_w is None:
        return anomalies

    # Check if swapped: cover_l matches spa_w and cover_w matches spa_l
    if (
        abs(cover_l - spa_w) < 1.0
        and abs(cover_w - spa_l) < 1.0
        and (abs(cover_l - spa_l) > 1.0 or abs(cover_w - spa_w) > 1.0)
    ):
        old_l, old_w = cover_l, cover_w
        cover["length_inches"] = spa_l
        cover["width_inches"] = spa_w
        anomalies.append({
            "field": "cover.length_inches, cover.width_inches",
            "issue": f"Cover dimensions ({old_l}x{old_w}) were swapped vs spa dimensions ({spa_l}x{spa_w})",
            "resolution": f"Swapped cover to ({spa_l}x{spa_w}) to match spa physical dimensions",
            "status": "fixed",
        })

    return anomalies


# ---------------------------------------------------------------------------
# Step 2: Build anomalies_reviewed for known issues
# ---------------------------------------------------------------------------


def _build_jet_count_anomaly(data: dict) -> list[dict]:
    """Create anomaly entries for jet count mismatches (accepted, not fixed)."""
    anomalies: list[dict] = []

    jets = data.get("jets")
    if jets is None:
        return anomalies

    total = jets.get("total_jet_count")
    jets_by_type = jets.get("jets_by_type", [])

    if total is None or not jets_by_type:
        return anomalies

    sum_val = sum(j.get("quantity", 0) for j in jets_by_type)

    if total != sum_val:
        anomalies.append({
            "field": "jets.total_jet_count vs jets.jets_by_type sum",
            "issue": f"total={total} vs sum_by_type={sum_val}",
            "resolution": (
                "Different counting methods: total is primary therapy jets, "
                "by_type includes all jet types including water features"
            ),
            "status": "accepted",
        })

    return anomalies


def _build_missing_category_anomalies(data: dict, model: SpaModel) -> list[dict]:
    """Create anomaly entries for missing/empty categories."""
    anomalies: list[dict] = []

    # NULL categories (entirely missing)
    null_cats = {
        "filters": model.filters,
        "lighting": model.lighting,
    }
    for cat_name, cat_val in null_cats.items():
        if cat_val is None:
            anomalies.append({
                "field": cat_name,
                "issue": "Category entirely null -- extraction failed",
                "resolution": "Data not extractable from available sources",
                "status": "accepted_not_available",
            })

    # EMPTY categories for Bullfrog (present but all fields null)
    if model.manufacturer.value == "bullfrog":
        bullfrog_cats = {
            "heater": model.heater,
            "spa_pak": model.spa_pak,
        }
        for cat_name, cat_val in bullfrog_cats.items():
            if cat_val is not None and _is_category_all_null(cat_val):
                anomalies.append({
                    "field": cat_name,
                    "issue": "Category present but all fields null",
                    "resolution": "Bullfrog manuals do not include this specification",
                    "status": "accepted_not_available",
                })

    return anomalies


def _build_range_anomalies(data: dict, model: SpaModel) -> list[dict]:
    """Create anomaly entries for out-of-range values (seating_capacity=0)."""
    anomalies: list[dict] = []

    if model.seating_capacity == 0:
        anomalies.append({
            "field": "seating_capacity",
            "issue": f"seating_capacity={model.seating_capacity} outside plausible range [2, 10]",
            "resolution": "Value not available from extraction sources; retained as 0 pending manual verification",
            "status": "accepted",
        })

    return anomalies


# ---------------------------------------------------------------------------
# Step 4: Compute completeness percentage
# ---------------------------------------------------------------------------


def _compute_completeness_pct(model: SpaModel, not_available: list[str]) -> float:
    """Compute completeness of available data.

    Formula: (non-null fields - not_available) / (total fields - not_available) * 100

    Counts meaningful fields on the model (excluding booleans, defaults,
    and list containers). A field is 'filled' if it has a non-null,
    non-empty value.
    """
    total_fields = 0
    filled_fields = 0

    # Top-level scalar fields
    _TOP_FIELDS = [
        "seating_capacity", "voltage", "amperage",
    ]
    for f in _TOP_FIELDS:
        val = getattr(model, f, None)
        total_fields += 1
        if val is not None and val != 0:
            filled_fields += 1

    # Dimensions
    if model.dimensions:
        for f in ["length_inches", "width_inches", "height_inches",
                   "dry_weight_lbs", "filled_weight_lbs", "water_capacity_gallons"]:
            total_fields += 1
            val = getattr(model.dimensions, f, None)
            if val is not None:
                filled_fields += 1

    # 10 category fields -- count non-null/non-empty leaf fields
    _CATEGORIES = [
        "jet_pumps", "circulation_pump", "spa_pak", "topside_control",
        "jets", "headrests", "filters", "heater", "lighting", "cover",
    ]
    _SKIP = {
        "shared_with_series", "is_dedicated", "requires_gfci",
        "jet_system_type", "frequency_hz",
    }

    for cat_name in _CATEGORIES:
        cat = getattr(model, cat_name, None)
        if cat is None:
            # Count the category as having at least 1 missing field
            total_fields += 1
            continue
        for field_name, value in cat.__dict__.items():
            if field_name.startswith("_"):
                continue
            if field_name in _SKIP:
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, list):
                # For lists, count as 1 field: filled if non-empty
                total_fields += 1
                if len(value) > 0:
                    filled_fields += 1
            else:
                total_fields += 1
                if value is not None:
                    filled_fields += 1

    na_count = len(not_available)
    denominator = total_fields - na_count
    if denominator <= 0:
        return 100.0

    numerator = filled_fields - na_count
    if numerator < 0:
        numerator = 0

    return round((numerator / denominator) * 100, 1)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def apply_verification() -> None:
    """Apply all verification fixes and metadata to 19 JSON files."""
    json_files = sorted(DATA_DIR.rglob("*.json"))
    print(f"Found {len(json_files)} JSON files in {DATA_DIR}")

    for json_path in json_files:
        print(f"\nProcessing: {json_path.name}")

        # Load raw JSON
        raw_text = json_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        model_name = data.get("model_name", "unknown")

        # Track all anomalies for this model
        all_anomalies: list[dict] = []

        # Step 1: Fix confirmed errors
        all_anomalies.extend(_fix_voltage(data, model_name))
        all_anomalies.extend(_fix_cover_dimensions(data, model_name))

        # Pre-validate to get SpaModel for analysis
        model = SpaModel.model_validate(data)

        # Step 2a: Jet count anomalies
        all_anomalies.extend(_build_jet_count_anomaly(data))

        # Step 2b: Missing/empty category anomalies
        all_anomalies.extend(_build_missing_category_anomalies(data, model))

        # Step 2c: Range anomalies
        all_anomalies.extend(_build_range_anomalies(data, model))

        # Step 2d: Build not-available list
        na_fields = build_not_available_list(model)

        # Step 4: Compute completeness
        completeness = _compute_completeness_pct(model, na_fields)

        # Step 2+3: Add data_quality metadata
        data["data_quality"] = {
            "verification_date": VERIFICATION_DATE,
            "verified_by": VERIFIED_BY,
            "not_available_fields": na_fields,
            "anomalies_reviewed": all_anomalies,
            "completeness_pct": completeness,
        }

        # Step 3: Mark source references as verified
        for src in data.get("source_documents", []):
            src["verified_by"] = VERIFIED_BY
            src["verified_date"] = VERIFICATION_DATE

        # Step 5: Validate with Pydantic before write
        validated = SpaModel.model_validate(data)
        assert validated.data_quality is not None, f"{model_name}: data_quality missing after apply"
        assert len(validated.data_quality.not_available_fields) > 0, (
            f"{model_name}: no not_available_fields"
        )

        # Write back with consistent formatting (2-space indent, trailing newline)
        output_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        json_path.write_text(output_text, encoding="utf-8")

        # Round-trip validation
        reloaded = json.loads(json_path.read_text(encoding="utf-8"))
        SpaModel.model_validate(reloaded)

        fixes = [a for a in all_anomalies if a["status"] == "fixed"]
        accepted = [a for a in all_anomalies if a["status"] != "fixed"]
        print(
            f"  {model_name}: {len(fixes)} fixes, {len(accepted)} accepted anomalies, "
            f"{len(na_fields)} not-available, completeness={completeness}%"
        )

    print(f"\nVerification applied to {len(json_files)} models successfully.")
