"""OpenAI-based extraction for dual-LLM validation pipeline.

Mirrors web_extractor_v2.py interface exactly so both extractors are
interchangeable. Uses the same shared prompts as the Gemini extractor
to prevent prompt drift.

Functions:
    extract() — full schema extraction from page text
    extract_categories() — targeted re-extraction with error context
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from .shared_prompts import EXTRACTION_PROMPT, REEXTRACT_PROMPT, REVIEW_PROMPT

logger = logging.getLogger(__name__)

# Load API key
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_BACKEND_DIR / ".env")

_client = None

OPENAI_MODEL = os.environ.get("OPENAI_WEB_MODEL", "gpt-5.2")
MAX_TOKENS = 16384


def _get_client():
    """Return (and lazily create) the module-level OpenAI client."""
    global _client
    if _client is None:
        import openai

        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set. Add it to backend/.env")
        _client = openai.OpenAI(api_key=key)
    return _client


def _call_openai(prompt: str, model_name: str) -> dict | None:
    """Call OpenAI with retry logic and return parsed JSON."""
    client = _get_client()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_completion_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content.strip()
            return json.loads(text)

        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse error for %s (attempt %d/%d): %s",
                model_name, attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as exc:
            exc_str = str(exc)
            if "429" in exc_str or "rate" in exc_str.lower():
                wait = 5 * (2 ** attempt)
                logger.warning("Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            else:
                logger.error("OpenAI error for %s: %s", model_name, exc)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

    return None


def extract(
    page_text: str,
    model_name: str,
    manufacturer: str,
    series: str,
    year: int = 2026,
) -> dict | None:
    """Extract all spec categories from a web page using OpenAI.

    Uses the same shared prompt as the Gemini extractor.

    Args:
        page_text: Clean text content of the manufacturer web page.
        model_name: Model name (e.g. "Vanguard").
        manufacturer: Manufacturer key (e.g. "hotspring").
        series: Series name (e.g. "Highlife Collection").
        year: Model year.

    Returns:
        Dict with all spec categories, or None on failure.
    """
    prompt = EXTRACTION_PROMPT.format(
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
        page_text=page_text[:30000],
    )
    return _call_openai(prompt, model_name)


def review(
    gemini_data: dict,
    page_text: str,
    model_name: str,
    manufacturer: str,
    series: str,
    year: int = 2026,
) -> dict | None:
    """Review Gemini's extraction and return corrected JSON.

    Args:
        gemini_data: The Gemini extraction result to review.
        page_text: Clean text content of the manufacturer web page.
        model_name: Model name (e.g. "Vanguard").
        manufacturer: Manufacturer key (e.g. "hotspring").
        series: Series name (e.g. "Highlife Collection").
        year: Model year.

    Returns:
        Dict with corrected spec categories, or None on failure.
    """
    prompt = REVIEW_PROMPT.format(
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
        gemini_json=json.dumps(gemini_data, indent=2, default=str),
        page_text=page_text[:30000],
    )
    return _call_openai(prompt, model_name)


def extract_categories(
    page_text: str,
    model_name: str,
    manufacturer: str,
    series: str,
    categories: list[str],
    errors: list[str],
    year: int = 2026,
) -> dict | None:
    """Re-extract specific categories with error context using OpenAI.

    Args:
        page_text: Clean text content of the manufacturer web page.
        model_name: Model name.
        manufacturer: Manufacturer key.
        series: Series name.
        categories: List of category keys to re-extract (e.g. ["jets"]).
        errors: List of error message strings for context.
        year: Model year.

    Returns:
        Dict with only the requested category keys, or None on failure.
    """
    error_context = "\n".join(f"- {e}" for e in errors)
    cat_str = ", ".join(categories)

    prompt = REEXTRACT_PROMPT.format(
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
        error_context=error_context,
        categories=cat_str,
        page_text=page_text[:30000],
    )
    return _call_openai(prompt, model_name)
