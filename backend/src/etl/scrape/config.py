"""Web scraping configuration: URL registry and rate limits.

Contains the URL registry for all 19 spa models across 3 manufacturers,
per-domain rate limits, and helper functions for URL-based configuration.
All pages are fetched via Playwright (no httpx branching).
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.etl.config import DATA_OUTPUT_DIR  # noqa: F401 -- re-export for scrape module

# === URL Registry ===
# Maps manufacturer key -> list of model entries.
# Each entry: model_name (matches MANUFACTURERS config), url, optional alt_url.
# All URLs are manufacturer-owned domains.

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
            "alt_url": None,
        },
        {
            "model_name": "Envoy",
            "url": "https://www.hotspring.com/shop/highlife/envoy",
            "alt_url": None,
        },
        {
            "model_name": "Aria",
            "url": "https://www.hotspring.com/shop/highlife/aria",
            "alt_url": None,
        },
        {
            "model_name": "Vanguard",
            "url": "https://www.hotspring.com/shop/highlife/vanguard",
            "alt_url": None,
        },
        {
            "model_name": "Sovereign",
            "url": "https://www.hotspring.com/shop/highlife/sovereign",
            "alt_url": None,
        },
        {
            "model_name": "Prodigy",
            "url": "https://www.hotspring.com/shop/highlife/prodigy",
            "alt_url": None,
        },
        {
            "model_name": "Jetsetter LX",
            "url": "https://www.hotspring.com/shop/highlife/jetsetter-lx",
            "alt_url": None,
        },
        {
            "model_name": "Jetsetter",
            "url": "https://www.hotspring.com/shop/highlife/jetsetter",
            "alt_url": None,
        },
    ],
    "bullfrog": [
        {
            "model_name": "M9",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9463",
            "alt_url": "https://www.bullfrogspas.com/spas/m-series-hot-tubs/m9/",
        },
        {
            "model_name": "M8",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9464",
            "alt_url": "https://www.bullfrogspas.com/spas/m-series-hot-tubs/m8/",
        },
        {
            "model_name": "M7",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9465",
            "alt_url": "https://www.bullfrogspas.com/spas/m-series-hot-tubs/m7/",
        },
        {
            "model_name": "M6",
            "url": "https://www.bullfrogfactorystores.com/models/detail/?unit_id=9466",
            "alt_url": "https://www.bullfrogspas.com/spas/m-series-hot-tubs/m6/",
        },
    ],
}

# === Rate Limits ===
# Per-domain delay in seconds between requests.

RATE_LIMITS: dict[str, float] = {
    "sundancespas.com": 2.0,
    "hotspring.com": 2.0,
    "bullfrogspas.com": 3.0,
    "bullfrogfactorystores.com": 2.0,
}

DEFAULT_RATE_LIMIT: float = 2.0


def get_delay_for_url(url: str) -> float:
    """Return the rate-limit delay (seconds) for a given URL's domain.

    Looks up the domain in RATE_LIMITS. Falls back to DEFAULT_RATE_LIMIT
    if the domain is not configured.
    """
    domain = urlparse(url).netloc.removeprefix("www.")
    return RATE_LIMITS.get(domain, DEFAULT_RATE_LIMIT)

