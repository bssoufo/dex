"""HTML content extraction and caching.

Handles HTML-to-clean-text conversion via BeautifulSoup, and caches raw
HTML to disk so re-extraction retries don't need to re-fetch pages.

Cache is keyed by URL hash + date, with a 24-hour TTL.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent / "cache"

# Tags removed entirely before text extraction
_REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe"]

# Cache TTL in seconds (24 hours)
_CACHE_TTL = 86400


def _cache_key(url: str) -> str:
    """Generate a filesystem-safe cache key from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cache_path(url: str) -> Path:
    """Return the cache file path for a URL."""
    return _CACHE_DIR / f"{_cache_key(url)}.html"


def get_cached_html(url: str) -> str | None:
    """Return cached HTML for a URL if it exists and is fresh (< 24h)."""
    path = _cache_path(url)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > _CACHE_TTL:
        logger.debug("Cache expired for %s (%.0fs old)", url, age)
        return None
    logger.info("Cache hit for %s", url)
    return path.read_text(encoding="utf-8")


def cache_html(url: str, html: str) -> None:
    """Write raw HTML to the cache directory."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(url)
    path.write_text(html, encoding="utf-8")
    logger.debug("Cached %d bytes for %s", len(html), url)


def html_to_text(html: str) -> str:
    """Convert raw HTML to clean text suitable for LLM extraction.

    Removes scripts, styles, navigation, footer, and header elements,
    then returns the visible text with whitespace normalized.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(_REMOVE_TAGS):
        tag.decompose()

    return soup.get_text(separator="\n", strip=True)
