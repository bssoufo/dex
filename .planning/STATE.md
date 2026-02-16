# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** 100% accurate retrieval of technical specifications and part numbers -- a wrong part is a failure.
**Current focus:** Phase 7 complete. Multi-agent system fully tested with 313 total tests (295 unit + 18 integration). Next: Phase 8 (Response Quality) or Phase 9 (Frontend).

## Current Position

Phase: 7 of 10 (Multi-Agent Orchestration) -- COMPLETE
Plan: 3 of 3 in current phase (all complete)
Status: Phase complete
Last activity: 2026-02-16 -- Completed 07-03-PLAN.md

Progress: [██████████████████████░░░░░░░░░] ~70%

## Performance Metrics

**Velocity:**
- Total plans completed: 20
- Average duration: 13.5 min
- Total execution time: 4.50 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 - Data Schema | 2/2 | 31 min | 15.5 min |
| 2 - PDF Extraction | 4/4 | 120 min | 30 min |
| 3 - Web Scraping | 3/3 | 22 min | 7.3 min |
| 4 - Data Verification | 3/3 | 14 min | 4.7 min |
| 5 - MCP Data Access | 2/2 | 11 min | 5.5 min |
| 6 - Single Agent Core | 3/3 | 38 min | 12.7 min |
| 7 - Multi-Agent Orchestration | 3/3 | 30 min | 10 min |

**Recent Trend:**
- Plan 07-03 completed in 16 min -- integration test verification with real Gemini API (18/18 tests pass, 313 total)
- Plan 07-02 completed in 5 min -- conversation sessions + validator wiring into API (295 total tests)
- Plan 07-01 completed in 9 min -- langgraph-supervisor multi-agent with 62 unit tests (291 total)

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
- [03-01]: Synchronous httpx.Client (not async) -- only 19 pages total, async adds complexity for no benefit
- [03-01]: ScrapedSpecs as plain dataclass not Pydantic -- intermediate format before schema merge
- [03-01]: Per-domain rate limits in config dict -- Bullfrog 10s per robots.txt, others 2s
- [03-01]: validate_model_name logs warning but does not raise on mismatch
- [03-01]: hotspas.com added as Bullfrog fallback since dealer unit_ids may change
- [03-02]: Sundance seating extracted from prose description since not a structured spec field
- [03-02]: Hot Spring jet count dual-format: standalone total (Format A) vs summed breakdown (Format B)
- [03-02]: Bullfrog model validation returns empty ScrapedSpecs on mismatch instead of raising
- [03-02]: Bullfrog span.label/span.value as primary data source, table rows as supplementary
- [03-03]: Web data fills null/0 only, NEVER overwrites non-null PDF values -- PDF is authoritative
- [03-03]: Website SourceReference only appended when at least one field was updated
- [03-03]: Jetsetter LX 404 and M7 403 logged as failures, not blocking pipeline
- [03-03]: Pipeline idempotent: re-running skips already-filled fields without duplicating source refs
- [04-01]: DataQuality defaults to None on SpaModel so existing 19 JSON files without the field still pass Pydantic validation
- [04-01]: Plausible ranges defined inline in checks.py rather than importing from validators.py (different input types)
- [04-01]: Verification check function pattern: takes SpaModel, returns list[Anomaly]
- [04-02]: Actual completeness is 181/2/7 (OK/NULL/EMPTY) not 182/2/6 as estimated in research
- [04-02]: Not-available classification: 323 part_numbers, 133 universal nulls, 4 manufacturer-specific
- [04-02]: CLI is strictly read-only -- no data modification, Plan 03 handles fixes
- [04-03]: Voltage fix uses actual top-level value (230V) not plan's assumed 240V -- data-driven correction
- [04-03]: Jet count mismatches marked as accepted (not fixed) -- different counting methods are both valid
- [04-03]: seating_capacity=0 for M7 and Capris marked as accepted pending manual verification
- [04-03]: Checkpoint auto-approved per user directive for autonomous execution
- [05-01]: FastMCP 2.14.x (not v3 RC) per user MEMORY.md lock and stability
- [05-01]: Literal type for ModelName (not StrEnum) -- JSON Schema enum constraint for LLM agents
- [05-01]: Lazy-init singleton for data store -- loads on first access, not at import time
- [05-01]: Case-insensitive lookup internally while Literal type enforces canonical case at protocol level
- [05-01]: model_dump() without exclude_none to preserve null fields (shows what is missing)
- [05-01]: not_available_fields scoped per category by prefix matching on data_quality.not_available_fields
- [05-02]: testpaths = ["tests"] relative to backend/ rootdir in pyproject.toml
- [05-02]: parse_result() helper handles CallToolResult.content[0].text JSON parsing with future-proof fallbacks
- [06-01]: Gemini 2.5 Flash for agent LLM -- already has API key, sub-500ms TTFT, temperature=0 for deterministic
- [06-01]: sys.executable for MCP subprocess command -- works on both Windows and Linux
- [06-01]: MultiServerMCPClient creates new session per tool call -- no persistent connection management needed
- [06-01]: monkeypatch.setenv for GEMINI_API_KEY in unit tests -- avoids requiring real key for prompt/config tests
- [06-02]: httpx already in main deps from scraping phase -- no dev dep addition needed for TestClient
- [06-02]: QueryRequest min_length=1 to reject empty questions at API boundary
- [06-02]: Tool call info in QueryResponse truncated to 200 chars for debugging without flooding
- [06-03]: Filters test uses Cameo (not Marin) -- Marin has null filter data
- [06-03]: Heater test uses Sundance Altamar (not Bullfrog M8) -- all Bullfrog heater data is null
- [06-03]: Performance CI threshold 30s (not 3s) -- MCP subprocess startup + Gemini API latency
- [06-03]: Checkpoint auto-approved per user directive for autonomous execution
- [07-01]: Concierge gets list_models tool (not empty) to avoid Gemini empty schema errors
- [07-01]: Validator is pure Python function called by API layer, NOT a LangGraph node
- [07-01]: include_agent_name="inline" on create_supervisor for Gemini compatibility
- [07-01]: output_mode="last_message" on create_supervisor to keep history lean
- [07-01]: create_dex_agent kept as deprecated wrapper for backward compatibility
- [07-02]: validate_response imported lazily inside /query handler (not at module top level)
- [07-02]: Empty warnings list converted to None for cleaner JSON responses
- [07-03]: Multi-turn timeout 180s (vs 60s single-turn) -- 2 sequential supervisor invocations with MCP subprocess startup
- [07-03]: Performance threshold 45s (up from 30s) -- supervisor routing adds one extra LLM call
- [07-03]: pytest-rerunfailures for LLM non-determinism -- handles ~10-15% flaky runs gracefully
- [07-03]: Longest AI message heuristic for answer extraction -- supervisor handoff messages are shorter than data answers

### Pending Todos

None.

### Blockers/Concerns

- [07-03]: Multi-agent response time is 12-15s per query (supervisor routing + MCP subprocess + Gemini API). Persistent MCP connections would reduce by ~5s.
- [02-01]: Bullfrog 2026 manual not yet published. Using 2025 v1.1 -- specs likely carry forward but must verify when 2026 becomes available.
- [02-01]: Part numbers are sparse in all 3 owner's manuals. Phase 3 web scraping and Phase 4 manual entry will be critical for part number population.
- [03-Research]: Part numbers NOT available on manufacturer product pages. 274/274 still null. Must defer to Phase 4 manual entry or separate retailer-site scraping effort.
- [03-03]: Jetsetter LX page returns 404, M7 returns 403 Forbidden. These models retain PDF-only data. May need alternative URLs or manual entry in Phase 4.
- [04-03]: M7 seating_capacity=0 and Capris seating_capacity=0 remain as accepted anomalies -- correct values unknown from available sources.
- [04-03]: 460 not-available fields (323 part numbers, 133 universal nulls, 4 mfr-specific) -- MCP tools handle these via not_available_fields in responses.

## Session Continuity

Last session: 2026-02-16
Stopped at: Completed 07-03-PLAN.md. Phase 7 complete. Next: Phase 8 (Response Quality) or Phase 9 (Frontend).
Resume file: None
