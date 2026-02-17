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
            "url": "https://www.hotspring.com/shop/highlife/grandee",
            "alt_url": "https://www.hotspringhottubs.com/grandee/",
        },
        {
            "model_name": "Envoy",
            "url": "https://www.hotspring.com/shop/highlife/envoy",
            "alt_url": "https://www.hotspringhottubs.com/envoy/",
        },
        {
            "model_name": "Aria",
            "url": "https://www.hotspring.com/shop/highlife/aria",
            "alt_url": "https://www.hotspringhottubs.com/aria/",
        },
        {
            "model_name": "Vanguard",
            "url": "https://www.hotspring.com/shop/highlife/vanguard",
            "alt_url": "https://www.hotspringhottubs.com/vanguard/",
        },
        {
            "model_name": "Sovereign",
            "url": "https://www.hotspring.com/shop/highlife/sovereign",
            "alt_url": "https://www.hotspringhottubs.com/sovereign/",
        },
        {
            "model_name": "Prodigy",
            "url": "https://www.hotspring.com/shop/highlife/prodigy",
            "alt_url": "https://www.hotspringhottubs.com/prodigy/",
        },
        {
            "model_name": "Jetsetter LX",
            "url": "https://olympichottub.com/hot-tub/jetsetter-lx/",
            "alt_url": "https://www.hotspring.com/shop/highlife/jetsetter-lx",
        },
        {
            "model_name": "Jetsetter",
            "url": "https://www.hotspring.com/shop/highlife/jetsetter",
            "alt_url": "https://www.hotspringhottubs.com/jetsetter/",
        },
    ],
    "bullfrog": [
        {
            "model_name": "M9",
            "url": "https://www.skillfulhome.com/products/bullfrog-spas-hot-tubs/bullfrog-spas-m-series-hot-tubs/bullfrog-spas-model-m9/",
            "alt_url": "https://patiosplash.com/bullfrog-spas/m-series/m9/",
        },
        {
            "model_name": "M8",
            "url": "https://patiosplash.com/bullfrog-spas/m-series/m8/",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m8/",
        },
        {
            "model_name": "M7",
            "url": "https://patiosplash.com/bullfrog-spas/m-series/m7/",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m7/",
        },
        {
            "model_name": "M6",
            "url": "https://www.skillfulhome.com/products/bullfrog-spas-hot-tubs/bullfrog-spas-m-series-hot-tubs/bullfrog-spas-m6/",
            "alt_url": "https://www.hotspas.com/hot-tubs/bullfrog-spas/m-series/bullfrog-model-m6/",
        },
    ],
}

# === Rate Limits ===
# Per-domain delay in seconds between requests.
# Bullfrog robots.txt specifies crawl-delay of 10 seconds.

RATE_LIMITS: dict[str, float] = {
    "sundancespas.com": 2.0,
    "hotspring.com": 2.0,
    "hotspringhottubs.com": 2.0,
    "olympichottub.com": 2.0,
    "patiosplash.com": 2.0,
    "skillfulhome.com": 2.0,
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
