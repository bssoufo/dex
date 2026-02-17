"""Website-first extraction pipeline.

Fetches manufacturer web pages, extracts specs via Gemini, and writes
fresh JSON files. Replaces the PDF-first approach for more accurate data.

Usage:
    # Extract all manufacturers
    uv run python -m src.etl.web_pipeline

    # Extract one manufacturer
    uv run python -m src.etl.web_pipeline hotspring

    # Extract a single model
    uv run python -m src.etl.web_pipeline hotspring Vanguard
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from ..schema.models import SpaModel
from ..schema.parts import SourceReference
from .config import DATA_OUTPUT_DIR, MANUFACTURERS
from .extract.web_extractor import extract_from_web
from .scrape.config import SCRAPE_URLS
from .scrape.fetcher import PageFetcher

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    return name.lower().replace(" ", "-")


def _fetch_page_text(fetcher: PageFetcher, url: str, alt_url: str | None) -> str | None:
    """Fetch a web page and return its text content."""
    try:
        html = fetcher.fetch_with_fallback(url, alt_url=alt_url)
        # Strip HTML to get clean text for Gemini
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        # Remove script/style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return None


def _build_source_ref(url: str) -> SourceReference:
    """Build a SourceReference for a web page."""
    return SourceReference(
        source_type="website",
        url=url,
        document_name=None,
        page_number=None,
        section=None,
        accessed_date=date.today().isoformat(),
        verified_by=None,
        verified_date=None,
    )


def _clean_none_strings(data):
    """Recursively convert string 'null'/'None' to actual None."""
    if isinstance(data, dict):
        return {k: _clean_none_strings(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_clean_none_strings(v) for v in data]
    if isinstance(data, str) and data.lower() in ("null", "none", "n/a"):
        return None
    return data


def _apply_defaults(data: dict) -> dict:
    """Apply null-safe defaults for fields the Pydantic schema requires.

    Gemini may return null for fields that the schema does not allow to be
    None (e.g., jet_system_type, is_dedicated, feature lists, dimensions).
    """
    # jets.jet_system_type: required enum, default to "fixed"
    jets = data.get("jets")
    if isinstance(jets, dict):
        if jets.get("jet_system_type") is None:
            jets["jet_system_type"] = "fixed"
        # jets_by_type[*].quantity: required int, default to 0
        for jet in jets.get("jets_by_type") or []:
            if isinstance(jet, dict) and jet.get("quantity") is None:
                jet["quantity"] = 0

    # circulation_pump.is_dedicated: required bool
    circ = data.get("circulation_pump")
    if isinstance(circ, dict):
        if circ.get("is_dedicated") is None:
            circ["is_dedicated"] = True

    # topside_control.features: required list
    topside = data.get("topside_control")
    if isinstance(topside, dict):
        if topside.get("features") is None:
            topside["features"] = []

    # spa_pak.features: required list
    spa_pak = data.get("spa_pak")
    if isinstance(spa_pak, dict):
        if spa_pak.get("features") is None:
            spa_pak["features"] = []

    # cover.features: required list
    cover = data.get("cover")
    if isinstance(cover, dict):
        if cover.get("features") is None:
            cover["features"] = []

    # dimensions: required floats, default to 0.0
    dims = data.get("dimensions")
    if isinstance(dims, dict):
        for field in ("length_inches", "width_inches", "height_inches"):
            if dims.get(field) is None:
                dims[field] = 0.0

    # voltage: required int
    if data.get("voltage") is None:
        data["voltage"] = 240

    return data


def run_web_model(
    manufacturer: str,
    model_name: str,
    fetcher: PageFetcher,
    year: int = 2026,
) -> SpaModel | None:
    """Extract specs for a single model from its web page.

    Args:
        manufacturer: Manufacturer key (e.g. "hotspring").
        model_name: Model name (e.g. "Vanguard").
        fetcher: HTTP fetcher instance.
        year: Model year.

    Returns:
        Validated SpaModel or None on failure.
    """
    mfr_config = MANUFACTURERS[manufacturer]
    series = mfr_config["series"]

    # Find URL for this model
    url_entry = None
    for entry in SCRAPE_URLS.get(manufacturer, []):
        if entry["model_name"] == model_name:
            url_entry = entry
            break

    if not url_entry:
        print(f"  ERROR: No URL configured for {manufacturer}/{model_name}")
        return None

    url = url_entry["url"]
    alt_url = url_entry.get("alt_url")

    print(f"\n{'='*60}")
    print(f"Extracting: {manufacturer} {model_name} ({series}, {year})")
    print(f"URL: {url}")
    print(f"{'='*60}")

    # 1. Fetch web page
    print(f"  Fetching page...")
    page_text = _fetch_page_text(fetcher, url, alt_url)
    if not page_text:
        print(f"  FAILED: Could not fetch page")
        return None
    print(f"  Page fetched: {len(page_text)} chars")

    # 2. Extract with Gemini
    print(f"  Extracting with Gemini...")
    raw_data = extract_from_web(
        page_text=page_text,
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
    )
    if not raw_data:
        print(f"  FAILED: Gemini extraction returned nothing")
        return None
    print(f"  Extraction complete: {len(raw_data)} top-level keys")

    # 3. Clean data
    raw_data = _clean_none_strings(raw_data)

    # 4. Apply null-safe defaults for required schema fields
    raw_data = _apply_defaults(raw_data)

    # 5. Build source reference
    source_ref = _build_source_ref(url)

    # 6. Assemble into SpaModel
    model_data = {
        "manufacturer": manufacturer,
        "series": series,
        "model_name": model_name,
        "year": year,
        "seating_capacity": raw_data.get("seating_capacity", 0) or 0,
        "jet_pumps": raw_data.get("jet_pumps"),
        "circulation_pump": raw_data.get("circulation_pump"),
        "spa_pak": raw_data.get("spa_pak"),
        "topside_control": raw_data.get("topside_control"),
        "jets": raw_data.get("jets"),
        "headrests": raw_data.get("headrests"),
        "filters": raw_data.get("filters"),
        "heater": raw_data.get("heater"),
        "lighting": raw_data.get("lighting"),
        "cover": raw_data.get("cover"),
        "dimensions": raw_data.get("dimensions", {}),
        "voltage": raw_data.get("voltage", 240),
        "amperage": raw_data.get("amperage"),
        "source_documents": [source_ref.model_dump()],
    }

    try:
        spa_model = SpaModel.model_validate(model_data)
    except ValidationError as exc:
        print(f"  VALIDATION ERROR:\n{exc}")
        # Write raw data for debugging
        debug_dir = DATA_OUTPUT_DIR / manufacturer / _slugify(series)
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{_slugify(model_name)}-{year}-RAW.json"
        debug_path.write_text(json.dumps(model_data, indent=2, default=str))
        print(f"  Raw data saved to: {debug_path}")
        return None

    # 6. Write JSON
    output_dir = DATA_OUTPUT_DIR / manufacturer / _slugify(series)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{_slugify(model_name)}-{year}.json"
    output_path.write_text(
        json.dumps(spa_model.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  Output: {output_path} ({output_path.stat().st_size} bytes)")
    return spa_model


def run_web_manufacturer(
    manufacturer: str,
    fetcher: PageFetcher,
    year: int = 2026,
) -> list[SpaModel]:
    """Extract specs for all models of a manufacturer from web pages."""
    mfr_config = MANUFACTURERS[manufacturer]
    models = mfr_config["models"]

    print(f"\n{'#'*60}")
    print(f"Manufacturer: {manufacturer} ({mfr_config['series']})")
    print(f"Models to extract: {len(models)}")
    print(f"{'#'*60}")

    results = []
    failures = []

    for model_name in models:
        try:
            spa_model = run_web_model(manufacturer, model_name, fetcher, year)
            if spa_model:
                results.append(spa_model)
            else:
                failures.append(model_name)
        except Exception as exc:
            logger.error("Failed %s %s: %s", manufacturer, model_name, exc)
            failures.append(model_name)
            print(f"  ERROR: {exc}")

    print(f"\n{'='*60}")
    print(f"  {manufacturer}: {len(results)}/{len(models)} extracted")
    if failures:
        print(f"  Failures: {', '.join(failures)}")
    print(f"{'='*60}")
    return results


def delete_existing_data(manufacturers: list[str] | None = None):
    """Delete existing JSON data files before fresh extraction.

    Args:
        manufacturers: If provided, only delete files for these manufacturers.
                       If None, delete all JSON files.
    """
    data_dir = DATA_OUTPUT_DIR
    if not data_dir.exists():
        return

    count = 0
    if manufacturers:
        for mfr in manufacturers:
            mfr_dir = data_dir / mfr
            if mfr_dir.exists():
                for json_file in mfr_dir.rglob("*.json"):
                    json_file.unlink()
                    count += 1
    else:
        for json_file in data_dir.rglob("*.json"):
            json_file.unlink()
            count += 1

    print(f"Deleted {count} existing JSON files from {data_dir}")


def run_web_extraction(
    year: int = 2026,
    manufacturers: list[str] | None = None,
    clean: bool = True,
) -> dict[str, list[SpaModel]]:
    """Run the full website-first extraction pipeline.

    Args:
        year: Model year.
        manufacturers: Subset of manufacturers to process. None = all.
        clean: If True, delete existing JSON files first.

    Returns:
        Dict mapping manufacturer key to list of SpaModel instances.
    """
    mfr_keys = manufacturers or list(MANUFACTURERS.keys())

    print(f"\n{'#'*60}")
    print(f"DEX Web Extraction Pipeline")
    print(f"Year: {year}")
    print(f"Manufacturers: {', '.join(mfr_keys)}")
    print(f"{'#'*60}")

    if clean:
        delete_existing_data(manufacturers=mfr_keys)

    fetcher = PageFetcher()
    all_results: dict[str, list[SpaModel]] = {}
    total_models = 0
    total_success = 0

    for mfr in mfr_keys:
        results = run_web_manufacturer(mfr, fetcher, year)
        all_results[mfr] = results
        mfr_total = len(MANUFACTURERS[mfr]["models"])
        total_models += mfr_total
        total_success += len(results)

    print(f"\n{'#'*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Total: {total_success}/{total_models} models extracted")
    for mfr, results in all_results.items():
        mfr_total = len(MANUFACTURERS[mfr]["models"])
        print(f"    {mfr}: {len(results)}/{mfr_total}")
    print(f"{'#'*60}")

    return all_results


# CLI entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        mfr = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) > 2 else None

        if model:
            fetcher = PageFetcher()
            run_web_model(mfr, model, fetcher)
        else:
            run_web_extraction(manufacturers=[mfr])
    else:
        run_web_extraction()
