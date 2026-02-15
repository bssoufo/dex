"""Sundance 880 Series extraction template.

Encodes Sundance-specific terminology (Fluidix, SmartTub, MicroClean Ultra,
SunGlow LED), PDF page hints from the structure analysis, and per-category
extraction prompts that guide Claude to the right sections of the
880-series-2026.pdf owner's manual.
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
- Report your confidence level: "high" if data is clearly stated, "medium" if you had to interpret layout, "low" if uncertain."""

_GENERAL_FIELDS_PROMPT = """\
ALSO extract these general fields for the model (include them in the "data" JSON object under a "general" key):
- seating_capacity (integer)
- dimensions: length_inches, width_inches, height_inches (all in inches, as floats)
- dry_weight_lbs (float, in pounds)
- water_capacity_gallons (float, in US gallons)
- voltage (integer, typically 240)
- amperage (integer, max current draw for the model's pump configuration)"""


# ---------------------------------------------------------------------------
# Page hints by category (from PDF analysis report)
# ---------------------------------------------------------------------------

_PAGE_HINTS: dict[str, str] = {
    "jet_pumps": (
        "Look in page 22 for electrical requirements and pump system "
        "configurations (1/2/3-pump systems with amperage). Pages 90-92 "
        "have wiring diagrams with pump voltage, amperage, and speed "
        "details. Per-model massage selector diagrams on pages 29, 32, "
        "35, 38, 41, 44, 47 show which pumps are assigned to each model."
    ),
    "circulation_pump": (
        "Look in pages 20-21 for equipment location diagrams that "
        "reference the circulation pump. Details are sparse in text."
    ),
    "spa_pak": (
        "Look in pages 20-21 for the equipment diagram showing the "
        "control board. Pages 90-92 have wiring diagrams referencing "
        "the circuit board."
    ),
    "topside_control": (
        "Look in pages 49-70 for SmartTub touchscreen control "
        "documentation including registration and control operations."
    ),
    "jets": (
        "Look in per-model feature pages for jet types and counts. "
        "Each model has labeled diagrams with quantities: "
        "Aspen pages 28-30, Optima 31-33, Cameo 34-36, "
        "Altamar 37-39, Vistamar 40-42, Marin 43-45, Capri 46-48. "
        "Jet types include Fluidix ST, Fluidix Nex, Focus, etc."
    ),
    "headrests": (
        "Look in per-model feature pages (pages 28-48). Headrests "
        "are listed as 'Pillows' with quantities (e.g., 'Pillows 4 ea.')."
    ),
    "filters": (
        "Look in pages 74-76 for filter cartridge maintenance. "
        "MicroClean Ultra filtration system is referenced there."
    ),
    "heater": (
        "Look in page 62 for heat settings and pages 86-87 for heater "
        "troubleshooting. The heater is typically a Smart Heater at "
        "5500W for 880 Series models."
    ),
    "lighting": (
        "Look in per-model feature pages (pages 28-48). Each model "
        "lists lights with quantities (e.g., 'Lights 2 ea.', "
        "'LED Light Lenses'). SunGlow LED system is the brand name."
    ),
    "cover": (
        "Cover dimensions are NOT in this manual. If any cover "
        "information is found, extract it; otherwise return null values. "
        "Cover specs will be filled from web scraping in a later phase."
    ),
}


# ---------------------------------------------------------------------------
# Category-specific prompt instructions
# ---------------------------------------------------------------------------

_CATEGORY_PROMPTS: dict[str, str] = {
    "jet_pumps": """\
Look for pump count, HP ratings (continuous duty horsepower), speed type \
(1-speed or 2-speed), frame size, and amperage. Sundance 880 Series uses \
56 Frame pumps. The number of pumps varies by model (1, 2, or 3 pumps). \
Look in the specifications table and wiring diagrams.

{general_fields}

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "pumps": [
    {{
      "position": 1,
      "horsepower_continuous": <float>,
      "horsepower_breakdown": <float or null>,
      "speed": "1-speed" | "2-speed" | "variable",
      "amperage_max": <float or null>,
      "frame": "56 Frame" or null,
      "voltage": 240
    }}
  ],
  "diverter_valves": <int or null>,
  "total_brake_horsepower": <float or null>,
  "general": {{
    "seating_capacity": <int>,
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
Sundance 880 Series uses a dedicated circulation pump for continuous \
filtration. Look for wattage, model name, and whether it is a dedicated \
(always-on low-flow) circulation pump.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "description": <string or null>,
  "is_dedicated": true,
  "wattage": <float or null>
}}""",
    "spa_pak": """\
Look for the control system name. Sundance uses the Advanced Touch Control \
system. Extract the model name, display type, voltage, features, and any \
smart home integration capabilities.

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
Extract the topside control panel details. Sundance features SmartTub \
System connectivity. Look for control panel type, features (touchscreen, \
icon-driven menus, WiFi/Bluetooth, app control), and any model name/number.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "type": <string or null>,
  "features": [<string>, ...],
  "smart_connectivity": <string or null>
}}""",
    "jets": """\
Extract total jet count for this specific model. Sundance uses Fluidix \
jets (Fluidix ST, Fluidix Nex, Focus, etc.). Extract the total count and \
the breakdown by jet type with quantities. Each model has different jet \
counts and type distributions shown in the labeled feature diagrams.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "total_jet_count": <int>,
  "jet_system_type": "fixed",
  "jets_by_type": [
    {{
      "jet_type": <string>,
      "quantity": <int>,
      "zone": <string or null>
    }}
  ]
}}""",
    "headrests": """\
Extract pillow/headrest count and type for this specific model. In the \
Sundance feature diagrams, headrests are listed as "Pillows" with a \
quantity (e.g., "Pillows 4 ea.").

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
Extract filter information. Sundance uses the MicroClean Ultra filtration \
system. Look for filtration area (square feet), filter quantity, filter \
type (cartridge), and any part numbers.

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
Extract heater specifications. Sundance uses the Smart Heater system. \
Look for wattage (typically 5500W at 240V for 880 Series), voltage, \
heater model name, and any part numbers.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "wattage": <int or null>,
  "voltage": <int>,
  "material": <string or null>
}}""",
    "lighting": """\
Extract lighting information. Sundance uses the SunGlow LED system. \
Look for interior lighting, waterfall lighting, exterior accent lighting, \
footwell lighting, grab bar lighting, and light counts from the per-model \
feature diagrams.

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
Extract spa cover specifications if present. Look for cover dimensions \
(length, width), thickness, material, and any features. Note: cover \
dimensions may not be in this owner's manual.

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


class Sundance880Template(ManufacturerTemplate):
    """Extraction template for Sundance 880 Series spas.

    Covers 7 models: Aspen, Optima, Cameo, Altamar, Vistamar, Marin, Capri.
    PDF: 880-series-2026.pdf (92 pages, 24.4 MB).

    Key terminology:
      - Jets: Fluidix ST, Fluidix Nex, Focus
      - Filter: MicroClean Ultra
      - Control: Advanced Touch Control, SmartTub System
      - Lighting: SunGlow LED
      - Pumps: 56 Frame, 1-speed or 2-speed
    """

    @property
    def manufacturer_name(self) -> str:
        return "sundance"

    @property
    def series_name(self) -> str:
        return "880 Series"

    @property
    def models(self) -> list[str]:
        return [
            "Aspen",
            "Optima",
            "Cameo",
            "Altamar",
            "Vistamar",
            "Marin",
            "Capri",
        ]

    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        """Build a full extraction prompt for a Sundance model and category."""
        page_hints = self.get_page_hints(spec_category)
        category_instructions = _CATEGORY_PROMPTS.get(spec_category, "")

        # Inject general fields prompt into jet_pumps category
        if spec_category == "jet_pumps":
            category_instructions = category_instructions.format(
                general_fields=_GENERAL_FIELDS_PROMPT,
            )

        prompt = (
            f"Extract the {spec_category.replace('_', ' ')} specifications "
            f"for the Sundance {model_name} ({self.series_name}, 2026) "
            f"from this owner's manual.\n\n"
            f"{_RULES}\n\n"
            f"{page_hints}\n\n"
            f"{category_instructions}"
        )
        return prompt

    def get_page_hints(self, spec_category: str) -> str:
        """Return page location hints for the given category."""
        return _PAGE_HINTS.get(spec_category, "")
