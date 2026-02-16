"""Scrape pipeline orchestrator: fetch, parse, merge for all 19 spa models.

Ties together the fetcher, manufacturer parsers, and merger to scrape
all model pages and merge the extracted specs into existing JSON files.

Usage::

    # Scrape all manufacturers
    uv run python -m src.etl.scrape.pipeline

    # Scrape one manufacturer
    uv run python -m src.etl.scrape.pipeline sundance
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from src.etl.scrape.config import SCRAPE_URLS, get_delay_for_url
from src.etl.scrape.fetcher import PageFetcher
from src.etl.scrape.merger import merge_scraped_into_model, resolve_json_path
from src.etl.scrape.parsers.bullfrog import BullfrogParser
from src.etl.scrape.parsers.hotspring import HotSpringParser
from src.etl.scrape.parsers.sundance import SundanceParser

logger = logging.getLogger(__name__)

# === Parser registry ===
PARSERS = {
    "sundance": SundanceParser(),
    "hotspring": HotSpringParser(),
    "bullfrog": BullfrogParser(),
}

# === Manufacturer metadata ===
MANUFACTURER_META = {
    "sundance": "880 Series",
    "hotspring": "Highlife Collection",
    "bullfrog": "M Series",
}


def scrape_model(
    manufacturer: str,
    model_entry: dict[str, str | None],
    fetcher: PageFetcher,
) -> dict[str, Any] | None:
    """Scrape a single model page and merge results into its JSON file.

    Args:
        manufacturer: Manufacturer key (e.g. "sundance").
        model_entry: Dict with keys ``model_name``, ``url``, ``alt_url``.
        fetcher: Shared PageFetcher instance.

    Returns:
        Merge report dict, or None if scraping/merging failed.
    """
    model_name = model_entry["model_name"]
    url = model_entry["url"]
    alt_url = model_entry.get("alt_url")
    series = MANUFACTURER_META[manufacturer]

    logger.info("--- Scraping %s %s from %s ---", manufacturer, model_name, url)

    # Fetch the page
    try:
        delay = get_delay_for_url(url)
        html = fetcher.fetch_with_fallback(url, alt_url, delay=delay)
    except Exception as exc:
        logger.error(
            "FAILED to fetch %s %s: %s: %s",
            manufacturer,
            model_name,
            type(exc).__name__,
            exc,
        )
        return None

    # Parse HTML with the appropriate manufacturer parser
    parser = PARSERS[manufacturer]
    scraped = parser.parse_model_page(html, model_name)

    # Track which URL was actually used (may be alt_url on fallback)
    scraped.source_url = url  # The primary URL is recorded; if fallback was used, fetcher logged it

    # Resolve the JSON file path
    json_path = resolve_json_path(manufacturer, series, model_name)
    if not json_path.exists():
        logger.warning(
            "JSON file does not exist for %s %s: %s -- skipping merge",
            manufacturer,
            model_name,
            json_path,
        )
        return None

    # Merge scraped data into the JSON file
    try:
        result = merge_scraped_into_model(json_path, scraped)
        result["manufacturer"] = manufacturer
        return result
    except Exception as exc:
        logger.error(
            "FAILED to merge %s %s: %s: %s",
            manufacturer,
            model_name,
            type(exc).__name__,
            exc,
        )
        return None


def run_scrape_pipeline(
    manufacturers: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full scrape pipeline across all (or specified) manufacturers.

    Fetches each model's product page, parses it with the manufacturer-
    specific parser, and merges the extracted specs into the existing
    JSON data files.

    Args:
        manufacturers: Optional list of manufacturer keys to process.
            If None, processes all three.

    Returns:
        Pipeline report dict with success/failure counts and field details.
    """
    if manufacturers is None:
        manufacturers = list(SCRAPE_URLS.keys())

    # Validate manufacturer keys
    for mfr in manufacturers:
        if mfr not in SCRAPE_URLS:
            raise ValueError(
                f"Unknown manufacturer: {mfr}. Valid: {list(SCRAPE_URLS.keys())}"
            )

    total_models = sum(len(SCRAPE_URLS[m]) for m in manufacturers)
    models_scraped = 0
    models_failed = 0
    total_fields_updated = 0
    by_manufacturer: dict[str, dict] = {}
    details: list[dict] = []
    failed_models: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  Dex Scrape Pipeline -- {total_models} models across {len(manufacturers)} manufacturers")
    print(f"{'='*60}\n")

    with PageFetcher() as fetcher:
        for mfr in manufacturers:
            mfr_models = SCRAPE_URLS[mfr]
            mfr_scraped = 0
            mfr_failed = 0
            mfr_fields_updated: list[str] = []

            print(f"\n--- {mfr.upper()} ({len(mfr_models)} models) ---")

            for model_entry in mfr_models:
                result = scrape_model(mfr, model_entry, fetcher)

                if result is None:
                    mfr_failed += 1
                    models_failed += 1
                    failed_models.append({
                        "manufacturer": mfr,
                        "model": model_entry["model_name"],
                        "url": model_entry["url"],
                    })
                    print(f"  FAILED: {model_entry['model_name']}")
                else:
                    mfr_scraped += 1
                    models_scraped += 1
                    mfr_fields_updated.extend(result["fields_updated"])
                    total_fields_updated += len(result["fields_updated"])
                    details.append(result)

                    updated_count = len(result["fields_updated"])
                    kept_count = len(result["fields_kept"])
                    missing_count = len(result["fields_missing"])
                    print(
                        f"  OK: {result['model_name']} -- "
                        f"{updated_count} filled, {kept_count} kept, {missing_count} missing"
                    )

            by_manufacturer[mfr] = {
                "scraped": mfr_scraped,
                "failed": mfr_failed,
                "fields_updated": mfr_fields_updated,
            }

    # Print summary
    print(f"\n{'='*60}")
    print("  PIPELINE SUMMARY")
    print(f"{'='*60}")
    print(f"  Models scraped: {models_scraped}/{total_models}")
    print(f"  Models failed:  {models_failed}")
    print(f"  Total fields updated: {total_fields_updated}")
    print()

    for mfr, mfr_report in by_manufacturer.items():
        print(f"  {mfr}: {mfr_report['scraped']} scraped, {mfr_report['failed']} failed, {len(mfr_report['fields_updated'])} fields updated")

    if failed_models:
        print(f"\n  FAILED MODELS:")
        for fm in failed_models:
            print(f"    - {fm['manufacturer']}/{fm['model']}: {fm['url']}")

    print(f"\n  PER-MODEL DETAIL:")
    for detail in details:
        updated = detail["fields_updated"]
        kept = detail["fields_kept"]
        missing = detail["fields_missing"]
        print(f"    {detail.get('manufacturer', '?')}/{detail['model_name']}:")
        if updated:
            print(f"      Updated: {', '.join(updated)}")
        if kept:
            print(f"      Kept:    {', '.join(kept)}")
        if missing:
            print(f"      Missing: {', '.join(missing)}")

    print(f"\n{'='*60}\n")

    return {
        "total_models": total_models,
        "models_scraped": models_scraped,
        "models_failed": models_failed,
        "total_fields_updated": total_fields_updated,
        "by_manufacturer": by_manufacturer,
        "details": details,
        "failed_models": failed_models,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    mfrs = sys.argv[1:] if len(sys.argv) > 1 else None
    run_scrape_pipeline(mfrs)
