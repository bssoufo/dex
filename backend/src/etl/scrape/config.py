"""Web scraping configuration: URL registry and rate limits.

Contains the URL registry for all 19 spa models across 3 manufacturers,
per-domain rate limits, and helper functions for URL-based configuration.
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.etl.config import DATA_OUTPUT_DIR  # noqa: F401 -- re-export for scrape module

# === URL Registry ===
# Maps manufacturer key -> list of model entries.
# Each entry: model_name (matches MANUFACTURERS config), url, optional alt_url.

SCRAPE_URLS: dict[str, list[dict[str, str | None]]] = {
    "sundance": [
        {
            "model_name": "Aspen",
            "url": "https://www.sundancespas.com/en-us/aspen-880-series/Aspen.html",
            "alt_url": None,
        },
        {
            "model_name": "Optima",
            "url": "https://www.sundancespas.com/en-us/optima-880-series/Optima.html",
            "alt_url": None,
        },
        {
            "model_name": "Cameo",
            "url": "https://www.sundancespas.com/en-us/cameo-880-series/Cameo.html",
            "alt_url": None,
        },
        {
            "model_name": "Altamar",
            "url": "https://www.sundancespas.com/en-us/altamar-880-series/Altamar.html",
            "alt_url": None,
        },
        {
            "model_name": "Vistamar",
            "url": "https://www.sundancespas.com/en-us/vistamar-880-series/Vistamar.html",
            "alt_url": None,
        },
        {
            "model_name": "Marin",
            "url": "https://www.sundancespas.com/en-us/marin-880-series/Marin.html",
            "alt_url": None,
        },
        {
            "model_name": "Capris",
            "url": "https://www.sundancespas.com/en-us/capri-880-series/Capri.html",
            "alt_url": None,
        },
    ],
    "hotspring": [
        {
            "model_name": "Grandee",
            "url": "https://www.hotspringhottubs.com/grandee/",
            "alt_url": None,
        },
        {
            "model_name": "Envoy",
            "url": "https://www.hotspringhottubs.com/envoy/",
            "alt_url": None,
        },
        {
            "model_name": "Aria",
            "url": "https://www.hotspringhottubs.com/aria/",
            "alt_url": None,
        },
        {
            "model_name": "Vanguard",
            "url": "https://www.hotspringhottubs.com/vanguard/",
            "alt_url": None,
        },
        {
            "model_name": "Sovereign",
            "url": "https://www.hotspringhottubs.com/sovereign/",
            "alt_url": None,
        },
        {
            "model_name": "Prodigy",
            "url": "https://www.hotspringhottubs.com/prodigy/",
            "alt_url": None,
        },
        {
            "model_name": "Jetsetter LX",
            "url": "https://www.hotspringhottubs.com/jetsetter-lx/",
            "alt_url": None,
        },
        {
            "model_name": "Jetsetter",
            "url": "https://www.hotspringhottubs.com/jetsetter/",
            "alt_url": None,
        },
    ],
    "bullfrog": [
        {
            "model_name": "M9",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9463",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m9/",
        },
        {
            "model_name": "M8",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9464",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m8/",
        },
        {
            "model_name": "M7",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=18476",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m7/",
        },
        {
            "model_name": "M6",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9466",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m6/",
        },
    ],
}

# === Rate Limits ===
# Per-domain delay in seconds between requests.
# Bullfrog robots.txt specifies crawl-delay of 10 seconds.

RATE_LIMITS: dict[str, float] = {
    "sundancespas.com": 2.0,
    "hotspringhottubs.com": 2.0,
    "bullfrogfactorystores.com": 10.0,
    "hotspas.com": 2.0,
}

DEFAULT_RATE_LIMIT: float = 2.0


def get_delay_for_url(url: str) -> float:
    """Return the rate-limit delay (seconds) for a given URL's domain.

    Looks up the domain in RATE_LIMITS. Falls back to DEFAULT_RATE_LIMIT
    if the domain is not configured.
    """
    domain = urlparse(url).netloc.removeprefix("www.")
    return RATE_LIMITS.get(domain, DEFAULT_RATE_LIMIT)
