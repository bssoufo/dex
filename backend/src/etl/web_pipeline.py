"""Website-first extraction pipeline with validation feedback loop.

Fetches manufacturer web pages (httpx for static, Playwright for JS-rendered),
extracts specs via Gemini v2, validates with cross-field checks, and
re-extracts failing categories with error context. Writes fresh JSON files.

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
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from ..schema.models import SpaModel
from ..schema.parts import SourceReference
from .config import DATA_OUTPUT_DIR, MANUFACTURERS
from .extract.web_extractor_v2 import extract, extract_categories
from .scrape.browser import PlaywrightFetcher
from .scrape.config import SCRAPE_URLS, get_delay_for_url, needs_browser
from .scrape.content import cache_html, get_cached_html, html_to_text
from .scrape.fetcher import PageFetcher
from .verify.checks import ExtractionError, get_extraction_errors

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    return name.lower().replace(" ", "-")


def _fetch_html(
    url: str,
    alt_url: str | None,
    http_fetcher: PageFetcher,
    browser_fetcher: PlaywrightFetcher | None,
) -> str | None:
    """Fetch raw HTML, using cache if available, correct fetcher by domain."""
    # Check cache first
    cached = get_cached_html(url)
    if cached is not None:
        return cached

    try:
        if needs_browser(url):
            if browser_fetcher is None:
                logger.error("Browser fetcher required but not available for %s", url)
                return None
            delay = get_delay_for_url(url)
            html = browser_fetcher.fetch_with_fallback(url, alt_url=alt_url, delay=delay)
        else:
            delay = get_delay_for_url(url)
            html = http_fetcher.fetch_with_fallback(url, alt_url=alt_url, delay=delay)

        # Cache for re-extraction retries
        cache_html(url, html)
        return html

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
    # Normalize pump speed values (Gemini may return "One-Speed" vs "1-speed")
    _SPEED_MAP = {
        "one-speed": "1-speed", "one speed": "1-speed", "single-speed": "1-speed",
        "two-speed": "2-speed", "two speed": "2-speed", "dual-speed": "2-speed",
    }
    pumps_data = data.get("jet_pumps")
    if isinstance(pumps_data, dict):
        for pump in pumps_data.get("pumps") or []:
            if isinstance(pump, dict) and isinstance(pump.get("speed"), str):
                pump["speed"] = _SPEED_MAP.get(pump["speed"].lower(), pump["speed"])

    jets = data.get("jets")
    if isinstance(jets, dict):
        if jets.get("jet_system_type") is None:
            jets["jet_system_type"] = "fixed"
        # jets_by_type must be a list, not None
        if jets.get("jets_by_type") is None:
            jets["jets_by_type"] = []
        for jet in jets.get("jets_by_type") or []:
            if isinstance(jet, dict) and jet.get("quantity") is None:
                jet["quantity"] = 0
        # jetpak_options: schema expects int count, Gemini may return list of names
        jp_opts = jets.get("jetpak_options")
        if isinstance(jp_opts, list):
            jets["jetpak_options"] = len(jp_opts)

    circ = data.get("circulation_pump")
    if isinstance(circ, dict):
        if circ.get("is_dedicated") is None:
            circ["is_dedicated"] = True

    topside = data.get("topside_control")
    if isinstance(topside, dict):
        if topside.get("features") is None:
            topside["features"] = []

    spa_pak = data.get("spa_pak")
    if isinstance(spa_pak, dict):
        if spa_pak.get("features") is None:
            spa_pak["features"] = []

    cover = data.get("cover")
    if isinstance(cover, dict):
        if cover.get("features") is None:
            cover["features"] = []

    dims = data.get("dimensions")
    if isinstance(dims, dict):
        for field in ("length_inches", "width_inches", "height_inches"):
            if dims.get(field) is None:
                dims[field] = 0.0

    if data.get("voltage") is None:
        data["voltage"] = 240

    return data


def _run_validation_loop(
    raw_data: dict,
    page_text: str,
    model_name: str,
    manufacturer: str,
    series: str,
    year: int,
) -> dict:
    """Run cross-field checks and re-extract failing categories once.

    Returns the (possibly improved) raw_data dict.
    """
    errors = get_extraction_errors(raw_data)
    if not errors:
        return raw_data

    # Collect failing categories and error messages
    failing_categories = list({e.category for e in errors})
    error_messages = [e.message for e in errors]

    print(f"  Validation errors found ({len(errors)}):")
    for e in errors:
        print(f"    [{e.category}] {e.message}")

    print(f"  Re-extracting categories: {', '.join(failing_categories)}")

    fixed = extract_categories(
        page_text=page_text,
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        categories=failing_categories,
        errors=error_messages,
        year=year,
    )

    if not fixed:
        print("  Re-extraction returned nothing, keeping original data")
        return raw_data

    # Merge fixed categories into original data
    for cat in failing_categories:
        if cat in fixed:
            raw_data[cat] = fixed[cat]
            print(f"    Updated {cat} from re-extraction")

    # Check again (informational only, no second retry)
    remaining = get_extraction_errors(raw_data)
    if remaining:
        print(f"  Still {len(remaining)} issue(s) after re-extraction (flagged for review):")
        for e in remaining:
            print(f"    [{e.category}] {e.message}")
    else:
        print("  All cross-field checks pass after re-extraction")

    return raw_data


def run_web_model(
    manufacturer: str,
    model_name: str,
    http_fetcher: PageFetcher,
    browser_fetcher: PlaywrightFetcher | None = None,
    year: int = 2026,
) -> SpaModel | None:
    """Extract specs for a single model from its web page.

    Args:
        manufacturer: Manufacturer key (e.g. "hotspring").
        model_name: Model name (e.g. "Vanguard").
        http_fetcher: HTTP fetcher for static sites.
        browser_fetcher: Playwright fetcher for JS-rendered sites. Optional.
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

    # 1. Fetch HTML (cached or fresh)
    print(f"  Fetching page...")
    html = _fetch_html(url, alt_url, http_fetcher, browser_fetcher)
    if not html:
        print(f"  FAILED: Could not fetch page")
        return None

    # 2. Convert to clean text
    page_text = html_to_text(html)
    print(f"  Page text: {len(page_text)} chars")

    # 3. Extract with Gemini v2
    print(f"  Extracting with Gemini...")
    raw_data = extract(
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

    # 4. Clean data
    raw_data = _clean_none_strings(raw_data)

    # 5. Cross-field validation loop (max 1 re-extraction)
    raw_data = _run_validation_loop(
        raw_data, page_text, model_name, manufacturer, series, year,
    )

    # 6. Apply null-safe defaults for required schema fields
    raw_data = _apply_defaults(raw_data)

    # 7. Build source reference
    source_ref = _build_source_ref(url)

    # 8. Assemble into SpaModel
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
        debug_dir = DATA_OUTPUT_DIR / manufacturer / _slugify(series)
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / f"{_slugify(model_name)}-{year}-RAW.json"
        debug_path.write_text(json.dumps(model_data, indent=2, default=str))
        print(f"  Raw data saved to: {debug_path}")
        return None

    # 9. Write JSON
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
    http_fetcher: PageFetcher,
    browser_fetcher: PlaywrightFetcher | None = None,
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
            spa_model = run_web_model(
                manufacturer, model_name, http_fetcher, browser_fetcher, year,
            )
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

    Uses httpx for static sites and Playwright for JS-rendered sites.
    Includes validation feedback loop for cross-field error correction.

    Args:
        year: Model year.
        manufacturers: Subset of manufacturers to process. None = all.
        clean: If True, delete existing JSON files first.

    Returns:
        Dict mapping manufacturer key to list of SpaModel instances.
    """
    mfr_keys = manufacturers or list(MANUFACTURERS.keys())

    print(f"\n{'#'*60}")
    print(f"DEX Web Extraction Pipeline v2")
    print(f"Year: {year}")
    print(f"Manufacturers: {', '.join(mfr_keys)}")
    print(f"{'#'*60}")

    if clean:
        delete_existing_data(manufacturers=mfr_keys)

    # Determine if we need browser for any requested manufacturer
    any_needs_browser = any(
        needs_browser(entry["url"])
        for mfr in mfr_keys
        for entry in SCRAPE_URLS.get(mfr, [])
        if entry.get("url")
    )

    http_fetcher = PageFetcher()
    browser_fetcher: PlaywrightFetcher | None = None

    if any_needs_browser:
        print("  Launching Playwright browser for JS-rendered sites...")
        browser_fetcher = PlaywrightFetcher()

    try:
        all_results: dict[str, list[SpaModel]] = {}
        total_models = 0
        total_success = 0

        for mfr in mfr_keys:
            results = run_web_manufacturer(mfr, http_fetcher, browser_fetcher, year)
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
    finally:
        http_fetcher.close()
        if browser_fetcher is not None:
            browser_fetcher.close()


# CLI entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        mfr = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) > 2 else None

        if model:
            http_fetcher = PageFetcher()
            # Check if this specific model needs a browser
            url_entry = None
            for entry in SCRAPE_URLS.get(mfr, []):
                if entry["model_name"] == model:
                    url_entry = entry
                    break

            browser_fetcher = None
            if url_entry and needs_browser(url_entry["url"]):
                browser_fetcher = PlaywrightFetcher()

            try:
                run_web_model(mfr, model, http_fetcher, browser_fetcher)
            finally:
                http_fetcher.close()
                if browser_fetcher:
                    browser_fetcher.close()
        else:
            run_web_extraction(manufacturers=[mfr])
    else:
        run_web_extraction()
