"""pdfplumber wrapper for pre-extraction PDF analysis.

Provides deterministic text and table extraction from manufacturer PDFs.
Used to analyze PDF structure before building extraction prompts, and to
supplement Claude's PDF API with pre-extracted tabular data.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def analyze_pdf_structure(pdf_path: Path) -> dict:
    """Analyze a PDF's structure: page count, tables, text previews.

    Opens the PDF with pdfplumber, iterates all pages, and returns a
    summary dict with total_pages and per-page info including table
    detection and text previews (first 300 chars).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dict with ``total_pages`` (int) and ``pages`` (list of page info dicts).
        Each page info dict contains: ``page_number``, ``has_tables``,
        ``table_count``, ``text_preview``.
    """
    report: dict = {"total_pages": 0, "pages": []}

    with pdfplumber.open(pdf_path) as pdf:
        report["total_pages"] = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            page_info: dict = {
                "page_number": i + 1,
                "has_tables": False,
                "table_count": 0,
                "text_preview": "",
            }

            # Detect tables
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }
            )
            if tables:
                page_info["has_tables"] = True
                page_info["table_count"] = len(tables)

            # Text preview (first 300 chars)
            text = page.extract_text() or ""
            page_info["text_preview"] = text[:300]

            report["pages"].append(page_info)

    return report


def extract_tables(
    pdf_path: Path, page_numbers: list[int]
) -> list[dict]:
    """Extract tables from specific pages of a PDF.

    Uses pdfplumber with line-based table detection strategy to extract
    tabular data from the specified page numbers.

    Args:
        pdf_path: Path to the PDF file.
        page_numbers: 1-indexed page numbers to extract tables from.

    Returns:
        List of dicts, each with ``page`` (int) and ``data`` (list of rows,
        where each row is a list of cell strings).
    """
    results: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in page_numbers:
            if page_num < 1 or page_num > len(pdf.pages):
                continue

            page = pdf.pages[page_num - 1]  # 0-indexed internally
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }
            )

            for table in tables:
                results.append({
                    "page": page_num,
                    "data": table,
                })

    return results
