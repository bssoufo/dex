"""ETL pipeline for extracting spa specifications from manufacturer PDFs.

Downloads manufacturer owner's manuals, extracts spec data using Claude's
PDF API with structured outputs, validates against the Pydantic schema,
and writes JSON data files.
"""
