# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** 100% accurate retrieval of technical specifications and part numbers -- a wrong part is a failure.
**Current focus:** Phase 2 complete. All 19 models extracted from PDFs. Next: Phase 3 (Web Scraping Pipeline).

## Current Position

Phase: 2 of 10 (PDF Extraction Pipeline) -- COMPLETE
Plan: 4 of 4 in current phase
Status: Complete
Last activity: 2026-02-15 -- All 19 models extracted successfully

Progress: [██████░░░░░░░░░░░░░░] ~25%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 25 min
- Total execution time: 2.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 - Data Schema | 2/2 | 31 min | 15.5 min |
| 2 - PDF Extraction | 4/4 | 120 min | 30 min |

**Recent Trend:**
- Plan 02-04 required multiple iteration cycles to fix schema tolerance for Gemini extraction quirks

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Schema-first approach -- design JSON schema before any ETL work begins (validates against 3 pilot models)
- [Roadmap]: Single agent before multi-agent -- prove accuracy with monolithic agent, then split into Concierge/Specialist/Validator
- [Roadmap]: Phases 2+3 parallelizable -- PDF extraction and web scraping can run concurrently since both depend only on Phase 1 schema
- [01-01]: StrEnum for Manufacturer/PumpSpeed/JetSystemType -- values shared across multiple fields, not Literal types
- [01-01]: PartReference as Pydantic model (not plain str) -- captures supersession chains and cross-model compatibility
- [01-01]: list[T] for variable-count components -- handles 1-4 pumps, multiple jet types, etc.
- [01-01]: JetSpecs unified model with jet_system_type enum -- both fixed jets and Bullfrog JetPak in one schema
- [01-02]: Bullfrog M9 per-pump HP set to 4.8 (14.40/3) since manufacturer only lists total BHP
- [01-02]: JSON Schema exported in serialization mode for accurate output representation
- [01-02]: Dual validation pattern: Pydantic model_validate() for Python + jsonschema.validate() for external
- [02-01]: Bullfrog 2025 manual used since 2026 not yet published -- source references must note year mismatch
- [02-01]: PDF binaries gitignored to keep repo lightweight (~40 MB total)
- [02-01]: Extraction order: Hot Spring first (most structured), Sundance second (most data), Bullfrog third (depends on web scraping)
- [02-02]: raw_data_json as JSON string instead of dict -- Anthropic SDK transform_schema sets additionalProperties:false on dict types, preventing Claude from returning arbitrary key/value pairs
- [02-02]: Non-blocking validation pattern -- sanity checks return warnings, do not raise exceptions or block extraction
- [02-02]: Slugified directory structure for JSON output paths (e.g. "880 Series" -> "880-series")
- [02-03]: General fields piggybacked on jet_pumps prompt to avoid extra API call per model
- [02-03]: Bullfrog jet prompt uses modular_jetpak system type with bay count instead of individual jet types
- [02-03]: Each extraction prompt includes explicit OUTPUT FORMAT with JSON structure matching Pydantic model fields
- [02-03]: Bullfrog prompts specify 2025 year since 2025 manual is being used
- [02-04]: Switched from Claude to Gemini for PDF extraction per user request
- [02-04]: Schema fields must be nullable to tolerate Gemini returning null for any field
- [02-04]: Gemini returns string "null" instead of actual null -- mapper must clean this
- [02-04]: Multi-amp values like "20A & 30A" parsed to max integer in mapper
- [02-04]: Retry with exponential backoff (5s base, 4 retries) handles Gemini 429 rate limits

### Pending Todos

None.

### Blockers/Concerns

- [Research]: Three sequential LLM calls (Concierge + Specialist + Validator) may exceed 3-second response target. May need faster model for Validator or parallel execution. Address in Phase 7.
- [02-01]: Bullfrog 2026 manual not yet published. Using 2025 v1.1 -- specs likely carry forward but must verify when 2026 becomes available.
- [02-01]: Part numbers are sparse in all 3 owner's manuals. Phase 3 web scraping and Phase 4 manual entry will be critical for part number population.
- [02-01]: Cover dimensions missing from Sundance manual entirely. Must fill from Phase 3 web scraping.

## Session Continuity

Last session: 2026-02-15
Stopped at: Phase 2 complete. All 19 models extracted.
Resume file: None
