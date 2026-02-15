---
phase: 01-data-schema-design
plan: 01
subsystem: database
tags: [pydantic, schema, json-schema, python, enums, data-modeling]

requires:
  - phase: none
    provides: "First phase, no dependencies"
provides:
  - "Pydantic v2 schema package at backend/src/schema/"
  - "SpaModel top-level model with 10 nested category models"
  - "PartReference with supersession chain fields"
  - "SourceReference for data provenance tracking"
  - "Manufacturer, PumpSpeed, JetSystemType enums"
  - "JSON Schema export via SpaModel.model_json_schema()"
affects: [02-pdf-extraction, 03-web-scraping, 04-data-verification, 05-mcp-data-access, 01-02 pilot data]

tech-stack:
  added: [pydantic 2.12.5]
  patterns: ["Nested category models with container/item pairs", "list[T] for variable-count components", "T | None = None for optional fields", "StrEnum for finite value sets", "shared_with_series boolean on every category"]

key-files:
  created:
    - backend/src/schema/__init__.py
    - backend/src/schema/enums.py
    - backend/src/schema/parts.py
    - backend/src/schema/models.py
    - backend/src/__init__.py
    - backend/pyproject.toml
  modified: []

key-decisions:
  - "Used StrEnum (not Literal) for Manufacturer, PumpSpeed, JetSystemType -- shared across multiple fields"
  - "PartReference as Pydantic BaseModel (not plain str) to capture supersession and cross-model compatibility"
  - "list[T] with min_length/max_length for variable-count components (pumps, jets, filters) instead of hardcoded fields"
  - "Every category model carries shared_with_series boolean for series-level data annotation"
  - "JetSpecs unified model handles both fixed jets and Bullfrog modular JetPak via jet_system_type enum"

patterns-established:
  - "T | None = None for all optional fields (Pydantic v2 pattern, never Optional[T])"
  - "from __future__ import annotations at top of every schema file"
  - "Field(description=...) on key fields for JSON Schema documentation"
  - "Container model (e.g. JetPumpSpecs) wrapping list of item models (e.g. JetPumpSpec)"

duration: 14min
completed: 2026-02-15
---

# Phase 1 Plan 1: Pydantic Schema Definition Summary

**Pydantic v2 schema with 10 nested category models, PartReference supersession tracking, 3 StrEnums, and SpaModel producing 21-property JSON Schema**

## Performance

- **Duration:** 14 min
- **Started:** 2026-02-15T08:48:24Z
- **Completed:** 2026-02-15T09:02:36Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments
- Complete Pydantic v2 schema package at `backend/src/schema/` with public API
- All 10 spec categories modeled as distinct Pydantic models with correct field types
- PartReference captures supersession chains (supersedes, superseded_by) and cross-model compatibility (fits_models, fits_years)
- Variable-count components (pumps, jets, filters, headrests, lights) use `list[T]` pattern
- JetSpecs accommodates both fixed-jet (Sundance/Hot Spring) and modular JetPak (Bullfrog) architectures
- SpaModel.model_json_schema() produces valid JSON Schema with 21 properties including all 10 categories

## Task Commits

Each task was committed atomically:

1. **Task 1: Create project structure, enums, and shared models** - `88c82c2` (feat)
2. **Task 2: Create 10 category models and top-level SpaModel** - `023f1e2` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Project config with pydantic 2.12.5 dependency
- `backend/src/__init__.py` - Empty package init
- `backend/src/schema/__init__.py` - Public API re-exports for all schema types
- `backend/src/schema/enums.py` - Manufacturer, PumpSpeed, JetSystemType StrEnum classes
- `backend/src/schema/parts.py` - PartReference, SourceReference, DimensionsSpec shared models
- `backend/src/schema/models.py` - 10 category models + SpaModel top-level model

## Decisions Made
- Used StrEnum (not Literal) for Manufacturer, PumpSpeed, JetSystemType because values are shared across multiple fields and models
- PartReference as Pydantic BaseModel (not plain str) to capture supersession and cross-model compatibility context
- list[T] with min_length/max_length for variable-count components (pumps 1-4, jets by type, filters) instead of hardcoded pump_1/pump_2 fields
- Every category model carries shared_with_series boolean for series-level data annotation
- JetSpecs unified model handles both fixed jets and Bullfrog modular JetPak via jet_system_type enum discriminator
- ConfigDict with json_schema_extra on SpaModel for JSON Schema description metadata

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Schema package is ready for Plan 01-02 (pilot data files + JSON Schema export + validation round-trip)
- All imports work, JSON Schema generation confirmed
- No blockers for next plan

---
*Phase: 01-data-schema-design*
*Completed: 2026-02-15*
