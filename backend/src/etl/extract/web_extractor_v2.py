"""Enhanced website-based extraction using Gemini with strict validation rules.

Improvements over v1 (web_extractor.py):
- Strict counting rules in prompt (jet sums must match total)
- Explicit rules for tricky formats like "1 - Moto-Massage DX (2)"
- extract_categories() for targeted re-extraction with error context
- Same Gemini client/retry logic as v1
- Prompts imported from shared_prompts.py (shared with OpenAI extractor)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .shared_prompts import EXTRACTION_PROMPT, REEXTRACT_PROMPT

logger = logging.getLogger(__name__)

# Load API key
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_BACKEND_DIR / ".env")

_client: genai.Client | None = None

GEMINI_MODEL = os.environ.get("GEMINI_WEB_MODEL", "gemini-2.5-flash")
MAX_TOKENS = 16384


def _get_client() -> genai.Client:
    """Return (and lazily create) the module-level Gemini client."""
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set. Add it to backend/.env")
        _client = genai.Client(api_key=key)
    return _client


def _call_gemini(prompt: str, model_name: str) -> dict | None:
    """Call Gemini with retry logic and return parsed JSON."""
    client = _get_client()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=MAX_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            text = response.text.strip()
            return json.loads(text)

        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse error for %s (attempt %d/%d): %s",
                model_name, attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as exc:
            if "429" in str(exc) or "rate" in str(exc).lower():
                wait = 5 * (2 ** attempt)
                logger.warning("Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            else:
                logger.error("Gemini error for %s: %s", model_name, exc)
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
    """Extract all spec categories from a web page using Gemini.

    Uses the enhanced prompt with strict counting rules.

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
    return _call_gemini(prompt, model_name)


def extract_categories(
    page_text: str,
    model_name: str,
    manufacturer: str,
    series: str,
    categories: list[str],
    errors: list[str],
    year: int = 2026,
) -> dict | None:
    """Re-extract specific categories with error context.

    Used by the validation feedback loop when cross-field checks find
    errors. Sends only the failing categories back to Gemini with the
    specific error messages for context.

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
    return _call_gemini(prompt, model_name)
