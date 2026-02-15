---
phase: 01-data-schema-design
plan: 02
subsystem: database
tags: [pydantic, json-schema, pilot-data, validation, jsonschema, data-modeling]

requires:
  - phase: 01-data-schema-design/01-01
    provides: "Pydantic v2 schema package with SpaModel, 10 category models, enums, PartReference"
provides:
  - "Three pilot JSON data files (Sundance Aspen, Hot Spring Grandee, Bullfrog M9)"
  - "JSON Schema export utility at backend/src/schema/export.py"
  - "Exported JSON Schema at backend/src/schemas/spa-model.schema.json"
  - "Proof that schema handles real-world complexity: multi-pump, multi-jet-type, modular vs fixed, supersession, series sharing"
affects: [02-pdf-extraction, 03-web-scraping, 04-data-verification, 05-mcp-data-access]

tech-stack:
  added: [jsonschema 4.26.0 (dev)]
  patterns: ["JSON data files as SpaModel instances", "export_json_schema() for Pydantic-to-JSON-Schema conversion", "jsonschema.validate() for external validation"]

key-files:
  created:
    - backend/src/data/sundance/880-series/aspen-2026.json
    - backend/src/data/hotspring/highlife/grandee-2026.json
    - backend/src/data/bullfrog/m-series/m9-2026.json
    - backend/src/schema/export.py
    - backend/src/schemas/spa-model.schema.json
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "Bullfrog M9 per-pump HP set to 4.8 (14.40 total / 3 pumps) since individual HP not listed by manufacturer"
  - "Grandee jet type quantities sum to 47 (not 49) per research data -- 2 unaccounted jets noted in research"
  - "JSON Schema exported in serialization mode for accurate representation of output format"

patterns-established:
  - "Data files stored at backend/src/data/{manufacturer}/{series}/{model}-{year}.json"
  - "JSON Schema exported via python -m src.schema.export"
  - "Dual validation: Pydantic model_validate() for Python, jsonschema.validate() for external"

duration: 17min
completed: 2026-02-15
---

# Phase 1 Plan 2: Pilot Data Files and JSON Schema Export Summary

**Three pilot JSON files (Aspen/Grandee/M9) validated against Pydantic schema and exported JSON Schema, proving the schema handles multi-pump, modular JetPak, supersession chains, and 7 jet type breakdowns**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-15T14:33:58Z
- **Completed:** 2026-02-15T14:50:31Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- Three pilot data files populated with real manufacturer specs, each loading into SpaModel without validation errors
- Sundance Aspen demonstrates 2 pumps, 66 Fluidix jets, heater supersession chain (6500-310 supersedes 6500-301), series-shared specs
- Hot Spring Grandee demonstrates named pump models (Wavemaster 9000/9200), 7 distinct jet types with per-type quantities and part numbers, Tri-X filter with part number
- Bullfrog M9 demonstrates 3 therapy pumps, modular JetPak system (6 slots, 16 options, 323 max jets), 14.40 total BHP
- JSON Schema export utility generates valid schema with 21 properties and 21 definitions
- All pilot files pass both Pydantic validation and external jsonschema validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create three pilot model JSON data files** - `8d45577` (feat)
2. **Task 2: Create JSON Schema export utility and export schema** - `eec66e6` (feat)

## Files Created/Modified
- `backend/src/data/sundance/880-series/aspen-2026.json` - Sundance Aspen pilot data (2 pumps, 66 jets, heater supersession)
- `backend/src/data/hotspring/highlife/grandee-2026.json` - Hot Spring Grandee pilot data (7 jet types, Wavemaster pumps, IQ 2020)
- `backend/src/data/bullfrog/m-series/m9-2026.json` - Bullfrog M9 pilot data (modular JetPak, 3 pumps, 14.40 BHP)
- `backend/src/schema/export.py` - JSON Schema export utility with export_json_schema() function
- `backend/src/schemas/spa-model.schema.json` - Exported JSON Schema (21 properties, 21 definitions)
- `backend/pyproject.toml` - Added jsonschema dev dependency
- `backend/uv.lock` - Updated lockfile

## Decisions Made
- Bullfrog M9 per-pump HP set to 4.8 each (14.40 total / 3 pumps) since Bullfrog only lists total BHP, not individual pump ratings
- Grandee jet type quantities sum to 47 (2+2+2+3+2+10+26) rather than 49 total -- research notes 2 unaccounted jets, likely uncategorized
- Used Pydantic serialization mode for JSON Schema export (`model_json_schema(mode="serialization")`) to accurately reflect output format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 (Data Schema Design) is fully complete
- Schema package, pilot data, and JSON Schema export are all in place
- Phase 2 (PDF Extraction) and Phase 3 (Web Scraping) can proceed -- both depend only on Phase 1 schema
- All 3 pilot files serve as reference examples for ETL output format

---
*Phase: 01-data-schema-design*
*Completed: 2026-02-15*
