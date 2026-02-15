"""ETL pipeline for extracting spa specifications from manufacturer PDFs.

Downloads manufacturer owner's manuals, extracts spec data using Google
Gemini with PDF understanding, validates against the Pydantic schema,
and writes JSON data files.
"""
