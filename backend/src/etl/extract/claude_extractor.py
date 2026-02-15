"""Claude PDF API extraction with structured outputs.

Wraps the Anthropic messages API to extract spec data from manufacturer
PDFs.  Uses document content blocks with cache_control for cost-efficient
multi-category extraction, and output_config with json_schema for
guaranteed schema compliance via constrained decoding.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anthropic
from anthropic import transform_schema
from pydantic import BaseModel, Field, field_validator

from ..config import CLAUDE_MODEL, MAX_TOKENS, SPEC_CATEGORIES

if TYPE_CHECKING:
    from ..templates.base import ManufacturerTemplate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output model
# ---------------------------------------------------------------------------


class CategoryExtraction(BaseModel):
    """Raw extraction result for a single spec category from Claude.

    The ``raw_data_json`` field holds a JSON string (not a dict) because
    the Anthropic structured-output schema sets ``additionalProperties:
    false`` on object types, which would prevent Claude from returning
    arbitrary key/value pairs.  The ``data`` property parses it lazily.
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
    """Raised when a Claude API extraction call fails."""

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
# Core extraction functions
# ---------------------------------------------------------------------------


def extract_spec_category(
    pdf_path: Path,
    extraction_prompt: str,
    *,
    model: str | None = None,
) -> CategoryExtraction:
    """Extract a single spec category from a PDF via the Claude API.

    Sends the full PDF as a base64-encoded document content block with
    ``cache_control`` enabled so that subsequent calls against the same
    PDF reuse cached tokens at 90% cost discount.

    Args:
        pdf_path: Path to the manufacturer PDF file.
        extraction_prompt: The full extraction prompt (from a
            ManufacturerTemplate).
        model: Claude model to use.  Defaults to ``CLAUDE_MODEL``.

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

    # Read and base64-encode the PDF
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    # Build the structured output schema from the Pydantic model
    output_schema = transform_schema(CategoryExtraction)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model or CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": extraction_prompt,
                        },
                    ],
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": output_schema,
                }
            },
        )
    except anthropic.APIError as exc:
        raise ExtractionError(
            f"Claude API error extracting from {pdf_path.name}: {exc}",
            pdf_path=pdf_path,
        ) from exc

    # Parse the structured output
    try:
        result = CategoryExtraction.model_validate_json(
            response.content[0].text
        )
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
        model: Claude model to use (optional override).

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
