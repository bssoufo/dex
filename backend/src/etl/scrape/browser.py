"""Playwright-based page fetcher for JS-rendered sites.

Uses headless Chromium to render pages that require JavaScript execution
(e.g. Bullfrog Spas). Provides the same interface as PageFetcher so the
pipeline can swap fetchers transparently.

Usage::

    with PlaywrightFetcher() as fetcher:
        html = fetcher.fetch("https://www.bullfrogspas.com/spas/m-series-hot-tubs/m9/")
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class PlaywrightFetcher:
    """Synchronous browser-based fetcher using Playwright.

    Reuses a single browser instance across fetches for efficiency.
    Waits for ``networkidle`` to ensure JS content is fully rendered.
    """

    def __init__(self, default_delay: float = 3.0) -> None:
        self.default_delay = default_delay
        self._playwright = None
        self._browser = None

    def _ensure_browser(self) -> None:
        """Lazily launch Playwright and a Chromium browser instance."""
        if self._browser is not None:
            return

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        logger.info("Playwright Chromium browser launched")

    def fetch(self, url: str, delay: float | None = None) -> str:
        """Fetch a URL using a headless browser and return the rendered HTML.

        Args:
            url: The page URL to fetch.
            delay: Seconds to sleep after fetch for rate limiting.

        Returns:
            The fully rendered page HTML.

        Raises:
            Exception: On navigation failure or timeout.
        """
        self._ensure_browser()
        assert self._browser is not None

        logger.info("Browser-fetching %s", url)
        page = self._browser.new_page(user_agent=USER_AGENT)
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            html = page.content()
        finally:
            page.close()

        sleep_seconds = delay if delay is not None else self.default_delay
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        return html

    def fetch_with_fallback(
        self,
        url: str,
        alt_url: str | None = None,
        delay: float | None = None,
    ) -> str:
        """Fetch a URL, falling back to alt_url on failure.

        Same interface as PageFetcher.fetch_with_fallback.
        """
        try:
            return self.fetch(url, delay=delay)
        except Exception as exc:
            if alt_url is None:
                raise
            logger.warning(
                "Primary URL failed (%s: %s), trying fallback: %s",
                type(exc).__name__, exc, alt_url,
            )
            return self.fetch(alt_url, delay=delay)

    def close(self) -> None:
        """Close the browser and Playwright instance."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> PlaywrightFetcher:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
