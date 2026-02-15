# Dex — Technical Knowledge Assistant

## What This Is

A proof-of-concept AI assistant for Spaparts that lets internal staff instantly look up exact technical specifications and part numbers for hot tub/spa models. Instead of manually digging through PDFs and manufacturer websites, staff type a question and get the precise part, spec, or dimension — with zero tolerance for inaccuracy.

## Core Value

100% accurate retrieval of technical specifications and part numbers. A wrong part is a failure — there is no acceptable margin of error.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] ETL pipeline extracts specs from manufacturer PDFs and websites into structured JSON
- [ ] AI-assisted extraction with human verification workflow
- [ ] Multi-agent assistant answers the 10 target question types accurately
- [ ] Concierge agent clarifies user intent (manufacturer, series, model, year)
- [ ] Specialist agent queries structured data via MCP tools
- [ ] Validator ensures all spec fields are checked and flags missing data
- [ ] Response includes part details: part number, HP/wattage, compatibility notes
- [ ] 19 POC models covered across 3 manufacturers (2026 only)
- [ ] React frontend for staff interaction
- [ ] Hosted deployment for remote client testing

### Out of Scope

- Pricing data — not needed for POC, add later from Spaparts pricing system
- Models outside 2026 — full solution scope, not POC
- Manufacturers beyond Sundance/Hot Spring/Bullfrog — full solution scope
- End-customer access — internal staff tool only for now
- Mobile app — web-first
- Real-time inventory integration — future scope

## Context

**Client:** Spaparts (Adam Rieck & Stephen Reed). They handle thousands of SKUs across multiple manufacturers and years. Staff currently look up specs manually — slow and error-prone.

**The "Adam" challenge:** Spaparts needs an assistant that a knowledgeable technician would trust. Approximate answers are dangerous — a part number that's one digit off means the wrong physical part ships.

**POC target models (19 total, all 2026):**

| Manufacturer | Series | Models |
|---|---|---|
| Sundance | 880 Series | Aspen, Optima, Cameo, Altamar, Vistamar, Marin, Capris |
| Hot Spring Spas | Highlife Collection | Grandee, Envoy, Aria, Vanguard, Sovereign, Prodigy, Jetsetter LX, Jetsetter |
| Bullfrog Spas | M Series | M9, M8, M7, M6 |

**10 target spec categories:**
1. Jet pump model/HP
2. Circulation pump type
3. Spa pak (control box) version
4. Topside control panel model
5. Jet part numbers and quantities
6. Headrest part numbers and quantities
7. Filter cartridge specifications
8. Heater element wattage/model
9. Light bulb/LED type
10. Physical cover dimensions

**Data sources:** Manufacturer websites, PDF manuals, spec sheets. Data needs to be extracted and structured — this extraction pipeline is part of the POC.

**Architecture direction from charter (flexible):** LangGraph multi-agent, MCP for data access, fastMCP Python server, React frontend. The key architectural insight: no RAG/vector search — structured data lookup via MCP tools to eliminate hallucination risk.

**Multi-agent design:**
- **Concierge** — front-end agent that clarifies intent, manages conversation, formats responses. Professional and helpful persona. No direct DB access.
- **Dex (Specialist)** — backend data expert that executes precise queries via MCP tools. Concise, data-focused.
- **Validator** — ensures all spec fields are checked, flags gaps.

## Constraints

- **Accuracy**: 100% correct part numbers and specs — no approximation, no hallucination
- **Data format (POC)**: Local JSON for structured spec data (PostgreSQL for full solution)
- **Stack**: Flexible — charter suggests Python/LangGraph/MCP/React but open to alternatives
- **Deployment**: Must be hosted for Adam & Stephen to test remotely
- **Scope**: Strictly 19 models, 2026 only, 3 manufacturers

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Structured lookup over RAG | Wrong parts are unacceptable — vector similarity can't guarantee exact matches | -- Pending |
| ETL pipeline in POC scope | Proving extraction works is as important as proving the assistant works | -- Pending |
| No pricing for POC | Focus on technical accuracy first, pricing comes from separate Spaparts system | -- Pending |
| Stack flexible | Charter suggests LangGraph/MCP/React but open to research-driven alternatives | -- Pending |
| AI + human verification for ETL | Pure AI extraction can't be trusted at 100% accuracy without human check | -- Pending |

---
*Last updated: 2026-02-14 after initialization*
