"""Website-first extraction pipeline: Gemini extracts, OpenAI reviews.

Fetches manufacturer web pages via Playwright, extracts specs with Gemini,
reviews with OpenAI, merges at field level, validates with cross-field
checks, and writes fresh JSON files.

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
from .extract import openai_extractor
from .extract.dual_resolver import merge_reviewed
from .extract.web_extractor_v2 import extract, extract_categories
from .scrape.browser import PlaywrightFetcher
from .scrape.config import SCRAPE_URLS, get_delay_for_url
from .scrape.content import cache_html, get_cached_html, html_to_text
from .quality_scorer import score_model
from .verify.checks import ExtractionError, get_extraction_errors

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    return name.lower().replace(" ", "-")


def _fetch_html(
    url: str,
    alt_url: str | None,
    browser_fetcher: PlaywrightFetcher,
) -> str | None:
    """Fetch raw HTML via Playwright, using cache if available."""
    # Check cache first
    cached = get_cached_html(url)
    if cached is not None:
        return cached

    try:
        delay = get_delay_for_url(url)
        html = browser_fetcher.fetch_with_fallback(url, alt_url=alt_url, delay=delay)

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


def _coerce_int(value, *, pick: str = "max") -> int | None:
    """Coerce a value to int, handling strings and lists from LLM output.

    LLMs sometimes return "115 V or 230 V", "20 amp (115 V) or 50 amp (230 V)",
    or [1500, 6000] for fields that require a single integer.

    Args:
        value: The value to coerce.
        pick: "max" to pick the largest number, "min" for smallest.

    Returns:
        An integer, or None if no numbers could be extracted.
    """
    import re

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, list):
        nums = [v for v in value if isinstance(v, (int, float))]
        if not nums:
            return None
        return int(max(nums) if pick == "max" else min(nums))
    if isinstance(value, str):
        found = re.findall(r"\d+", value)
        if not found:
            return None
        ints = [int(n) for n in found]
        return max(ints) if pick == "max" else min(ints)
    return None


def _apply_defaults(data: dict) -> dict:
    """Apply null-safe defaults for fields the Pydantic schema requires.

    Gemini may return null for fields that the schema does not allow to be
    None (e.g., jet_system_type, is_dedicated, feature lists, dimensions).
    Also coerces string/list values to int for voltage, amperage, and wattage
    fields at both top-level and nested levels.
    """
    # Normalize pump speed values (Gemini may return "One-Speed" vs "1-speed")
    _SPEED_MAP = {
        "one-speed": "1-speed", "one speed": "1-speed", "single-speed": "1-speed",
        "two-speed": "2-speed", "two speed": "2-speed", "dual-speed": "2-speed",
    }
    _VALID_SPEEDS = {"1-speed", "2-speed", "variable"}
    pumps_data = data.get("jet_pumps")
    if isinstance(pumps_data, dict):
        for pump in pumps_data.get("pumps") or []:
            if isinstance(pump, dict) and isinstance(pump.get("speed"), str):
                mapped = _SPEED_MAP.get(pump["speed"].lower(), pump["speed"])
                pump["speed"] = mapped if mapped in _VALID_SPEEDS else None

        # Remove phantom pump: when a dedicated circ pump exists and the last
        # jet pump entry has speed=None with all other fields null, it's likely
        # the circulation pump double-counted as a jet pump.
        circ_data = data.get("circulation_pump")
        pumps_list = pumps_data.get("pumps") or []
        if (
            circ_data
            and isinstance(circ_data, dict)
            and circ_data.get("is_dedicated")
            and len(pumps_list) > 1
        ):
            last = pumps_list[-1]
            if isinstance(last, dict) and last.get("speed") is None:
                spec_fields = ("model_name", "horsepower_continuous",
                               "horsepower_breakdown", "amperage_max", "frame",
                               "voltage", "part_number")
                if all(last.get(f) is None for f in spec_fields):
                    pumps_list.pop()
                    pumps_data["pumps"] = pumps_list

    jets = data.get("jets")
    if isinstance(jets, dict):
        if jets.get("jet_system_type") not in ("fixed", "modular_jetpak"):
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
        # Coerce voltage/amperage: LLMs return "115 V or 230 V" etc.
        spa_pak["voltage"] = _coerce_int(spa_pak.get("voltage"))
        spa_pak["amperage"] = _coerce_int(spa_pak.get("amperage"))
        spa_pak["frequency_hz"] = _coerce_int(spa_pak.get("frequency_hz"))

    heater = data.get("heater")
    if isinstance(heater, dict):
        # Coerce wattage/voltage: LLMs return [1500, 6000] or "6000 W" etc.
        heater["wattage"] = _coerce_int(heater.get("wattage"))
        heater["voltage"] = _coerce_int(heater.get("voltage"))

    cover = data.get("cover")
    if isinstance(cover, dict):
        if cover.get("features") is None:
            cover["features"] = []

    dims = data.get("dimensions")
    if isinstance(dims, dict):
        for field in ("length_inches", "width_inches", "height_inches"):
            if dims.get(field) is None:
                dims[field] = 0.0

    # Top-level voltage/amperage: coerce and apply defaults
    data["voltage"] = _coerce_int(data.get("voltage")) or 240
    data["amperage"] = _coerce_int(data.get("amperage"))

    # Seating capacity: LLMs sometimes return string "7" or null
    seat = data.get("seating_capacity")
    if isinstance(seat, str):
        import re
        found = re.findall(r"\d+", seat)
        data["seating_capacity"] = int(found[0]) if found else 0
    elif seat is None:
        data["seating_capacity"] = 0

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
    browser_fetcher: PlaywrightFetcher,
    year: int = 2026,
) -> SpaModel | None:
    """Extract specs for a single model from its web page.

    Uses Gemini for extraction and OpenAI for review, then merges
    at field level.

    Args:
        manufacturer: Manufacturer key (e.g. "hotspring").
        model_name: Model name (e.g. "Vanguard").
        browser_fetcher: Playwright fetcher for all sites.
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

    # 1. Fetch HTML (cached or fresh) — always Playwright
    print(f"  Fetching page...")
    html = _fetch_html(url, alt_url, browser_fetcher)
    if not html:
        print(f"  FAILED: Could not fetch page")
        return None

    # 2. Convert to clean text
    page_text = html_to_text(html)
    print(f"  Page text: {len(page_text)} chars")

    # 3. Extract with Gemini
    print(f"  Extracting with Gemini...")
    gemini_data = extract(
        page_text=page_text,
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
    )
    if not gemini_data:
        print(f"  FAILED: Gemini extraction returned nothing")
        return None
    print(f"  Gemini extraction complete: {len(gemini_data)} top-level keys")

    # 4. OpenAI reviews Gemini's extraction
    print(f"  Reviewing with OpenAI...")
    review_data = openai_extractor.review(
        gemini_data=gemini_data,
        page_text=page_text,
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
    )
    if not review_data:
        print(f"  WARNING: OpenAI review returned nothing, using Gemini only")
        raw_data = gemini_data
    else:
        print(f"  OpenAI review complete: {len(review_data)} top-level keys")

        # 5. Field-level merge
        raw_data, report = merge_reviewed(gemini_data, review_data, model_name)
        print(f"  Merge: {report.confirmed} confirmed, {report.corrected} corrected, "
              f"{report.filled} filled, {report.nulled} nulled")
        if report.changes:
            for change in report.changes:
                print(f"    [{change.change_type}] {change.field_path}: "
                      f"{change.gemini_value} -> {change.review_value}")

    # 6. Clean data
    raw_data = _clean_none_strings(raw_data)

    # 7. Cross-field validation loop (max 1 re-extraction)
    raw_data = _run_validation_loop(
        raw_data, page_text, model_name, manufacturer, series, year,
    )

    # 8. Apply null-safe defaults for required schema fields
    raw_data = _apply_defaults(raw_data)

    # 9. Build source reference
    source_ref = _build_source_ref(url)

    # 10. Assemble into SpaModel
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

    # 11. Write JSON with quality scoring
    output_dir = DATA_OUTPUT_DIR / manufacturer / _slugify(series)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{_slugify(model_name)}-{year}.json"

    model_dict = spa_model.model_dump()
    model_dict["data_quality"] = score_model(model_dict)
    output_path.write_text(
        json.dumps(model_dict, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    completeness = model_dict["data_quality"]["completeness_pct"]
    print(f"  Output: {output_path} ({output_path.stat().st_size} bytes, {completeness}% complete)")
    return spa_model


def run_web_manufacturer(
    manufacturer: str,
    browser_fetcher: PlaywrightFetcher,
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
                manufacturer, model_name, browser_fetcher, year,
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

    Uses Playwright for all sites. Extracts with Gemini, reviews with
    OpenAI, merges at field level. Includes validation feedback loop
    for cross-field error correction.

    Args:
        year: Model year.
        manufacturers: Subset of manufacturers to process. None = all.
        clean: If True, delete existing JSON files first.

    Returns:
        Dict mapping manufacturer key to list of SpaModel instances.
    """
    mfr_keys = manufacturers or list(MANUFACTURERS.keys())

    print(f"\n{'#'*60}")
    print(f"DEX Extract + Review Pipeline")
    print(f"Year: {year}")
    print(f"Manufacturers: {', '.join(mfr_keys)}")
    print(f"{'#'*60}")

    if clean:
        delete_existing_data(manufacturers=mfr_keys)

    print("  Launching Playwright browser...")
    browser_fetcher = PlaywrightFetcher()

    try:
        all_results: dict[str, list[SpaModel]] = {}
        total_models = 0
        total_success = 0

        for mfr in mfr_keys:
            results = run_web_manufacturer(mfr, browser_fetcher, year)
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
        browser_fetcher.close()


# CLI entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        mfr = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) > 2 else None

        if model:
            browser_fetcher = PlaywrightFetcher()
            try:
                run_web_model(mfr, model, browser_fetcher)
            finally:
                browser_fetcher.close()
        else:
            run_web_extraction(manufacturers=[mfr])
    else:
        run_web_extraction()
