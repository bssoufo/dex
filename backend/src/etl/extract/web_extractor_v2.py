"""Enhanced website-based extraction using Gemini with strict validation rules.

Improvements over v1 (web_extractor.py):
- Strict counting rules in prompt (jet sums must match total)
- Explicit rules for tricky formats like "1 - Moto-Massage DX (2)"
- extract_categories() for targeted re-extraction with error context
- Same Gemini client/retry logic as v1
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

from ..config import SPEC_CATEGORIES

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


# Full extraction prompt with enhanced counting rules
_EXTRACTION_PROMPT = """\
You are a technical data extraction specialist. Extract structured spa \
specification data from this manufacturer web page text.

MODEL: {model_name}
MANUFACTURER: {manufacturer}
SERIES: {series}
YEAR: {year}

Extract ALL of the following spec categories from the page content below. \
Return ONLY data explicitly stated on the page. If a value is not present, \
use null. NEVER guess or infer values.

Return a single JSON object with these top-level keys:

{{
  "seating_capacity": <int or null>,
  "voltage": <int or null>,
  "amperage": <int or null>,
  "dimensions": {{
    "length_inches": <float or null>,
    "width_inches": <float or null>,
    "height_inches": <float or null>,
    "dry_weight_lbs": <float or null>,
    "filled_weight_lbs": <float or null>,
    "water_capacity_gallons": <float or null>
  }},
  "jet_pumps": {{
    "pumps": [
      {{
        "position": <int>,
        "model_name": <string or null>,
        "horsepower_continuous": <float or null>,
        "horsepower_breakdown": <float or null>,
        "speed": <"1-speed" or "2-speed" or null>,
        "amperage_max": <float or null>,
        "frame": <string or null>,
        "voltage": <int or null>,
        "part_number": null
      }}
    ],
    "diverter_valves": <int or null>,
    "total_brake_horsepower": <float or null>,
    "shared_with_series": false
  }},
  "circulation_pump": {{
    "model_name": <string or null>,
    "description": <string or null>,
    "is_dedicated": <bool or null>,
    "wattage": <int or null>,
    "part_number": null,
    "shared_with_series": false
  }},
  "spa_pak": {{
    "model_name": <string or null>,
    "display_type": <string or null>,
    "voltage": <int or null>,
    "amperage": <int or null>,
    "frequency_hz": <int or null>,
    "features": [<strings>],
    "part_number": null,
    "shared_with_series": false
  }},
  "topside_control": {{
    "model_name": <string or null>,
    "type": <string or null>,
    "features": [<strings>],
    "smart_connectivity": <string or null>,
    "part_number": null,
    "shared_with_series": false
  }},
  "jets": {{
    "total_jet_count": <int or null>,
    "jet_system_type": <"fixed" or "modular_jetpak" or null>,
    "jets_by_type": [
      {{
        "jet_type": <string>,
        "quantity": <int>,
        "zone": <string or null>,
        "part_number": null,
        "description": null
      }}
    ],
    "jetpak_count": <int or null>,
    "jetpak_options": [<strings>] or null,
    "shared_with_series": false
  }},
  "headrests": {{
    "headrests": [
      {{
        "type": <string>,
        "quantity": <int or null>,
        "part_number": null,
        "description": <string or null>
      }}
    ],
    "shared_with_series": false
  }},
  "filters": {{
    "filters": [
      {{
        "system_name": <string or null>,
        "filter_type": <string or null>,
        "filtration_area_sqft": <float or null>,
        "quantity": <int or null>,
        "description": <string or null>,
        "no_bypass": <bool or null>,
        "part_number": null
      }}
    ],
    "shared_with_series": false
  }},
  "heater": {{
    "model_name": <string or null>,
    "wattage": <int or null>,
    "voltage": <int or null>,
    "material": null,
    "part_number": null,
    "shared_with_series": false
  }},
  "lighting": {{
    "lights": [
      {{
        "location": <string>,
        "type": <string or null>,
        "description": <string or null>,
        "part_number": null
      }}
    ],
    "water_feature": <string or null>,
    "shared_with_series": false
  }},
  "cover": {{
    "model_name": <string or null>,
    "thickness": <string or null>,
    "material": <string or null>,
    "features": [<strings>],
    "length_inches": <float or null>,
    "width_inches": <float or null>,
    "part_number": null,
    "shared_with_series": false
  }}
}}

STRICT RULES:
- The sum of all jets_by_type quantities MUST equal total_jet_count exactly. \
Count carefully before responding.
- For entries like "1 - Moto-Massage DX (2)", the leading number is the count \
of that jet type, and "(2)" is the number of actual jet nozzles per unit. \
The quantity = leading number * nozzles, e.g. 1 * 2 = 2.
- Use null rather than guessing — never invent numbers.
- List ALL jet types shown on the page, do not merge or skip any.
- Convert ALL dimensions to inches (e.g., 7'3" = 87 inches, 2.21m = 87 inches).
- For HP values, extract the EXACT number stated (e.g., "2.5 HP continuous" -> 2.5).
- For Bullfrog models with total BHP, divide by pump count for per-pump HP.
- If the page lists jet types with quantities, include ALL of them.
- Part numbers are NOT expected on manufacturer websites — always null.
- Return VALID JSON only — no markdown, no code fences, no explanation.

PAGE CONTENT:
{page_text}
"""

# Targeted re-extraction prompt for specific categories with error context
_REEXTRACT_PROMPT = """\
You are a technical data extraction specialist. A previous extraction of \
this spa model had validation errors. Re-extract ONLY the specified \
categories, paying careful attention to the errors described.

MODEL: {model_name}
MANUFACTURER: {manufacturer}
SERIES: {series}
YEAR: {year}

PREVIOUS ERRORS:
{error_context}

Re-extract ONLY these categories: {categories}

STRICT RULES:
- The sum of all jets_by_type quantities MUST equal total_jet_count exactly.
- For entries like "1 - Moto-Massage DX (2)", the leading number is the count \
of that type, "(2)" is nozzles per unit. Quantity = count * nozzles.
- Use null rather than guessing — never invent numbers.
- List ALL jet types shown on the page, do not merge or skip any.
- If total_jet_count seems unreasonably high (>100), recount from the page carefully.
- Convert ALL dimensions to inches.
- Return VALID JSON with only the requested category keys. No markdown or code fences.

PAGE CONTENT:
{page_text}
"""


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
    prompt = _EXTRACTION_PROMPT.format(
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

    prompt = _REEXTRACT_PROMPT.format(
        model_name=model_name,
        manufacturer=manufacturer,
        series=series,
        year=year,
        error_context=error_context,
        categories=cat_str,
        page_text=page_text[:30000],
    )
    return _call_gemini(prompt, model_name)
