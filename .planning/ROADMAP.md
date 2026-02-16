# Roadmap: Dex -- Technical Knowledge Assistant

## Overview

Dex delivers a zero-hallucination technical knowledge assistant for Spaparts staff. The roadmap follows data dependencies strictly: schema before extraction, extraction before tools, tools before agents, agents before UI. Comprehensive depth splits the work into 10 phases, each delivering a coherent, independently verifiable capability. The most critical insight from research is preserved: prove accuracy with a single agent before introducing multi-agent complexity.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Schema Design** - Define the canonical JSON schema for all 10 spec categories
- [x] **Phase 2: PDF Extraction Pipeline** - Build automated extraction from manufacturer PDF manuals
- [x] **Phase 3: Web Scraping Pipeline** - Build automated extraction from manufacturer websites
- [x] **Phase 4: Data Verification and Population** - Verify and populate all 190 data points with source tracking
- [ ] **Phase 5: MCP Data Access Layer** - Build deterministic query tools over verified data
- [ ] **Phase 6: Single Agent Core** - Prove query accuracy with one agent before multi-agent split
- [ ] **Phase 7: Multi-Agent Orchestration** - Split into Concierge/Specialist/Validator with conversation context
- [ ] **Phase 8: Response Quality** - Source attribution, cross-references, and polished output format
- [ ] **Phase 9: Frontend** - React chat interface with table rendering
- [ ] **Phase 10: Deployment and Hardening** - Hosted deployment for remote client testing

## Phase Details

### Phase 1: Data Schema Design
**Goal**: The canonical data structure exists that both ETL (writes to) and MCP tools (reads from) will use -- the keystone of the entire system
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. A Pydantic schema defines all 10 spec categories with strict field types (enums for known values, explicit nullable for optional fields)
  2. The schema models cross-reference relationships (which parts fit which models, supersession chains)
  3. Three pilot model files (one per manufacturer: Sundance Aspen, Hot Spring Grandee, Bullfrog M9) validate that the schema handles real-world data complexity (multi-pump positions, series-level shared specs)
  4. JSON Schema export from Pydantic produces valid schema files that can be used for validation
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Define Pydantic schema: enums, shared models (PartReference, SourceReference), 10 category models, SpaModel
- [x] 01-02-PLAN.md -- Create 3 pilot data files (Aspen, Grandee, M9), export JSON Schema, validate round-trip

### Phase 2: PDF Extraction Pipeline
**Goal**: Automated extraction of technical specs from manufacturer PDF manuals into structured JSON matching the Phase 1 schema
**Depends on**: Phase 1
**Requirements**: ETL-01
**Success Criteria** (what must be TRUE):
  1. PDFs from all three manufacturers (Sundance, Hot Spring, Bullfrog) can be processed through the extraction pipeline
  2. Extracted data conforms to the Phase 1 Pydantic schema and passes validation
  3. Manufacturer-specific extraction templates handle different PDF layouts (tables, multi-column, embedded specs)
  4. Extraction output includes page number and section reference for traceability back to source
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md -- Install dependencies, create ETL module skeleton, download manufacturer PDFs, analyze PDF structure
- [x] 02-02-PLAN.md -- Build core extraction engine: Claude PDF API wrapper, schema mapper, validators, output writer with provenance
- [x] 02-03-PLAN.md -- Create per-manufacturer extraction templates (Sundance, Hot Spring, Bullfrog) and pipeline orchestrator
- [x] 02-04-PLAN.md -- Execute extraction pipeline against all PDFs, validate output (switched to Gemini per user request)

### Phase 3: Web Scraping Pipeline
**Goal**: Automated extraction of technical specs from manufacturer websites to fill data gaps left by PDF extraction (dimensions, weights, water capacity, seating) -- all via static HTML scraping with httpx + BeautifulSoup
**Depends on**: Phase 1
**Requirements**: ETL-02
**Success Criteria** (what must be TRUE):
  1. Manufacturer website pages for all 19 POC models can be scraped and parsed
  2. Extracted web data conforms to the Phase 1 Pydantic schema and passes validation
  3. JavaScript-heavy manufacturer sites (dynamic content) are handled correctly
  4. Scraper captures source URL for every extracted data point
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- Install httpx/BS4/lxml/tenacity, create scrape module skeleton with URL registry, fetcher, parser base, and parsing utilities
- [x] 03-02-PLAN.md -- Build manufacturer-specific HTML parsers (Sundance, Hot Spring, Bullfrog) against live web pages
- [x] 03-03-PLAN.md -- Build merger and pipeline orchestrator, execute scraping against all 19 models, verify data gaps filled

### Phase 4: Data Verification and Population
**Goal**: All 190 data points (19 models x 10 categories) are human-verified and populated with full source tracking
**Depends on**: Phase 2, Phase 3
**Requirements**: ETL-03, ETL-04, ETL-05, DATA-03
**Success Criteria** (what must be TRUE):
  1. Every extracted data point has been reviewed by a human against the source document (PDF or website) before entering the verified data store
  2. A completeness dashboard shows coverage status for all 190 data points (19 models x 10 categories) with clear indication of verified/unverified/missing
  3. Every spec value in the verified data store links back to its source document (PDF filename + page, or URL)
  4. All 19 POC model JSON files pass Pydantic schema validation with zero errors
  5. Any data point that could not be found in source documents is explicitly marked as "not available" (not left empty or guessed)
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md -- Extend schema with DataQuality model, build automated verification checks (voltage, dimensions, jets, sources)
- [x] 04-02-PLAN.md -- Build completeness dashboard, not-available field marker, and anomaly report CLI
- [x] 04-03-PLAN.md -- Execute verification: fix confirmed errors, populate metadata on all 19 JSON files, human review checkpoint

### Phase 5: MCP Data Access Layer
**Goal**: Deterministic, strongly-typed MCP tools provide the sole gateway to verified data -- zero LLM logic in the data layer
**Depends on**: Phase 4
**Requirements**: QUERY-03, QUERY-04
**Success Criteria** (what must be TRUE):
  1. MCP tools use strongly-typed enumerated parameters (manufacturer, model name, spec category) -- no free-text query strings that could introduce ambiguity
  2. A lookup for any of the 190 verified data points returns the exact correct value from the JSON data store
  3. All 10 spec categories are queryable through MCP tools (pumps, circulation, spa pak, topside, jets, headrests, filters, heater, lights, covers)
  4. When data is not available for a requested model/category, the tool returns an explicit "not found" response (never an empty or null result without explanation)
  5. MCP tool tests cover all 19 models x 10 categories with automated pass/fail assertions
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Single Agent Core
**Goal**: A single monolithic agent answers spec questions accurately for all 19 models, proving core accuracy before multi-agent split
**Depends on**: Phase 5
**Requirements**: AGENT-02, QUERY-01, QUERY-05, RESP-02, RESP-03, RESP-06
**Success Criteria** (what must be TRUE):
  1. A user can type a natural language question ("What pump does the Sundance Aspen use?") and receive the correct part number, HP/wattage, and compatibility information
  2. When data is missing for a query, the agent responds with explicit "not available" messaging -- never fabricates a part number or spec
  3. Out-of-scope queries (models outside POC, pricing questions, non-technical questions) are handled gracefully with clear messaging about what the system can and cannot answer
  4. Response time from query submission to complete answer is under 3 seconds
  5. The agent correctly answers queries across all 10 spec categories, verified against a test matrix of representative questions
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: Multi-Agent Orchestration
**Goal**: The single agent is split into Concierge/Specialist/Validator with supervised handoffs and multi-turn conversation support
**Depends on**: Phase 6
**Requirements**: AGENT-01, AGENT-03, AGENT-04, AGENT-05, QUERY-02
**Success Criteria** (what must be TRUE):
  1. The Concierge agent clarifies ambiguous queries (e.g., "What about the pump?" prompts for which model) and guides the user through disambiguation
  2. The Validator agent checks every response for completeness and flags when spec fields are missing from the data store
  3. Multi-agent orchestration via LangGraph supervisor pattern routes queries through Concierge -> Specialist -> Validator without error propagation across agent boundaries
  4. A user can ask follow-up questions ("What about the filter for that model?") and the system maintains conversation context without requiring the user to re-specify the model
  5. All queries that passed with the single agent in Phase 6 still pass with the multi-agent system (no regression)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Response Quality
**Goal**: Every response includes source attribution, cross-references, and a clean scannable format that a technician trusts
**Depends on**: Phase 7
**Requirements**: RESP-01, RESP-04, RESP-05
**Success Criteria** (what must be TRUE):
  1. Every response includes source attribution showing which PDF/URL and page the data came from
  2. When a part fits multiple models, the response includes cross-reference information ("This pump also fits: Optima, Cameo")
  3. Response format is clean and scannable: part numbers are prominently displayed, not buried in prose; specs are structured (not paragraph-form)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

### Phase 9: Frontend
**Goal**: A React chat interface that Spaparts staff can use to interact with Dex in a professional, efficient manner
**Depends on**: Phase 7 (can begin in parallel with Phase 8 using agent API)
**Requirements**: UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):
  1. A React-based chat interface accepts natural language input and displays agent responses in real-time via SSE streaming
  2. Technical specs with multiple fields (e.g., all jet part numbers for a model) render as properly formatted tables, not raw text
  3. The interface presents a professional, concise persona -- no chatty filler, no unnecessary animations, fast and functional
  4. The chat interface connects to the FastAPI backend and handles the full query lifecycle (input -> streaming response -> rendered output)
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD
- [ ] 09-03: TBD

### Phase 10: Deployment and Hardening
**Goal**: Dex is hosted and accessible by Adam and Stephen for remote testing, stable enough for demo sessions
**Depends on**: Phase 8, Phase 9
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):
  1. The complete system (frontend + API + agents + MCP + data) is deployed to a hosted environment accessible via URL by Adam and Stephen
  2. The system handles multiple concurrent users without crashes or data corruption during demo/testing sessions
  3. Error handling covers API downtime, malformed queries, and unexpected agent failures gracefully (user sees helpful error messages, not stack traces)
  4. The full 190-data-point test matrix passes in the deployed environment (not just local)
**Plans**: TBD

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10
Note: Phases 2 and 3 can execute in parallel (both depend only on Phase 1). Phases 8 and 9 can execute in parallel (both depend on Phase 7).

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. Data Schema Design | 2/2 | ✓ Complete | 2026-02-14 |
| 2. PDF Extraction Pipeline | 4/4 | ✓ Complete | 2026-02-15 |
| 3. Web Scraping Pipeline | 3/3 | ✓ Complete | 2026-02-16 |
| 4. Data Verification and Population | 3/3 | ✓ Complete | 2026-02-16 |
| 5. MCP Data Access Layer | 0/TBD | Not started | - |
| 6. Single Agent Core | 0/TBD | Not started | - |
| 7. Multi-Agent Orchestration | 0/TBD | Not started | - |
| 8. Response Quality | 0/TBD | Not started | - |
| 9. Frontend | 0/TBD | Not started | - |
| 10. Deployment and Hardening | 0/TBD | Not started | - |
