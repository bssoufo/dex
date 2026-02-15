---
phase: 02-pdf-extraction-pipeline
plan: 03
subsystem: etl
tags: [extraction-templates, manufacturer-prompts, pipeline-orchestrator, claude-api, prompt-engineering]

# Dependency graph
requires:
  - phase: 02-pdf-extraction-pipeline (02-01)
    provides: "ManufacturerTemplate ABC, PDF analysis report with page hints, ETL config"
  - phase: 02-pdf-extraction-pipeline (02-02)
    provides: "Claude extractor, schema mapper, validators, writer, provenance modules"
provides:
  - "Three manufacturer extraction templates (Sundance, Hot Spring, Bullfrog) with per-category prompts"
  - "Pipeline orchestrator (run_model, run_manufacturer, run_extraction) as single entry point"
  - "Template registry mapping manufacturer keys to template instances"
affects: [02-04-run-extraction, 03-web-scraping]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Template registry pattern: TEMPLATES dict maps manufacturer keys to instantiated template objects"
    - "Prompt engineering pattern: shared RULES + page hints + category-specific instructions + output schema"
    - "General fields piggybacked on jet_pumps prompt to avoid extra API calls"

key-files:
  created:
    - backend/src/etl/templates/sundance.py
    - backend/src/etl/templates/hotspring.py
    - backend/src/etl/templates/bullfrog.py
    - backend/src/etl/pipeline.py
  modified: []

key-decisions:
  - "General fields (seating, dimensions, voltage, amperage) extracted in jet_pumps prompt to avoid an extra API call per model"
  - "Bullfrog jet prompt uses modular_jetpak system type with bay count instead of individual jet types"
  - "Each prompt includes explicit OUTPUT FORMAT with JSON structure matching Pydantic model fields"

patterns-established:
  - "Template registry: TEMPLATES dict for manufacturer-to-template lookup"
  - "Extraction prompt structure: header + RULES + page_hints + category_instructions + OUTPUT FORMAT"
  - "Pipeline entry points: run_model (single) -> run_manufacturer (series) -> run_extraction (all)"

# Metrics
duration: 18min
completed: 2026-02-15
---

# Phase 2 Plan 3: Manufacturer Templates and Pipeline Orchestrator Summary

**Three manufacturer-specific extraction templates with 10 category prompts each, plus pipeline orchestrator wiring extract->validate->map->write flow**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-15T13:32:15Z
- **Completed:** 2026-02-15T13:50:47Z
- **Tasks:** 2
- **Files created:** 4

## Accomplishments
- Sundance880Template with Fluidix/SmartTub/MicroClean Ultra vocabulary and page hints targeting 92-page manual structure
- HotSpringHighlifeTemplate with Wavemaster/SilentFlo/IQ 2020/Tri-X/Moto-Massage DX vocabulary and page 45 master spec table reference
- BullfrogMSeriesTemplate with fundamentally different JetPak modular jet extraction (bay count, not individual jet types)
- Pipeline orchestrator with run_model/run_manufacturer/run_extraction entry points and CLI support

## Task Commits

Each task was committed atomically:

1. **Task 1: Create per-manufacturer extraction templates** - `f1d59fe` (feat)
2. **Task 2: Build pipeline orchestrator** - `2f761c0` (feat)

## Files Created/Modified
- `backend/src/etl/templates/sundance.py` - Sundance 880 Series template (7 models, Fluidix/SmartTub terminology)
- `backend/src/etl/templates/hotspring.py` - Hot Spring Highlife Collection template (8 models, Wavemaster/Tri-X terminology)
- `backend/src/etl/templates/bullfrog.py` - Bullfrog M Series template (4 models, JetPak modular system)
- `backend/src/etl/pipeline.py` - Pipeline orchestrator with template registry and CLI entry point

## Decisions Made
- [02-03]: General fields (seating_capacity, dimensions, voltage, amperage) piggybacked on the jet_pumps extraction prompt to avoid an extra API call per model
- [02-03]: Bullfrog jet extraction uses modular_jetpak system type targeting bay count and options rather than individual jet type enumeration
- [02-03]: Each extraction prompt includes explicit OUTPUT FORMAT section with JSON structure matching target Pydantic model fields to guide structured output
- [02-03]: Bullfrog prompts specify 2025 year (not 2026) since 2025 manual is being used due to 2026 not yet published

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full extraction pipeline is wired and ready to execute against real PDFs (Plan 02-04)
- All 19 models (7 Sundance + 8 Hot Spring + 4 Bullfrog) have templates and prompts
- Pipeline can be invoked via CLI: `uv run python -m src.etl.pipeline [manufacturer] [model]`
- Actual extraction requires ANTHROPIC_API_KEY environment variable and PDF files in pdf_store/

---
*Phase: 02-pdf-extraction-pipeline*
*Completed: 2026-02-15*
