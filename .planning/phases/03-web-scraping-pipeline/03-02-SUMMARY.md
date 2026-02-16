---
phase: 03-web-scraping-pipeline
plan: 02
subsystem: etl
tags: [beautifulsoup4, lxml, web-scraping, html-parsing, sundance, hotspring, bullfrog]

# Dependency graph
requires:
  - phase: 03-web-scraping-pipeline
    provides: ScrapedSpecs dataclass, ManufacturerParser ABC, parsing utilities, PageFetcher, URL registry
  - phase: 01-data-schema
    provides: Pydantic SpaModel schema defining expected spec fields
provides:
  - SundanceParser extracting 11 spec fields from sundancespas.com product pages
  - HotSpringParser extracting 13 spec fields from hotspringhottubs.com dealer pages
  - BullfrogParser extracting 9 spec fields from bullfrogfactorystores.com dealer pages
affects: [03-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-manufacturer HTML DOM traversal, two-format jet count parsing, model name validation preventing wrong-model extraction]

key-files:
  created:
    - backend/src/etl/scrape/parsers/sundance.py
    - backend/src/etl/scrape/parsers/hotspring.py
    - backend/src/etl/scrape/parsers/bullfrog.py
  modified: []

key-decisions:
  - "Sundance seating from prose: extracted from description text patterns since not a structured field"
  - "Hot Spring jet count dual-format: Format A (standalone total) vs Format B (sum breakdown segments)"
  - "Bullfrog model validation returns empty ScrapedSpecs on mismatch instead of raising exception"
  - "Bullfrog span.label/span.value as primary data source, table rows as supplementary"

patterns-established:
  - "Each parser implements _extract_all_attributes() to build a label->value dict from site-specific DOM"
  - "Extraction logging: every parser logs which fields were extracted and which are missing"
  - "Graceful degradation: all fields default to None, parsers never raise on parseable HTML"

# Metrics
duration: 10min
completed: 2026-02-16
---

# Phase 3 Plan 02: Manufacturer Parsers Summary

**Three manufacturer-specific HTML parsers (Sundance, Hot Spring, Bullfrog) extracting dimensions, weights, capacity, jets, electrical, and filtration from live web pages into ScrapedSpecs**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-16T11:31:25Z
- **Completed:** 2026-02-16T11:41:19Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- SundanceParser extracts 11 fields from sundancespas.com: dimensions (L/W/H), weight, water capacity, jets, electrical (volts/amps), filtration area, diverter valves, seating (from prose text)
- HotSpringParser extracts 13 fields from hotspringhottubs.com: dimensions, dry+filled weights, water capacity, seating, jets (two count formats), pump count, filtration area, electrical, heater wattage
- BullfrogParser extracts 9 fields from bullfrogfactorystores.com: dimensions, dry+filled weights, water capacity, seating, jets, pump count; validates model name to prevent wrong-model extraction
- All parsers tested against 2+ live model pages with non-None results for key fields

## Task Commits

Each task was committed atomically:

1. **Task 1: Build Sundance 880 Series parser** - `c731b5d` (feat)
2. **Task 2: Build Hot Spring Highlife parser** - `8b3ab77` (feat)
3. **Task 3: Build Bullfrog M Series parser** - `9ca2b86` (feat)

## Files Created/Modified
- `backend/src/etl/scrape/parsers/sundance.py` - SundanceParser: parses li.attribute-values elements from expandable Specs/Dimensions sections
- `backend/src/etl/scrape/parsers/hotspring.py` - HotSpringParser: parses Divi two-column row layout with strong labels and paragraph values
- `backend/src/etl/scrape/parsers/bullfrog.py` - BullfrogParser: parses span.label/span.value pairs and supplementary spec table

## Decisions Made
- Sundance seating capacity is extracted from narrative description text (e.g. "Comfortably seating seven") since it is not a structured spec field -- uses word-to-number mapping with multiple regex patterns
- Hot Spring jet count parsing handles two formats across models: Format A where first number is a standalone total (Grandee: "43, 2 Moto-Massage...") and Format B where there is no total and individual counts must be summed (Envoy: "1 Moto-Massage DX jet, 2 SoothingStream jets, ...")
- Bullfrog model name validation returns an empty ScrapedSpecs instead of raising when the page shows a different model -- this prevents silently extracting wrong specs when dealer unit_ids change
- Bullfrog data extracted from span.label/span.value pairs as primary source (19 attributes) supplemented by table rows (30 attributes) for additional detail like seat breakdown and pump count

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hot Spring jet count returned 1 instead of 42 for Envoy**
- **Found during:** Task 2 (Hot Spring parser)
- **Issue:** Initial implementation assumed first number in jets text was always the total count. Envoy's jets field starts with "1 Moto-Massage DX jet" where 1 is a per-type count, not a total.
- **Fix:** Added dual-format detection: if text matches "N, N [Uppercase]" pattern it's Format A (standalone total), otherwise sum all leading numbers from comma-separated segments (Format B).
- **Files modified:** backend/src/etl/scrape/parsers/hotspring.py
- **Verification:** Grandee returns 43 (Format A), Envoy returns 42 (Format B: 1+2+3+2+3+10+2+19)
- **Committed in:** 8b3ab77 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix necessary for correct jet count across Hot Spring models. No scope creep.

## Issues Encountered
- Sundance seating capacity not available as structured spec field -- solved by regex extraction from description prose
- Hot Spring dimensions use unicode smart-quote entities for feet/inches marks -- handled by normalizing unicode before parsing

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All three manufacturer parsers complete and tested against live web pages
- Plan 03-03 can now build the merge pipeline and orchestrator to run all parsers, match results to existing JSON models, and merge scraped specs into the Pydantic SpaModel data files
- Parser coverage: Sundance 7 models, Hot Spring 8 models, Bullfrog 4 models = all 19 POC models

---
*Phase: 03-web-scraping-pipeline*
*Completed: 2026-02-16*
