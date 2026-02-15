"""Google Gemini PDF extraction with structured outputs.

Wraps the ``google-genai`` SDK (new unified API) to extract spec data
from manufacturer PDFs.  Uploads PDF files via the Gemini File API for
efficient multi-category extraction, and requests JSON responses matching
the CategoryExtraction schema.

Replaces the original Claude extractor (02-04 plan: user requested Gemini
instead of Claude for extraction LLM).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator

from ..config import GEMINI_MODEL, MAX_TOKENS, SPEC_CATEGORIES

if TYPE_CHECKING:
    from ..templates.base import ManufacturerTemplate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load API key from backend/.env
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_BACKEND_DIR / ".env")

_api_key = os.environ.get("GEMINI_API_KEY")
if not _api_key:
    logger.warning("GEMINI_API_KEY not found in environment or .env file")

# Initialize the client (singleton for the module)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return (and lazily create) the module-level Gemini client."""
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ExtractionError(
                "GEMINI_API_KEY not set. Add it to backend/.env"
            )
        _client = genai.Client(api_key=key)
    return _client


# ---------------------------------------------------------------------------
# Structured output model (LLM-agnostic -- same as original)
# ---------------------------------------------------------------------------


class CategoryExtraction(BaseModel):
    """Raw extraction result for a single spec category.

    The ``raw_data_json`` field holds a JSON string (not a dict) because
    this keeps the extraction data flexible for arbitrary key/value pairs.
    The ``data`` property parses it lazily.
    """

    model_name: str
    spec_category: str
    page_numbers: list[int] = Field(
        description="Page numbers where data was found",
    )
    section_title: str | None = None
    confidence: Literal["high", "medium", "low"]
    notes: str | None = None
    raw_data_json: str = Field(
        description=(
            "JSON string containing the extracted spec data as a "
            "flat or nested object whose keys match the target "
            "Pydantic model fields for this spec category"
        ),
    )

    # -- convenience accessor -------------------------------------------------

    @property
    def data(self) -> dict:
        """Parse ``raw_data_json`` into a Python dict."""
        try:
            return json.loads(self.raw_data_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    # -- validation -----------------------------------------------------------

    @field_validator("raw_data_json", mode="before")
    @classmethod
    def _coerce_data_to_json_str(cls, v: object) -> str:
        """Accept both a JSON string and a plain dict (for tests)."""
        if isinstance(v, dict):
            return json.dumps(v)
        return str(v)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Raised when a Gemini API extraction call fails."""

    def __init__(
        self,
        message: str,
        pdf_path: Path | str | None = None,
        category: str | None = None,
    ) -> None:
        self.pdf_path = pdf_path
        self.category = category
        super().__init__(message)


# ---------------------------------------------------------------------------
# PDF file cache (upload once, reuse across categories)
# ---------------------------------------------------------------------------

_uploaded_files: dict[str, types.File] = {}


def _upload_pdf(pdf_path: Path) -> types.File:
    """Upload a PDF to Gemini File API, caching by path.

    Gemini File API uploads are reusable for 48 hours.  We cache locally
    within the process to avoid re-uploading for each category extraction.
    """
    client = _get_client()
    path_key = str(pdf_path.resolve())

    if path_key in _uploaded_files:
        cached = _uploaded_files[path_key]
        # Verify the file is still active
        try:
            file_info = client.files.get(name=cached.name)
            if file_info.state == "ACTIVE":
                return cached
        except Exception:
            pass  # Re-upload if verification fails

    print(f"  Uploading PDF to Gemini: {pdf_path.name}...")
    uploaded = client.files.upload(
        file=str(pdf_path),
        config=types.UploadFileConfig(
            display_name=pdf_path.name,
            mime_type="application/pdf",
        ),
    )

    # Wait for processing to complete
    while uploaded.state == "PROCESSING":
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state != "ACTIVE":
        raise ExtractionError(
            f"PDF upload failed (state={uploaded.state}): {pdf_path.name}",
            pdf_path=pdf_path,
        )

    _uploaded_files[path_key] = uploaded
    print(f"  PDF uploaded successfully: {uploaded.name}")
    return uploaded


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------


_SYSTEM_INSTRUCTION = (
    "You are a technical data extraction specialist. You extract "
    "structured specification data from manufacturer PDF manuals for "
    "hot tubs/spas. You MUST respond with valid JSON only -- no "
    "markdown, no code fences, no explanation text. Just the raw "
    "JSON object matching the requested schema.\n\n"
    "The JSON object must have these exact fields:\n"
    '- "model_name": string (the spa model name)\n'
    '- "spec_category": string (the category being extracted)\n'
    '- "page_numbers": array of integers (pages where data was found)\n'
    '- "section_title": string or null\n'
    '- "confidence": "high" | "medium" | "low"\n'
    '- "notes": string or null\n'
    '- "raw_data_json": string (a JSON-encoded string of the actual '
    "extracted data -- must be a valid JSON string, not a raw object)"
)


def _parse_gemini_response(response_text: str) -> CategoryExtraction:
    """Parse a Gemini response into a CategoryExtraction.

    Handles common response formats: plain JSON, markdown-fenced JSON,
    and nested JSON with raw_data_json as either string or dict.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            f"Failed to parse Gemini JSON response: {exc}\n"
            f"Response text (first 500 chars): {text[:500]}"
        ) from exc

    # If raw_data_json is a dict, convert to JSON string for Pydantic
    if isinstance(parsed.get("raw_data_json"), dict):
        parsed["raw_data_json"] = json.dumps(parsed["raw_data_json"])

    return CategoryExtraction.model_validate(parsed)


# ---------------------------------------------------------------------------
# Core extraction functions
# ---------------------------------------------------------------------------


def extract_spec_category(
    pdf_path: Path,
    extraction_prompt: str,
    *,
    model: str | None = None,
) -> CategoryExtraction:
    """Extract a single spec category from a PDF via the Gemini API.

    Uploads the PDF (or reuses cached upload) and sends the extraction
    prompt with the full document context.

    Args:
        pdf_path: Path to the manufacturer PDF file.
        extraction_prompt: The full extraction prompt (from a
            ManufacturerTemplate).
        model: Gemini model to use.  Defaults to ``GEMINI_MODEL``.

    Returns:
        A ``CategoryExtraction`` with metadata and the raw data as a
        JSON string in ``raw_data_json``.

    Raises:
        ExtractionError: On API or parsing failures.
    """
    if not pdf_path.exists():
        raise ExtractionError(
            f"PDF not found: {pdf_path}", pdf_path=pdf_path
        )

    client = _get_client()

    # Upload or retrieve cached PDF
    uploaded_file = _upload_pdf(pdf_path)

    # Build the request
    model_name = model or GEMINI_MODEL

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type="application/pdf",
                        ),
                        types.Part.from_text(text=extraction_prompt),
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                temperature=0.1,
                max_output_tokens=MAX_TOKENS,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        raise ExtractionError(
            f"Gemini API error extracting from {pdf_path.name}: {exc}",
            pdf_path=pdf_path,
        ) from exc

    # Parse the structured output
    try:
        result = _parse_gemini_response(response.text)
    except Exception as exc:
        raise ExtractionError(
            f"Failed to parse extraction response for {pdf_path.name}: {exc}",
            pdf_path=pdf_path,
        ) from exc

    return result


def extract_model_specs(
    pdf_path: Path,
    template: ManufacturerTemplate,
    model_name: str,
    *,
    model: str | None = None,
) -> dict[str, CategoryExtraction]:
    """Extract all spec categories for a single spa model.

    Iterates over ``SPEC_CATEGORIES`` from config, builds the prompt
    via the manufacturer template, and calls ``extract_spec_category``
    for each.  Failures on individual categories are logged but do not
    abort the remaining extractions.

    Args:
        pdf_path: Path to the manufacturer PDF file.
        template: The manufacturer-specific template instance.
        model_name: Spa model name (e.g. ``"Aspen"``).
        model: Gemini model to use (optional override).

    Returns:
        Dict mapping category name (str) to ``CategoryExtraction``.
        Categories that failed extraction are omitted from the dict.
    """
    results: dict[str, CategoryExtraction] = {}

    for category in SPEC_CATEGORIES:
        try:
            prompt = template.get_extraction_prompt(model_name, category)
            extraction = extract_spec_category(
                pdf_path, prompt, model=model
            )
            results[category] = extraction
            print(
                f"Extracting {model_name} / {category}... "
                f"({extraction.confidence})"
            )
        except ExtractionError as exc:
            logger.error(
                "Failed to extract %s / %s: %s",
                model_name,
                category,
                exc,
            )
            print(f"Extracting {model_name} / {category}... FAILED: {exc}")

    return results
