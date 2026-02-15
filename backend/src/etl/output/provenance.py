"""Builds SourceReference metadata from extraction results.

Every data point in the Dex system is traceable back to a page and
section in a source document.  This module translates the LLM's
extraction metadata (page numbers, section titles) into the
``SourceReference`` model defined in the Phase 1 schema.
"""

from __future__ import annotations

from datetime import date

from ...schema.parts import SourceReference
from ..extract.gemini_extractor import CategoryExtraction


def build_source_reference(
    pdf_filename: str,
    extraction: CategoryExtraction,
    accessed_date: str | None = None,
) -> SourceReference:
    """Create a SourceReference from a single category extraction.

    Args:
        pdf_filename: Name of the PDF file (e.g. ``"880-series-2026.pdf"``).
        extraction: The ``CategoryExtraction`` result.
        accessed_date: ISO date string (YYYY-MM-DD).  Defaults to today.

    Returns:
        A ``SourceReference`` instance with ``source_type="pdf"``.
    """
    return SourceReference(
        source_type="pdf",
        document_name=pdf_filename,
        page_number=(
            extraction.page_numbers[0]
            if extraction.page_numbers
            else None
        ),
        section=extraction.section_title,
        accessed_date=accessed_date or date.today().isoformat(),
    )


def build_all_source_refs(
    pdf_filename: str,
    extractions: dict[str, CategoryExtraction],
    accessed_date: str | None = None,
) -> list[SourceReference]:
    """Build deduplicated source references from all category extractions.

    Produces one ``SourceReference`` per unique (page_number, section)
    pair, avoiding duplicates when multiple categories reference the
    same page and section.

    Args:
        pdf_filename: Name of the PDF file.
        extractions: Dict mapping category name to
            ``CategoryExtraction``.
        accessed_date: ISO date string.  Defaults to today.

    Returns:
        List of deduplicated ``SourceReference`` instances.
    """
    seen: set[tuple[int | None, str | None]] = set()
    refs: list[SourceReference] = []

    for extraction in extractions.values():
        ref = build_source_reference(
            pdf_filename, extraction, accessed_date
        )
        key = (ref.page_number, ref.section)
        if key not in seen:
            seen.add(key)
            refs.append(ref)

    return refs
