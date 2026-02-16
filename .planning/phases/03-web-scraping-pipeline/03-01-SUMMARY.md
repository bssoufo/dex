---
phase: 03-web-scraping-pipeline
plan: 01
subsystem: etl
tags: [httpx, beautifulsoup4, lxml, tenacity, web-scraping, parsing]

# Dependency graph
requires:
  - phase: 01-data-schema
    provides: Pydantic SpaModel schema that scraped data will merge into
  - phase: 02-pdf-extraction-pipeline
    provides: ETL config with MANUFACTURERS dict and DATA_OUTPUT_DIR path
provides:
  - URL registry for all 19 spa models across 3 manufacturer sites
  - Rate-limited HTTP fetcher with retry and fallback URL support
  - ScrapedSpecs dataclass as intermediate format between HTML parsing and schema merge
  - ManufacturerParser abstract base class for manufacturer-specific parsers
  - Dimension, weight, and text parsing utilities for varied web formats
affects: [03-02-PLAN, 03-03-PLAN]

# Tech tracking
tech-stack:
  added: [httpx, beautifulsoup4, lxml, tenacity]
  patterns: [manufacturer-specific parser ABC, ScrapedSpecs intermediate dataclass, per-domain rate limiting]

key-files:
  created:
    - backend/src/etl/scrape/__init__.py
    - backend/src/etl/scrape/config.py
    - backend/src/etl/scrape/fetcher.py
    - backend/src/etl/scrape/parsers/__init__.py
    - backend/src/etl/scrape/parsers/base.py
    - backend/src/etl/scrape/parsers/utils.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "Synchronous httpx.Client (not async) -- only 19 pages total, async is overkill"
  - "ScrapedSpecs as plain dataclass not Pydantic -- intermediate format before schema merge"
  - "Per-domain rate limits in config dict with get_delay_for_url helper"
  - "Bullfrog crawl-delay set to 10s per robots.txt specification"
  - "validate_model_name logs warning but does not raise on mismatch"

patterns-established:
  - "ManufacturerParser ABC: each manufacturer implements parse_model_page(html, model_name) -> ScrapedSpecs"
  - "Parsing utilities always return None on failure (no exceptions for bad input)"
  - "URL registry with alt_url fallback for dealer sites with unstable URLs"

# Metrics
duration: 5min
completed: 2026-02-16
---

# Phase 3 Plan 01: Scrape Foundation Summary

**httpx/BeautifulSoup scrape module with 19-model URL registry, rate-limited fetcher, parser ABC, and dimension/weight parsing utilities**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-16T11:23:58Z
- **Completed:** 2026-02-16T11:28:33Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Installed httpx, beautifulsoup4, lxml, tenacity as scraping dependencies
- Created URL registry covering all 19 models across Sundance (7), Hot Spring (8), Bullfrog (4) with fallback URLs for Bullfrog dealer site
- Built PageFetcher with tenacity retry (3 attempts, exponential backoff) and context manager support
- Created ManufacturerParser ABC and ScrapedSpecs dataclass with 15 optional spec fields
- Implemented 6 parsing utilities handling diverse text formats (feet-inches, meters, cm, fractional, ranges, comma-separated numbers)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create scrape module skeleton** - `802c837` (feat)
2. **Task 2: Create dimension and weight parsing utilities** - `54266b8` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Added httpx, beautifulsoup4, lxml, tenacity dependencies
- `backend/uv.lock` - Updated lock file with new dependencies
- `backend/src/etl/scrape/__init__.py` - Scrape module package init
- `backend/src/etl/scrape/config.py` - URL registry (19 models), rate limits, get_delay_for_url helper
- `backend/src/etl/scrape/fetcher.py` - PageFetcher with retry, rate limiting, fallback URL support
- `backend/src/etl/scrape/parsers/__init__.py` - Parsers subpackage init
- `backend/src/etl/scrape/parsers/base.py` - ScrapedSpecs dataclass and ManufacturerParser ABC
- `backend/src/etl/scrape/parsers/utils.py` - parse_dimension_inches, parse_weight_lbs, parse_gallons, parse_int, parse_float, clean_text

## Decisions Made
- Used synchronous httpx.Client instead of async -- only 19 pages, async adds complexity for no benefit
- ScrapedSpecs is a plain dataclass, not Pydantic -- it is an intermediate format before merging into Pydantic SpaModel JSON files
- Per-domain rate limits stored in config dict with helper function -- Bullfrog at 10s per robots.txt, others at 2s
- validate_model_name warns on mismatch but does not raise -- prevents false positives from blocking extraction
- hotspas.com added as fallback for Bullfrog since dealer unit_ids may change

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Scrape module skeleton complete and importable
- Plan 03-02 can now implement the three manufacturer-specific parsers (sundance.py, hotspring.py, bullfrog.py) by extending ManufacturerParser
- Plan 03-03 can build the merge pipeline and orchestrator using the fetcher, config, and parser infrastructure
- All parsing utilities tested and ready for use in manufacturer parsers

---
*Phase: 03-web-scraping-pipeline*
*Completed: 2026-02-16*
