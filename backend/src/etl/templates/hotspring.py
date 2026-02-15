"""Hot Spring Highlife Collection extraction template.

Encodes Hot Spring-specific terminology (Wavemaster, SilentFlo 5000,
IQ 2020, Tri-X, Moto-Massage DX), PDF page hints from the structure
analysis, and per-category extraction prompts that guide Claude to the
right sections of the highlife-2026.pdf owner's manual.
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
- filled_weight_lbs (float, in pounds)
- water_capacity_gallons (float, in US gallons)
- voltage (integer, typically 230)
- amperage (integer or string if dual circuit, e.g. "20A+30A")"""


# ---------------------------------------------------------------------------
# Page hints by category (from PDF analysis report)
# ---------------------------------------------------------------------------

_PAGE_HINTS: dict[str, str] = {
    "jet_pumps": (
        "Look in per-model jet diagrams on pages 25-32. Each model has "
        "a diagram showing pump assignments (Pump 1 System 1, Pump 1 "
        "System 2, etc.) with jet types per zone. Hot Spring uses "
        "Wavemaster pumps (9000 series, 9200 series). Model pages: "
        "Grandee p25, Envoy p26, Vanguard p27, Aria p28, Sovereign p29, "
        "Prodigy p30, Jetsetter LX p31, Jetsetter p32."
    ),
    "circulation_pump": (
        "Look in pages 41-42 for the SilentFlo 5000 circulation pump "
        "referenced in the troubleshooting/service section. Also check "
        "page 7 for features overview."
    ),
    "spa_pak": (
        "Look in page 7 for the IQ 2020 control system features "
        "overview. Page 46 may list model numbers. The IQ 2020 "
        "integrates with the FreshWater salt system."
    ),
    "topside_control": (
        "Look in pages 17-24 for detailed touch screen control "
        "documentation. The IQ 2020 touchscreen includes Bluetooth "
        "and WiFi connectivity."
    ),
    "jets": (
        "Look in per-model jet diagrams on pages 25-32. Each model "
        "shows jet types by zone: Moto-Massage DX, SmartJet, "
        "HydroStream, HighFlow, Rotary Hydromassage, Directional "
        "Hydromassage, Directional Precision. Hot Spring has the most "
        "detailed jet breakdown of all 3 manufacturers. Model pages: "
        "Grandee p25, Envoy p26, Vanguard p27, Aria p28, Sovereign p29, "
        "Prodigy p30, Jetsetter LX p31, Jetsetter p32."
    ),
    "headrests": (
        "Look in page 7 for the features overview. 'Comfort Pillow' "
        "is referenced in the spa features section."
    ),
    "filters": (
        "Look in page 34 for filter maintenance information and page "
        "45 for the master spec table which lists filter area in sq ft. "
        "Hot Spring uses the Tri-X filter with no-bypass design."
    ),
    "heater": (
        "Look in pages 14-15 for heater maintenance and page 45 for "
        "the master spec table which lists heater wattage per model. "
        "Hot Spring uses the No-Fault heater system."
    ),
    "lighting": (
        "Look in page 7 for the features overview. Multi-zone LED "
        "lighting with water feature lighting is mentioned there."
    ),
    "cover": (
        "Look in page 45 for the master spec table. Spa footprint "
        "dimensions listed there can be used for cover sizing. "
        "Extract any explicit cover information if present."
    ),
}


# ---------------------------------------------------------------------------
# Category-specific prompt instructions
# ---------------------------------------------------------------------------

_CATEGORY_PROMPTS: dict[str, str] = {
    "jet_pumps": """\
Look for pump model names (Wavemaster 9000, 9200 series), HP ratings, \
speed type, and which pump powers which jet system. Hot Spring names \
their pumps (e.g., Wavemaster 9200) rather than just listing HP. Extract \
pump assignments from the per-model jet diagrams.

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
    "seating_capacity": <int>,
    "dimensions": {{
      "length_inches": <float>,
      "width_inches": <float>,
      "height_inches": <float>
    }},
    "dry_weight_lbs": <float or null>,
    "filled_weight_lbs": <float or null>,
    "water_capacity_gallons": <float or null>,
    "voltage": <int>,
    "amperage": <int or null>
  }}
}}""",
    "circulation_pump": """\
Hot Spring Highlife Collection uses the SilentFlo 5000 dedicated \
circulation pump for continuous filtration. This is a dedicated, \
always-on pump. Look for wattage, model name, and any part numbers.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "description": <string or null>,
  "is_dedicated": true,
  "wattage": <float or null>
}}""",
    "spa_pak": """\
Hot Spring uses the IQ 2020 control system with FreshWater salt system \
integration. Extract the control system name, display type, voltage, \
features, and integration capabilities.

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
Extract the topside control panel details. Hot Spring features the \
IQ 2020 touchscreen with Bluetooth and WiFi connectivity. Look for \
control panel type, features, smart home integration, and app control \
capabilities.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "type": <string or null>,
  "features": [<string>, ...],
  "smart_connectivity": <string or null>
}}""",
    "jets": """\
Extract the total jet count and per-type breakdown for this specific \
model. Hot Spring has multiple named jet types: Moto-Massage DX, \
SmartJet, HydroStream, HighFlow, Rotary Hydromassage, Directional \
Hydromassage, Directional Precision, and Mini jets. Extract the \
quantity of each jet type and the zone/seat where they are located. \
Hot Spring has the most detailed jet breakdown of the 3 manufacturers.

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
Extract headrest/pillow information for this model. Hot Spring uses \
"Comfort Pillow" as the brand name. Look for quantity and type.

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
Extract filter specifications. Hot Spring uses the Tri-X filter with \
a no-bypass design. Look for filtration area (in square feet), filter \
quantity, part numbers, and the no-bypass feature. The master spec \
table on page 45 lists effective filter area per model.

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "filters": [
    {{
      "system_name": <string or null>,
      "filter_type": <string or null>,
      "filtration_area_sqft": <float or null>,
      "quantity": <int or null>,
      "description": <string or null>,
      "no_bypass": <boolean or null>
    }}
  ]
}}""",
    "heater": """\
Extract heater specifications. Hot Spring uses the No-Fault heater \
system. The master spec table on page 45 has heater wattage per model. \
Some models have dual wattage options (e.g., 1500/6000W).

OUTPUT FORMAT:
The "data" field must contain a JSON object with this structure:
{{
  "model_name": <string or null>,
  "wattage": <int or null>,
  "voltage": <int>,
  "material": <string or null>
}}""",
    "lighting": """\
Extract lighting information. Hot Spring features multi-zone LED \
lighting with water feature lighting. Look for interior lights, \
exterior lights, water features, and any color options.

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
Extract spa cover specifications. The master spec table on page 45 \
lists footprint dimensions which determine cover size. Look for any \
explicit cover dimensions, thickness, material, or features.

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


class HotSpringHighlifeTemplate(ManufacturerTemplate):
    """Extraction template for Hot Spring Highlife Collection spas.

    Covers 8 models: Grandee, Envoy, Aria, Vanguard, Sovereign, Prodigy,
    Jetsetter LX, Jetsetter.
    PDF: highlife-2026.pdf (46 pages, 4.2 MB).

    Key terminology:
      - Pumps: Wavemaster 9000/9200 series
      - Circulation: SilentFlo 5000
      - Control: IQ 2020, FreshWater salt system
      - Jets: Moto-Massage DX, SmartJet, HydroStream, HighFlow,
              Rotary Hydromassage, Directional Hydromassage/Precision
      - Filter: Tri-X (no-bypass design)
      - Heater: No-Fault
      - Spec table: Page 45 (master comparison for all 8 models)
    """

    @property
    def manufacturer_name(self) -> str:
        return "hotspring"

    @property
    def series_name(self) -> str:
        return "Highlife Collection"

    @property
    def models(self) -> list[str]:
        return [
            "Grandee",
            "Envoy",
            "Aria",
            "Vanguard",
            "Sovereign",
            "Prodigy",
            "Jetsetter LX",
            "Jetsetter",
        ]

    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        """Build a full extraction prompt for a Hot Spring model and category."""
        page_hints = self.get_page_hints(spec_category)
        category_instructions = _CATEGORY_PROMPTS.get(spec_category, "")

        # Inject general fields prompt into jet_pumps category
        if spec_category == "jet_pumps":
            category_instructions = category_instructions.format(
                general_fields=_GENERAL_FIELDS_PROMPT,
            )

        prompt = (
            f"Extract the {spec_category.replace('_', ' ')} specifications "
            f"for the Hot Spring {model_name} ({self.series_name}, 2026) "
            f"from this owner's manual.\n\n"
            f"{_RULES}\n\n"
            f"{page_hints}\n\n"
            f"{category_instructions}"
        )
        return prompt

    def get_page_hints(self, spec_category: str) -> str:
        """Return page location hints for the given category."""
        return _PAGE_HINTS.get(spec_category, "")
