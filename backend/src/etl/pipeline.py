"""Main extraction pipeline orchestrator.

Single entry point for running PDF-to-JSON extractions. Ties together
manufacturer templates, Gemini extractor, schema mapper, validators,
provenance builder, and JSON writer into a cohesive pipeline.

Usage:
    # Extract all manufacturers
    uv run python -m src.etl.pipeline

    # Extract all models for one manufacturer
    uv run python -m src.etl.pipeline sundance

    # Extract a single model
    uv run python -m src.etl.pipeline sundance Aspen
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ..schema.models import SpaModel
from .config import DATA_OUTPUT_DIR, MANUFACTURERS, PDF_STORE_DIR
from .extract.gemini_extractor import CategoryExtraction, extract_model_specs
from .output.provenance import build_all_source_refs
from .output.writer import write_model_json, write_raw_json
from .templates.bullfrog import BullfrogMSeriesTemplate
from .templates.hotspring import HotSpringHighlifeTemplate
from .templates.sundance import Sundance880Template
from .transform.schema_mapper import map_to_spa_model
from .transform.validators import validate_extraction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES = {
    "sundance": Sundance880Template(),
    "hotspring": HotSpringHighlifeTemplate(),
    "bullfrog": BullfrogMSeriesTemplate(),
}


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def run_model(
    manufacturer: str,
    model_name: str,
    year: int = 2026,
) -> SpaModel | None:
    """Extract specifications for a single spa model from its PDF.

    Runs the full pipeline: extract (Gemini API) -> validate -> provenance
    -> map (to SpaModel) -> write (JSON file).

    Args:
        manufacturer: Manufacturer key (e.g. ``"sundance"``).
        model_name: Model name (e.g. ``"Aspen"``).
        year: Model year. Defaults to 2026.

    Returns:
        A validated ``SpaModel`` if extraction and mapping succeed,
        or ``None`` if mapping fails (raw debug JSON is written instead).

    Raises:
        KeyError: If manufacturer is not in ``TEMPLATES`` or ``MANUFACTURERS``.
        FileNotFoundError: If the manufacturer's PDF is not found.
    """
    # Resolve template and config
    template = TEMPLATES[manufacturer]
    mfr_config = MANUFACTURERS[manufacturer]
    series = mfr_config["series"]

    # Resolve PDF path
    pdf_path = PDF_STORE_DIR / manufacturer / mfr_config["pdf_filename"]
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}. "
            f"Run the PDF download step first (Plan 02-01)."
        )

    print(f"\n{'='*60}")
    print(f"Extracting: {manufacturer} {model_name} ({series}, {year})")
    print(f"PDF: {pdf_path.name}")
    print(f"{'='*60}")

    # 1. Extract all categories from PDF via Gemini API
    extractions: dict[str, CategoryExtraction] = extract_model_specs(
        pdf_path, template, model_name
    )

    if not extractions:
        print(f"  WARNING: No categories extracted for {model_name}")
        return None

    # 2. Validate extractions (non-blocking warnings)
    warnings = validate_extraction(model_name, extractions)
    if warnings:
        print(f"\n  Validation warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")
    else:
        print(f"\n  Validation: all checks passed")

    # 3. Build provenance source references
    source_refs = build_all_source_refs(pdf_path.name, extractions)

    # 4. Map to SpaModel
    spa_model = map_to_spa_model(
        manufacturer, series, model_name, year, extractions, source_refs
    )

    # 5. Write output
    if spa_model is not None:
        output_path = write_model_json(spa_model)
        print(f"  Output: {output_path}")
        return spa_model

    # Mapping failed -- write raw debug JSON
    print(f"  WARNING: Schema mapping failed for {model_name}")
    raw_data = {
        cat: ext.data for cat, ext in extractions.items()
    }
    output_dir = DATA_OUTPUT_DIR / manufacturer
    write_raw_json(model_name, year, raw_data, output_dir)
    return None


def run_manufacturer(
    manufacturer: str,
    year: int = 2026,
) -> list[SpaModel]:
    """Extract specifications for all models of a manufacturer.

    Args:
        manufacturer: Manufacturer key (e.g. ``"sundance"``).
        year: Model year. Defaults to 2026.

    Returns:
        List of successfully extracted ``SpaModel`` instances.

    Raises:
        KeyError: If manufacturer is not in ``MANUFACTURERS``.
    """
    mfr_config = MANUFACTURERS[manufacturer]
    models: list[str] = mfr_config["models"]

    print(f"\n{'#'*60}")
    print(f"Manufacturer: {manufacturer} ({mfr_config['series']})")
    print(f"Models to extract: {len(models)}")
    print(f"{'#'*60}")

    results: list[SpaModel] = []
    failures: list[str] = []

    for model_name in models:
        try:
            spa_model = run_model(manufacturer, model_name, year)
            if spa_model is not None:
                results.append(spa_model)
            else:
                failures.append(model_name)
        except Exception as exc:
            logger.error(
                "Failed to extract %s %s: %s",
                manufacturer,
                model_name,
                exc,
            )
            failures.append(model_name)
            print(f"  ERROR extracting {model_name}: {exc}")

    # Summary
    print(f"\n{'='*60}")
    print(
        f"  {manufacturer}: {len(results)}/{len(models)} models "
        f"extracted successfully"
    )
    if failures:
        print(f"  Failures: {', '.join(failures)}")
    print(f"{'='*60}")

    return results


def run_extraction(
    year: int = 2026,
    manufacturers: list[str] | None = None,
) -> dict[str, list[SpaModel]]:
    """Extract specifications for all manufacturers (or a subset).

    This is the top-level entry point for the full extraction pipeline.

    Args:
        year: Model year. Defaults to 2026.
        manufacturers: List of manufacturer keys to process. If ``None``,
            processes all manufacturers in ``MANUFACTURERS``.

    Returns:
        Dict mapping manufacturer key to list of ``SpaModel`` instances.
    """
    mfr_keys = manufacturers or list(MANUFACTURERS.keys())

    print(f"\n{'#'*60}")
    print(f"DEX Extraction Pipeline")
    print(f"Year: {year}")
    print(f"Manufacturers: {', '.join(mfr_keys)}")
    print(f"{'#'*60}")

    all_results: dict[str, list[SpaModel]] = {}
    total_models = 0
    total_success = 0
    total_failures = 0

    for mfr in mfr_keys:
        results = run_manufacturer(mfr, year)
        all_results[mfr] = results

        mfr_total = len(MANUFACTURERS[mfr]["models"])
        total_models += mfr_total
        total_success += len(results)
        total_failures += mfr_total - len(results)

    # Grand summary
    print(f"\n{'#'*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Total models: {total_models}")
    print(f"  Successful:   {total_success}")
    print(f"  Failed:       {total_failures}")
    for mfr, results in all_results.items():
        mfr_total = len(MANUFACTURERS[mfr]["models"])
        print(f"    {mfr}: {len(results)}/{mfr_total}")
    print(f"{'#'*60}")

    return all_results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        manufacturer = sys.argv[1]
        model_name = sys.argv[2] if len(sys.argv) > 2 else None
        if model_name:
            run_model(manufacturer, model_name)
        else:
            run_manufacturer(manufacturer)
    else:
        run_extraction()
