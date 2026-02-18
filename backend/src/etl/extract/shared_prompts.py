"""Centralized extraction prompts shared by Gemini and OpenAI extractors.

Both LLMs receive identical prompts to prevent drift. The schema template
and strict rules are defined once here and imported by both extractors.
"""

from __future__ import annotations

# Full extraction prompt with enhanced counting rules and category guidance
EXTRACTION_PROMPT = """\
You are a technical data extraction specialist. Extract structured spa \
specification data from this manufacturer web page text.

MODEL: {model_name}
MANUFACTURER: {manufacturer}
SERIES: {series}
YEAR: {year}

Extract ALL of the following spec categories from the page content below. \
Return ONLY data explicitly stated on the page. If a value is not present, \
use null. NEVER guess or infer values.

Return a single JSON object with these top-level keys:

{{
  "seating_capacity": <int or null>,
  "voltage": <int or null>,
  "amperage": <int or null>,
  "dimensions": {{
    "length_inches": <float or null>,
    "width_inches": <float or null>,
    "height_inches": <float or null>,
    "dry_weight_lbs": <float or null>,
    "filled_weight_lbs": <float or null>,
    "water_capacity_gallons": <float or null>
  }},
  "jet_pumps": {{
    "pumps": [
      {{
        "position": <int>,
        "model_name": <string or null>,
        "horsepower_continuous": <float or null>,
        "horsepower_breakdown": <float or null>,
        "speed": <"1-speed" or "2-speed" or null>,
        "amperage_max": <float or null>,
        "frame": <string or null>,
        "voltage": <int or null>,
        "part_number": null
      }}
    ],
    "diverter_valves": <int or null>,
    "total_brake_horsepower": <float or null>,
    "shared_with_series": false
  }},
  "circulation_pump": {{
    "model_name": <string or null>,
    "description": <string or null>,
    "is_dedicated": <bool or null>,
    "wattage": <int or null>,
    "part_number": null,
    "shared_with_series": false
  }},
  "spa_pak": {{
    "model_name": <string or null>,
    "display_type": <string or null>,
    "voltage": <int or null>,
    "amperage": <int or null>,
    "frequency_hz": <int or null>,
    "features": [<strings>],
    "part_number": null,
    "shared_with_series": false
  }},
  "topside_control": {{
    "model_name": <string or null>,
    "type": <string or null>,
    "features": [<strings>],
    "smart_connectivity": <string or null>,
    "part_number": null,
    "shared_with_series": false
  }},
  "jets": {{
    "total_jet_count": <int or null>,
    "jet_system_type": <"fixed" or "modular_jetpak" or null>,
    "jets_by_type": [
      {{
        "jet_type": <string>,
        "quantity": <int>,
        "zone": <string or null>,
        "part_number": null,
        "description": null
      }}
    ],
    "jetpak_count": <int or null>,
    "jetpak_options": [<strings>] or null,
    "shared_with_series": false
  }},
  "headrests": {{
    "headrests": [
      {{
        "type": <string>,
        "quantity": <int or null>,
        "part_number": null,
        "description": <string or null>
      }}
    ],
    "shared_with_series": false
  }},
  "filters": {{
    "filters": [
      {{
        "system_name": <string or null>,
        "filter_type": <string or null>,
        "filtration_area_sqft": <float or null>,
        "quantity": <int or null>,
        "description": <string or null>,
        "no_bypass": <bool or null>,
        "part_number": null
      }}
    ],
    "shared_with_series": false
  }},
  "heater": {{
    "model_name": <string or null>,
    "wattage": <int or null>,
    "voltage": <int or null>,
    "material": null,
    "part_number": null,
    "shared_with_series": false
  }},
  "lighting": {{
    "lights": [
      {{
        "location": <string>,
        "type": <string or null>,
        "description": <string or null>,
        "part_number": null
      }}
    ],
    "water_feature": <string or null>,
    "shared_with_series": false
  }},
  "cover": {{
    "model_name": <string or null>,
    "thickness": <string or null>,
    "material": <string or null>,
    "features": [<strings>],
    "length_inches": <float or null>,
    "width_inches": <float or null>,
    "part_number": null,
    "shared_with_series": false
  }}
}}

STRICT RULES:
- The sum of all jets_by_type quantities MUST equal total_jet_count exactly. \
Count carefully before responding.
- For entries like "1 - Moto-Massage DX (2)", the leading number is the count \
of that jet type, and "(2)" is the number of actual jet nozzles per unit. \
The quantity = leading number * nozzles, e.g. 1 * 2 = 2.
- Use null rather than guessing — never invent numbers.
- List ALL jet types shown on the page, do not merge or skip any.
- Convert ALL dimensions to inches (e.g., 7'3" = 87 inches, 2.21m = 87 inches).
- For HP values, extract the EXACT number stated (e.g., "2.5 HP continuous" -> 2.5).
- For Bullfrog models with total BHP, divide by pump count for per-pump HP.
- If the page lists jet types with quantities, include ALL of them.
- Part numbers are NOT expected on manufacturer websites — always null.
- Return VALID JSON only — no markdown, no code fences, no explanation.

CATEGORY GUIDANCE:
- JET PUMP: pump count, HP, speed, frame, amperage. Each physical pump = one entry.
- CIRC PUMP: wattage, dedicated vs shared.
- SPA PAK: model name, voltage, amperage.
- TOPSIDE: type, features, WiFi/app connectivity.
- JETS: every jet type with quantity and part number if shown.
- HEADRESTS: type name, quantity, part number if shown.
- FILTER CARTRIDGE: sq ft area, cartridge count.
- HEATER: wattage (or kW * 1000).
- LIGHT BULB: LED type, interior vs exterior, color-changing.
- COVER DIMENSIONS: length, width (may match spa dims).

PAGE CONTENT:
{page_text}
"""

# Review prompt: OpenAI reviews Gemini's extraction against the page text
REVIEW_PROMPT = """\
You are a technical data verification specialist. A previous AI extracted \
structured spa specification data from a manufacturer web page. Your job is \
to REVIEW the extraction against the original page text and return a \
CORRECTED version of the JSON.

MODEL: {model_name}
MANUFACTURER: {manufacturer}
SERIES: {series}
YEAR: {year}

PREVIOUS EXTRACTION (to verify):
{gemini_json}

INSTRUCTIONS:
1. Compare EVERY field in the extraction above against the page text below.
2. If a field is correct, keep it as-is.
3. If a field is wrong, replace it with the correct value from the page.
4. If a field is null but the page has the data, fill it in.
5. If a field has a value but the page does NOT support it, set it to null.
6. Return the COMPLETE JSON structure with all corrections applied.

STRICT RULES:
- The sum of all jets_by_type quantities MUST equal total_jet_count exactly. \
Count carefully before responding.
- For entries like "1 - Moto-Massage DX (2)", the leading number is the count \
of that jet type, and "(2)" is the number of actual jet nozzles per unit. \
The quantity = leading number * nozzles, e.g. 1 * 2 = 2.
- Use null rather than guessing — never invent numbers.
- List ALL jet types shown on the page, do not merge or skip any.
- Convert ALL dimensions to inches (e.g., 7'3" = 87 inches, 2.21m = 87 inches).
- For HP values, extract the EXACT number stated (e.g., "2.5 HP continuous" -> 2.5).
- Part numbers are NOT expected on manufacturer websites — always null.
- Return VALID JSON only — no markdown, no code fences, no explanation.

PAGE CONTENT:
{page_text}
"""

# Targeted re-extraction prompt for specific categories with error context
REEXTRACT_PROMPT = """\
You are a technical data extraction specialist. A previous extraction of \
this spa model had validation errors. Re-extract ONLY the specified \
categories, paying careful attention to the errors described.

MODEL: {model_name}
MANUFACTURER: {manufacturer}
SERIES: {series}
YEAR: {year}

PREVIOUS ERRORS:
{error_context}

Re-extract ONLY these categories: {categories}

STRICT RULES:
- The sum of all jets_by_type quantities MUST equal total_jet_count exactly.
- For entries like "1 - Moto-Massage DX (2)", the leading number is the count \
of that type, "(2)" is nozzles per unit. Quantity = count * nozzles.
- Use null rather than guessing — never invent numbers.
- List ALL jet types shown on the page, do not merge or skip any.
- If total_jet_count seems unreasonably high (>100), recount from the page carefully.
- Convert ALL dimensions to inches.
- Return VALID JSON with only the requested category keys. No markdown or code fences.

CATEGORY GUIDANCE:
- JET PUMP: pump count, HP, speed, frame, amperage. Each physical pump = one entry.
- CIRC PUMP: wattage, dedicated vs shared.
- SPA PAK: model name, voltage, amperage.
- TOPSIDE: type, features, WiFi/app connectivity.
- JETS: every jet type with quantity and part number if shown.
- HEADRESTS: type name, quantity, part number if shown.
- FILTER CARTRIDGE: sq ft area, cartridge count.
- HEATER: wattage (or kW * 1000).
- LIGHT BULB: LED type, interior vs exterior, color-changing.
- COVER DIMENSIONS: length, width (may match spa dims).

PAGE CONTENT:
{page_text}
"""
