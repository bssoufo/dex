"""HTTP page fetcher with retry logic and rate limiting.

Provides a synchronous PageFetcher that wraps httpx.Client with tenacity
retry and per-request delay to respect robots.txt crawl-delay directives.
Only 19 pages total -- async is unnecessary.
"""

from __future__ import annotations

import logging
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

USER_AGENT = "DexBot/1.0 (internal-use; spa-specs-extraction)"


class PageFetcher:
    """Synchronous HTTP client with retry and rate limiting.

    Usage::

        with PageFetcher() as fetcher:
            html = fetcher.fetch("https://example.com/spa-model")

    Or with fallback URLs::

        html = fetcher.fetch_with_fallback(
            url="https://primary.com/model",
            alt_url="https://backup.com/model",
            delay=10.0,
        )
    """

    def __init__(self, default_delay: float = 2.0) -> None:
        self.default_delay = default_delay
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
    )
    def fetch(self, url: str, delay: float | None = None) -> str:
        """Fetch a URL and return the response body as text.

        Retries up to 3 times with exponential backoff on failure.
        Sleeps for *delay* seconds after the request to respect rate limits.

        Args:
            url: The page URL to fetch.
            delay: Seconds to sleep after fetch. Defaults to self.default_delay.

        Returns:
            The response body text (HTML).

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx after all retries exhausted.
        """
        logger.info("Fetching %s", url)
        response = self.client.get(url)
        response.raise_for_status()

        sleep_seconds = delay if delay is not None else self.default_delay
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        return response.text

    def fetch_with_fallback(
        self,
        url: str,
        alt_url: str | None = None,
        delay: float | None = None,
    ) -> str:
        """Fetch a URL, falling back to alt_url on failure.

        Tries the primary *url* first. If it fails (after all retries),
        tries *alt_url* if provided. Raises if both fail.

        Args:
            url: Primary URL to fetch.
            alt_url: Optional fallback URL.
            delay: Seconds to sleep after each fetch.

        Returns:
            The response body text (HTML).

        Raises:
            Exception: If both primary and fallback URLs fail.
        """
        try:
            return self.fetch(url, delay=delay)
        except Exception as exc:
            if alt_url is None:
                raise
            logger.warning(
                "Primary URL failed (%s: %s), trying fallback: %s",
                type(exc).__name__,
                exc,
                alt_url,
            )
            return self.fetch(alt_url, delay=delay)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def __enter__(self) -> PageFetcher:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
