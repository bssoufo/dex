---
phase: 02-pdf-extraction-pipeline
plan: 02
subsystem: etl
tags: [anthropic, claude-api, structured-outputs, pydantic, extraction, validation, provenance, json-output]

requires:
  - phase: 01-data-schema-design/01-01
    provides: "SpaModel and 10 category Pydantic models for schema mapping"
  - phase: 01-data-schema-design/01-02
    provides: "SourceReference and DimensionsSpec models for provenance and dimensions"
  - phase: 02-pdf-extraction-pipeline/02-01
    provides: "ETL skeleton with config.py, ManufacturerTemplate ABC, anthropic SDK"
provides:
  - "Claude PDF API extraction wrapper with structured outputs and prompt caching"
  - "CategoryExtraction model for typed extraction results with provenance metadata"
  - "Schema mapper converting raw extraction dicts to validated SpaModel instances"
  - "Post-extraction sanity validators (range, confidence, completeness, duplicate checks)"
  - "JSON output writer with manufacturer/series directory structure"
  - "SourceReference provenance builder with page/section deduplication"
affects: [02-03-manufacturer-templates, 02-04-extraction-run, 03-web-scraping]

tech-stack:
  added: []
  patterns:
    - "Claude PDF API with base64 document blocks and cache_control for cost efficiency"
    - "Structured outputs via output_config.format.json_schema with transform_schema()"
    - "raw_data_json as JSON string to avoid additionalProperties:false constraint on dict fields"
    - "Non-blocking validation warnings pattern for extraction QA"

key-files:
  created:
    - backend/src/etl/extract/claude_extractor.py
    - backend/src/etl/transform/schema_mapper.py
    - backend/src/etl/transform/validators.py
    - backend/src/etl/output/writer.py
    - backend/src/etl/output/provenance.py
  modified: []

key-decisions:
  - "raw_data_json as JSON string instead of dict: Anthropic SDK transform_schema sets additionalProperties:false on dict types, preventing Claude from returning arbitrary key/value pairs. Using a JSON string field and parsing via property accessor avoids this constraint."
  - "Non-blocking validation: Sanity checks return warning strings rather than raising exceptions, so the pipeline logs issues but continues extracting remaining categories."
  - "Series slug for output paths: _slugify() converts series names to filesystem-safe slugs (e.g. '880 Series' -> '880-series') for consistent directory structure."

patterns-established:
  - "CategoryExtraction as extraction result type: all extraction functions return this model, all downstream consumers accept it"
  - "JSON string for variable-schema structured outputs: use str field + JSON parsing when Claude needs to return arbitrary structures"
  - "Provenance deduplication by (page_number, section) tuple"
  - "RAW.json debug output for failed SpaModel validations"

duration: 23min
completed: 2026-02-15
---

# Phase 2 Plan 2: Extraction Engine Summary

**Claude PDF extraction engine with structured outputs, schema mapper to SpaModel, sanity validators, JSON writer with manufacturer/series directory structure, and SourceReference provenance builder**

## Performance

- **Duration:** 23 min
- **Started:** 2026-02-15T17:44:57Z
- **Completed:** 2026-02-15T18:08:06Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- Built Claude PDF API wrapper that sends PDFs as base64 document blocks with ephemeral cache_control (90% cost discount on subsequent calls to same PDF) and structured outputs via output_config json_schema
- Created CategoryExtraction model with raw_data_json (JSON string) to work around Anthropic SDK's additionalProperties:false constraint on dict types -- data is parsed lazily via property accessor
- Implemented schema mapper that assembles per-category extractions into validated SpaModel instances with cross-category field lookup for seating_capacity and electrical data
- Built post-extraction validators checking HP ranges (0.5-10), jet counts (5-200), dimensions (40-150in), wattage (1000-6000), confidence levels, completeness, and cross-category duplicate detection
- Created JSON output writer with manufacturer/series slug directory structure and RAW.json debug output for failed validations
- Built provenance builder creating deduplicated SourceReference instances from extraction page numbers and section titles

## Task Commits

Each task was committed atomically:

1. **Task 1: Build Claude PDF extractor with structured outputs** - `b569ea7` (feat)
2. **Task 2: Build schema mapper, validators, writer, and provenance** - `e8ff339` (feat)

## Files Created/Modified
- `backend/src/etl/extract/claude_extractor.py` - Claude PDF API wrapper with CategoryExtraction model, extract_spec_category(), extract_model_specs()
- `backend/src/etl/transform/schema_mapper.py` - map_to_spa_model() assembling category extractions into validated SpaModel
- `backend/src/etl/transform/validators.py` - validate_extraction() returning non-blocking warning strings for range/confidence/completeness/duplicate checks
- `backend/src/etl/output/writer.py` - write_model_json() and write_raw_json() with slugified directory paths
- `backend/src/etl/output/provenance.py` - build_source_reference() and build_all_source_refs() with (page, section) deduplication

## Decisions Made
- **raw_data_json as JSON string:** The Anthropic SDK's `transform_schema()` sets `additionalProperties: false` on dict-typed fields, which would constrain Claude's structured output to an empty object. Using a `str` field containing JSON and parsing it via a `@property` accessor preserves the ability to extract arbitrary spec data while keeping structured output compliance.
- **Non-blocking validation pattern:** Validators return warning strings rather than raising exceptions. The pipeline logs issues but continues -- sanity checks are advisory, not gatekeepers. This prevents a single implausible value from blocking extraction of all remaining data.
- **Slugified directory structure:** Output paths use `_slugify()` to convert series names to filesystem-safe slugs (e.g. "880 Series" -> "880-series"), matching the Phase 1 pilot data layout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed CategoryExtraction.data from dict to raw_data_json (JSON string)**
- **Found during:** Task 1 (Claude PDF extractor)
- **Issue:** Plan specified `data: dict` field on CategoryExtraction. However, Anthropic SDK's `transform_schema()` sets `additionalProperties: false` on all object types, which would constrain Claude's structured output to an empty `{}` for the data field -- making extraction useless.
- **Fix:** Changed to `raw_data_json: str` (JSON string) with a `@property data` accessor that parses it. Added a `field_validator` that also accepts plain dicts (for test convenience) by serializing them to JSON.
- **Files modified:** backend/src/etl/extract/claude_extractor.py
- **Verification:** Tested both JSON string input and dict input -- both produce correct `.data` property output
- **Committed in:** b569ea7 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correct API interaction. The plan's `dict` approach would have produced empty extraction results. No scope creep.

## Issues Encountered
None -- plan executed cleanly after the data field fix.

## User Setup Required
None - no external service configuration required. The extraction engine uses the anthropic SDK which requires `ANTHROPIC_API_KEY` environment variable at runtime (already documented in Phase 2 research).

## Next Phase Readiness
- Extraction engine is complete and ready for manufacturer-specific templates (Plan 02-03)
- Templates only need to provide extraction prompts and page hints -- all API interaction, schema mapping, validation, and file output is handled by these 5 modules
- The CategoryExtraction -> validators -> schema_mapper -> writer pipeline is tested and functional
- Key pattern for template authors: extraction prompts should instruct Claude to return data matching the target Pydantic model field names for each category

---
*Phase: 02-pdf-extraction-pipeline*
*Completed: 2026-02-15*
