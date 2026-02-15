"""Bullfrog M Series extraction template.

Encodes Bullfrog-specific terminology (JetPak, Simplicity filter, K1000
Premium Touch Screen), PDF page hints from the structure analysis, and
per-category extraction prompts that guide Claude to the right sections
of the m-series.pdf owner's manual (2025 version).

CRITICAL DIFFERENCE: Bullfrog uses a modular JetPak system for jets.
The jet extraction prompt is fundamentally different from Sundance and
Hot Spring -- it extracts JetPak bay count and options rather than
individual jet types and counts.
"""

from __future__ import annotations

from .base import ManufacturerTemplate


# ---------------------------------------------------------------------------
# Shared prompt fragments
# ---------------------------------------------------------------------------

_RULES = """\
RULES:
- Extract ONLY data explicitly stated in the document. Never infer or calculate values.
- If a value is not present in the document, use null.
- Include the page number(s) where you found each piece of data.
- Report your confidence level: "high" if data is clearly stated, "medium" if you had to interpret layout, "low" if uncertain.
- NOTE: This is a 2025 owner's manual. The 2026 version has not been published yet. Record this in your notes."""

_GENERAL_FIELDS_PROMPT = """\
ALSO extract these general fields for the model (include them in the "data" JSON object under a "general" key):
- seating_capacity (integer, if listed)
- dimensions: length_inches, width_inches, height_inches (convert from feet/inches to total inches as floats)
- dry_weight_lbs (float, in pounds, if listed)
- water_capacity_gallons (float, in US gallons, if listed)
- voltage (integer, typically 240)
- amperage (integer, max current draw)"""


# ---------------------------------------------------------------------------
# Page hints by category (from PDF analysis report)
# ---------------------------------------------------------------------------

_PAGE_HINTS: dict[str, str] = {
    "jet_pumps": (
        "Look in page 9 for the equipment compartment diagram showing "
        "Jet pump 1, 2, 3 positions. Page 12 mentions that M9/M8 have "
        "3 jet pumps. Page 37 has the wiring diagram (YT-9 UL) with "
        "pump voltage and speed details: Pump 1 (A2) 240V 2-speed, "
        "Pump 2 (A3) 240V 2-speed, Pump 3 (C1) 240V 2-speed. "
        "Pages 33-34 have electrical requirements (50A or 60A GFCI)."
    ),
    "circulation_pump": (
        "Look in page 9 for the equipment compartment diagram showing "
        "'Circulation pump / O3'. Page 37 wiring diagram shows "
        "circulation pump at position A1, 240V, 2-speed."
    ),
    "spa_pak": (
        "Look in page 9 for the equipment compartment diagram showing "
        "the 'Control center box'."
    ),
    "topside_control": (
        "Look in pages 12-16 for the control guide. M9/M8 use the "
        "'Premium Touch Screen Control (K1000)'. Detailed control "
        "operation documentation is in this section."
    ),
    "jets": (
        "CRITICAL: Bullfrog uses a modular JetPak system. Look in "
        "page 8 for the spa overview showing JetPaks, in-wall therapy "
        "jets, high-flow foot therapy jet, and leg therapy jets. "
        "Page 17 covers JetPak interchanging procedure. The manual "
        "does NOT list total jet counts per model because they depend "
        "on which JetPaks are installed. Extract JetPak bay count "
        "and any base jet counts mentioned."
    ),
    "headrests": (
        "Look in page 8 for the spa feature overview. 'Adjustable "
        "headrest' is listed as item 4 in the overview diagram."
    ),
    "filters": (
        "Look in page 8 for the feature overview mentioning 'Filter "
        "access' and 'Simplicity Filter'. Page 28 references filter "
        "cleaning in the winterization section."
    ),
    "heater": (
        "Look in page 9 for the equipment compartment diagram showing "
        "the 'Water heater' component."
    ),
    "lighting": (
        "Look in page 8 for the spa feature overview. 'Interior LED "
        "lights' is listed in the overview diagram."
    ),
    "cover": (
        "Look in page 32 for the dimensions table. Cover dimensions "
        "can be derived from the spa dimensions. The table lists "
        "Width, Length, and Height for M9, M8, M7, and M6."
    ),
}


# ---------------------------------------------------------------------------
# Category-specific prompt instructions
# ---------------------------------------------------------------------------

_CATEGORY_PROMPTS: dict[str, str] = {
    "jet_pumps": """\
Bullfrog lists total BHP rather than per-pump HP. Extract the total \
brake horsepower and the number of pumps for this model. If only total \
BHP is given, divide by the pump count to estimate per-pump HP and note \
this calculation in the notes field. M9 and M8 have 3 jet pumps. M7 and \
M6 may have fewer. All pumps are 240V 2-speed based on the wiring diagram.

{general_fields}

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "pumps": [
    {{
      "position": 1,
      "model_name": <string or null>,
      "horsepower_continuous": <float>,
      "horsepower_breakdown": <float or null>,
      "speed": "1-speed" | "2-speed" | "variable",
      "amperage_max": <float or null>,
      "voltage": 240
    }}
  ],
  "diverter_valves": <int or null>,
  "total_brake_horsepower": <float or null>,
  "general": {{
    "seating_capacity": <int or null>,
    "dimensions": {{
      "length_inches": <float>,
      "width_inches": <float>,
      "height_inches": <float>
    }},
    "dry_weight_lbs": <float or null>,
    "water_capacity_gallons": <float or null>,
    "voltage": <int>,
    "amperage": <int or null>
  }}
}}""",
    "circulation_pump": """\
Extract the circulation pump details. Bullfrog has a dedicated \
circulation pump shown in the equipment compartment diagram. The wiring \
diagram shows it at position A1, 240V, 2-speed (low speed K1, common L2). \
It also handles ozone (O3) integration.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "description": <string or null>,
  "is_dedicated": true,
  "wattage": <float or null>
}}""",
    "spa_pak": """\
Extract the control system (spa pak) information. Look for the \
'Control center box' in the equipment compartment diagram. Extract \
the model name, features, and any integration capabilities.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string>,
  "display_type": <string or null>,
  "voltage": <int>,
  "amperage": <int or null>,
  "frequency_hz": 60,
  "features": [<string>, ...]
}}""",
    "topside_control": """\
Extract the topside control panel details. Bullfrog M9/M8 use the \
"Premium Touch Screen Control (K1000)". Look for control features, \
display type, smart connectivity, and app integration.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "type": <string or null>,
  "features": [<string>, ...],
  "smart_connectivity": <string or null>
}}""",
    "jets": """\
CRITICAL: Bullfrog uses a modular JetPak system. Do NOT try to extract \
individual jet type counts like you would for Sundance or Hot Spring. \
Instead extract:
- jet_system_type: MUST be "modular_jetpak"
- jetpak_count: Number of JetPak bays (slots) in this model
- jetpak_options: Number of available JetPak types (typically 16+)
- total_jet_count: Base jet count without JetPaks (if listed), \
  or the count of built-in non-JetPak jets (in-wall therapy jets, \
  high-flow foot therapy jet, leg therapy jets)
- max_jet_count: Maximum jet count with all JetPaks installed (if listed)
- therapy_jet_count: Number of therapy-specific jets
- jets_by_type: Leave as empty list -- JetPak configurations are too \
  numerous to enumerate

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "total_jet_count": <int or 0>,
  "jet_system_type": "modular_jetpak",
  "jets_by_type": [],
  "jetpak_count": <int or null>,
  "jetpak_options": <int or null>,
  "therapy_jet_count": <int or null>,
  "max_jet_count": <int or null>
}}""",
    "headrests": """\
Extract headrest information. Look for 'Adjustable headrest' in the \
spa feature overview. Extract quantity and type.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "headrests": [
    {{
      "type": <string or null>,
      "quantity": <int or null>,
      "description": <string or null>
    }}
  ]
}}""",
    "filters": """\
Extract filter specifications. Bullfrog uses the Simplicity filtration \
system (different from MicroClean Ultra or Tri-X used by other \
manufacturers). Look for filter type, area, quantity, and any part \
numbers.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "filters": [
    {{
      "system_name": <string or null>,
      "filter_type": <string or null>,
      "filtration_area_sqft": <float or null>,
      "quantity": <int or null>,
      "description": <string or null>
    }}
  ]
}}""",
    "heater": """\
Extract heater specifications from the equipment compartment diagram. \
Look for 'Water heater' component, wattage, voltage, and any model \
name or part number.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "wattage": <int or null>,
  "voltage": <int>,
  "material": <string or null>
}}""",
    "lighting": """\
Extract lighting information. Look for 'Interior LED lights' in the \
spa feature overview and any exterior or accent lighting.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "lights": [
    {{
      "location": <string>,
      "type": <string>,
      "description": <string or null>
    }}
  ],
  "water_feature": <string or null>
}}""",
    "cover": """\
Extract cover specifications. The dimensions table on page 32 lists \
spa dimensions (Width, Length, Height) for each M Series model. \
Cover dimensions correspond to the spa footprint. Convert \
feet/inches to total inches. Look for any explicit cover features \
or material.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "thickness": <string or null>,
  "material": <string or null>,
  "features": [<string>, ...],
  "length_inches": <float or null>,
  "width_inches": <float or null>
}}""",
}


# ---------------------------------------------------------------------------
# Template class
# ---------------------------------------------------------------------------


class BullfrogMSeriesTemplate(ManufacturerTemplate):
    """Extraction template for Bullfrog M Series spas.

    Covers 4 models: M9, M8, M7, M6.
    PDF: m-series.pdf (46 pages, 11.0 MB, 2025 version -- 2026 not yet
    published).

    Key terminology:
      - Jets: JetPak modular system (bays, interchangeable cartridges)
      - Filter: Simplicity filtration
      - Control: Premium Touch Screen Control K1000 (M9/M8)
      - Pumps: 2-speed, 240V
      - Equipment: Control center box, EOS mixing module, AOP/Ozone

    CRITICAL: Bullfrog's JetPak system is fundamentally different from
    fixed-jet manufacturers. The jet extraction prompt targets bay count
    and base jet count rather than individual jet types.
    """

    @property
    def manufacturer_name(self) -> str:
        return "bullfrog"

    @property
    def series_name(self) -> str:
        return "M Series"

    @property
    def models(self) -> list[str]:
        return ["M9", "M8", "M7", "M6"]

    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        """Build a full extraction prompt for a Bullfrog model and category."""
        page_hints = self.get_page_hints(spec_category)
        category_instructions = _CATEGORY_PROMPTS.get(spec_category, "")

        # Inject general fields prompt into jet_pumps category
        if spec_category == "jet_pumps":
            category_instructions = category_instructions.format(
                general_fields=_GENERAL_FIELDS_PROMPT,
            )

        prompt = (
            f"Extract the {spec_category.replace('_', ' ')} specifications "
            f"for the Bullfrog {model_name} ({self.series_name}, 2025) "
            f"from this owner's manual.\n\n"
            f"{_RULES}\n\n"
            f"{page_hints}\n\n"
            f"{category_instructions}"
        )
        return prompt

    def get_page_hints(self, spec_category: str) -> str:
        """Return page location hints for the given category."""
        return _PAGE_HINTS.get(spec_category, "")
