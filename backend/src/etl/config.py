"""ETL extraction configuration.

Centralizes paths, model selection, manufacturer metadata, and spec
categories used throughout the extraction pipeline.
"""

from __future__ import annotations

from pathlib import Path

# === Paths ===

_PACKAGE_DIR = Path(__file__).resolve().parent
PDF_STORE_DIR: Path = _PACKAGE_DIR / "pdf_store"
DATA_OUTPUT_DIR: Path = _PACKAGE_DIR.parent / "data"

# === Gemini model selection ===
# Switched from Claude to Gemini per user request (02-04 plan).
# Gemini 2.0 Flash for cost-efficient extraction with PDF understanding.

GEMINI_MODEL: str = "gemini-2.0-flash"
GEMINI_MODEL_CHEAP: str = "gemini-2.0-flash-lite"
MAX_TOKENS: int = 8192

# === Manufacturer configuration ===

MANUFACTURERS: dict[str, dict] = {
    "sundance": {
        "series": "880 Series",
        "models": [
            "Aspen",
            "Optima",
            "Cameo",
            "Altamar",
            "Vistamar",
            "Marin",
            "Capris",
        ],
        "pdf_filename": "880-series-2026.pdf",
        "pdf_url": "https://links.imagerelay.com/cdn/574/ql/d3d8cc5af9e7477b817ca804ada71e50/25-880-ENG-Manual-Rev-D-103125-L.pdf",
    },
    "hotspring": {
        "series": "Highlife Collection",
        "models": [
            "Grandee",
            "Envoy",
            "Aria",
            "Vanguard",
            "Sovereign",
            "Prodigy",
            "Jetsetter LX",
            "Jetsetter",
        ],
        "pdf_filename": "highlife-2026.pdf",
        "pdf_url": "https://d1oxc6ayqrhsgs.cloudfront.net/hot-spring/hot-spring-highlife-collection-owners-manual-2026.pdf",
    },
    "bullfrog": {
        "series": "M Series",
        "models": ["M9", "M8", "M7", "M6"],
        "pdf_filename": "m-series.pdf",
        "pdf_url": None,  # Must be located manually -- see Phase 2 research
    },
}

# === Spec categories (the 10 data categories in SpaModel) ===

SPEC_CATEGORIES: list[str] = [
    "jet_pumps",
    "circulation_pump",
    "spa_pak",
    "topside_control",
    "jets",
    "headrests",
    "filters",
    "heater",
    "lighting",
    "cover",
]
