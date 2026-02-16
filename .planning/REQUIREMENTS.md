# Requirements: Dex -- Technical Knowledge Assistant

**Defined:** 2026-02-14
**Core Value:** 100% accurate retrieval of technical specifications and part numbers -- a wrong part is a failure.

## v1 Requirements

### Data Extraction (ETL)

- [x] **ETL-01**: PDF extraction pipeline extracts specs from manufacturer PDF manuals into structured JSON
- [x] **ETL-02**: Web scraping pipeline extracts specs from manufacturer websites into structured JSON
- [ ] **ETL-03**: AI-assisted extraction with human verification for every data point
- [ ] **ETL-04**: Data completeness dashboard tracks 190 data points (19 models x 10 categories)
- [ ] **ETL-05**: Source document tracking links each spec value to its source PDF/URL and page

### Data Schema (DATA)

- [x] **DATA-01**: Structured JSON schema covers all 10 spec categories with strict field definitions
- [x] **DATA-02**: Schema includes cross-reference fields for part compatibility across models
- [ ] **DATA-03**: All 19 POC models populated with verified data for all 10 spec categories

### Agent System (AGENT)

- [ ] **AGENT-01**: Concierge agent clarifies user intent and manages conversation flow
- [ ] **AGENT-02**: Specialist agent (Dex) executes precise queries via MCP tools
- [ ] **AGENT-03**: Validator agent verifies response completeness and flags missing data
- [ ] **AGENT-04**: Multi-agent orchestration via LangGraph supervisor pattern
- [ ] **AGENT-05**: Multi-turn conversation context maintained across follow-up questions

### Query & Retrieval (QUERY)

- [ ] **QUERY-01**: Natural language query input parsed by Concierge
- [ ] **QUERY-02**: Model/series/manufacturer disambiguation when query is ambiguous
- [ ] **QUERY-03**: Exact part number retrieval via structured lookup (not RAG/vector)
- [ ] **QUERY-04**: All 10 spec categories queryable (pumps, controls, jets, filters, heater, lights, covers, headrests)
- [ ] **QUERY-05**: Out-of-scope queries handled gracefully with clear messaging

### Response Quality (RESP)

- [ ] **RESP-01**: Every response includes source attribution (which PDF/URL the data came from)
- [ ] **RESP-02**: Missing data explicitly flagged as "not available" (never hallucinate)
- [ ] **RESP-03**: Response includes part details: part number, HP/wattage, compatibility notes
- [ ] **RESP-04**: Cross-reference information shows which other models a part fits
- [ ] **RESP-05**: Clean, scannable response format with part numbers prominently displayed
- [ ] **RESP-06**: Response time under 3 seconds

### Frontend (UI)

- [ ] **UI-01**: React chat interface for staff interaction
- [ ] **UI-02**: Real-time table rendering for technical specs
- [ ] **UI-03**: Professional, concise persona (not chatty)

### Deployment (DEPLOY)

- [ ] **DEPLOY-01**: Hosted deployment accessible by Adam & Stephen remotely
- [ ] **DEPLOY-02**: Stable enough for client demo/testing sessions

## v2 Requirements

### Enhanced Query

- **EQUERY-01**: Bulk query mode -- compare specs across an entire series
- **EQUERY-02**: Confidence indicators on responses (HIGH/LOW certainty)
- **EQUERY-03**: Contextual help suggestions after answering a question

### Analytics & Monitoring

- **ANALY-01**: Query analytics dashboard -- track most asked questions, response success rates
- **ANALY-02**: ETL diff detection -- flag when manufacturer data changes

### Expanded Coverage

- **COVER-01**: Additional model years beyond 2026
- **COVER-02**: Additional manufacturers beyond Sundance/Hot Spring/Bullfrog
- **COVER-03**: PostgreSQL database for scale (replace local JSON)

### Pricing & Integration

- **PRICE-01**: Pricing data integration from Spaparts pricing system
- **INTEG-01**: Real-time inventory integration

## Out of Scope

| Feature | Reason |
|---------|--------|
| RAG / vector similarity search | Wrong parts are unacceptable -- vector search returns "similar" not "exact" |
| AI-generated spec descriptions | LLMs fabricate plausible-but-wrong specs -- template responses with verified data only |
| Auto-updating from manufacturer sites | Unverified auto-updates could introduce silent errors |
| Voice input / phone integration | Adds STT complexity, introduces transcription errors for part numbers |
| End-customer access | Different UX, trust model, and scope -- internal staff only for POC |
| Pricing in POC | Comes from separate Spaparts system, adds complexity without proving core hypothesis |
| Models outside 2026 | Full solution scope -- POC proves concept with 19 models |
| Multi-language support | All 3 POC manufacturers publish in English |
| Full-text PDF search fallback | Bypasses structured data layer, reintroduces manual lookup problem |
| General-purpose chatbot personality | Staff need fast answers, not conversation -- professional and concise |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ETL-01 | Phase 2 | Complete |
| ETL-02 | Phase 3 | Complete |
| ETL-03 | Phase 4 | Complete |
| ETL-04 | Phase 4 | Complete |
| ETL-05 | Phase 4 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 4 | Complete |
| AGENT-01 | Phase 7 | Complete |
| AGENT-02 | Phase 6 | Complete |
| AGENT-03 | Phase 7 | Complete |
| AGENT-04 | Phase 7 | Complete |
| AGENT-05 | Phase 7 | Complete |
| QUERY-01 | Phase 6 | Complete |
| QUERY-02 | Phase 7 | Complete |
| QUERY-03 | Phase 5 | Complete |
| QUERY-04 | Phase 5 | Complete |
| QUERY-05 | Phase 6 | Complete |
| RESP-01 | Phase 8 | Complete |
| RESP-02 | Phase 6 | Complete |
| RESP-03 | Phase 6 | Complete |
| RESP-04 | Phase 8 | Complete |
| RESP-05 | Phase 8 | Complete |
| RESP-06 | Phase 6 | Complete |
| UI-01 | Phase 9 | Complete |
| UI-02 | Phase 9 | Complete |
| UI-03 | Phase 9 | Complete |
| DEPLOY-01 | Phase 10 | Pending |
| DEPLOY-02 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-02-14*
*Last updated: 2026-02-14 after roadmap creation*
