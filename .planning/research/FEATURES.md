# Feature Research

**Domain:** AI-powered technical knowledge assistant / parts lookup system (internal staff tool)
**Researched:** 2026-02-14
**Confidence:** HIGH (for table stakes and core features); MEDIUM (for differentiators and future features)

## Feature Landscape

This research covers two distinct feature dimensions: (A) the **assistant interaction layer** that staff use daily, and (B) the **data management / ETL layer** that feeds accurate data into the system. Both are critical -- the assistant is only as good as its data, and great data is useless without a usable interface.

---

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or untrustworthy.

#### A. Assistant Interaction Features

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Natural language query input | Staff expect to type questions in plain English, not memorize query syntax | LOW | Simple text input; LLM handles NLP. The concierge agent parses intent. |
| Exact part number retrieval | Core value proposition. Staff need THE part number, not a list of maybes | MEDIUM | Requires structured data lookup via MCP tools, NOT vector similarity search. This is the #1 requirement per PROJECT.md. |
| Model/series/manufacturer disambiguation | Staff may say "Cameo pump" without specifying year or series; system must clarify | MEDIUM | Concierge agent must detect ambiguity and ask targeted follow-up questions before routing to specialist. |
| Spec category coverage (all 10 types) | Staff expect to ask about any of the 10 spec categories and get an answer | MEDIUM | Each category (pumps, controls, jets, filters, etc.) needs its own query pattern and data schema. |
| Source attribution / data provenance | When accuracy is critical, staff need to know WHERE the answer came from (which PDF, which manufacturer page) | LOW | Every response should cite the source document/page. Builds trust and enables verification. |
| "I don't know" honesty | Better to say "data not available for this model" than hallucinate a part number | LOW | Validator agent must detect missing data fields and surface gaps explicitly rather than letting LLM fill in. |
| Conversation context (multi-turn) | Staff asking about one model should be able to ask follow-up questions without re-specifying the model | MEDIUM | LangGraph state management maintains conversation context across turns. |
| Fast response time (< 3 seconds) | Staff are on the phone with customers; delays kill call efficiency | LOW | Structured JSON lookup is inherently fast. No vector DB queries or embedding generation needed. |
| Clean, scannable response format | Part numbers and specs need to be visually distinct, not buried in paragraphs | LOW | Structured response templates: part number prominently displayed, supporting details (HP, wattage, compatibility) in consistent format. |
| Error handling for unsupported queries | When staff ask about a model or spec outside POC scope, system should say so clearly | LOW | Concierge checks query against known model/spec inventory before routing. |

#### B. Data Management / ETL Features

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| PDF spec extraction pipeline | Manufacturer data lives in PDFs; system needs to ingest it | HIGH | Combination of PDF parsing (tables, text), AI-assisted extraction, and structured output to JSON. This is a major development effort. |
| Web scraping for manufacturer specs | Some specs are on manufacturer websites, not in PDFs | MEDIUM | Targeted scraping of specific manufacturer pages (Sundance, Hot Spring, Bullfrog). Not general-purpose crawling. |
| Structured JSON output schema | Extracted data must conform to a consistent schema per spec category | MEDIUM | Define strict schemas for each of the 10 spec categories. Schema violations caught at extraction time, not query time. |
| Human verification workflow | AI extraction cannot be trusted at 100% accuracy without human review | MEDIUM | Every extracted spec needs a human approval step before it enters the production dataset. This is non-negotiable per PROJECT.md. |
| Data completeness tracking | Know which models have complete data vs. gaps | LOW | Dashboard or report showing coverage: 19 models x 10 spec categories = 190 data points to track. |
| Source document management | Track which PDFs/URLs were used for each data point | LOW | Metadata layer linking each spec value to its source document and page number. |

---

### Differentiators (Competitive Advantage)

Features that set Dex apart from "just searching a PDF manually" or basic lookup tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-agent validation pipeline | Three-agent architecture (Concierge + Specialist + Validator) catches errors that single-agent systems miss | HIGH | The validator agent independently verifies that the specialist's response includes all required fields and that no data was fabricated. This is the key architectural differentiator. |
| Compatibility and cross-reference notes | Staff can ask "what pump fits the 2026 Cameo" AND get compatibility notes (e.g., "also fits Optima") | MEDIUM | Requires cross-reference data in the structured schema. Extremely valuable for staff who need to suggest alternatives. |
| Guided disambiguation flow | Instead of failing on ambiguous queries, system walks staff through clarification ("Which series? 880 or 980?") | MEDIUM | Concierge agent with decision-tree logic. Makes the system feel intelligent rather than brittle. |
| Confidence indicators on responses | System tells staff "HIGH confidence: verified data" vs. "LOW confidence: data may be incomplete" | LOW | Validator agent flags data completeness. Staff know when to double-check manually. |
| Bulk query mode | Staff can ask for all pump specs across a series, not just one model at a time | MEDIUM | "Show me all jet pump models for the 880 Series" returns a comparison table. Saves significant time for staff comparing models. |
| ETL diff detection | When manufacturer data changes (new PDF revision), system detects and flags differences from existing data | HIGH | Requires versioning of source documents and comparison logic. Prevents stale data. Future scope but high-value. |
| Query analytics / usage patterns | Track what staff ask most frequently to identify data gaps and UI improvements | LOW | Log queries, response success rates, and disambiguation frequency. Inform future development priorities. |
| Contextual help suggestions | After answering a question, suggest related lookups ("You might also need the filter spec for this model") | LOW | Pattern-based suggestions from common query sequences. Nice quality-of-life improvement. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems -- especially in a system demanding 100% accuracy.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| RAG / vector similarity search | "It's the standard AI approach" | Vector search returns "similar" results, not exact ones. For part numbers, "similar" = WRONG. A part number off by one digit ships the wrong physical part. Research confirms: "to the model, 120mm and 130mm look almost identical" in embedding space. | Structured data lookup via MCP tools against JSON/DB. Deterministic queries return exact matches. No approximation. |
| Free-form AI-generated spec descriptions | "Let the AI explain the specs in its own words" | LLMs will confidently fabricate plausible-sounding specs that are subtly wrong. A generated "5.0 HP pump" when the real spec is "4.0 HP" is dangerous. | Template-based responses that slot in verified data values. The LLM formats but does NOT generate spec data. |
| Auto-updating from manufacturer websites | "Just scrape the latest data automatically" | Unverified auto-updates could introduce errors silently. A changed part number or typo on the manufacturer site propagates immediately into staff answers. | ETL pipeline with human verification gate. New data is staged, reviewed, then promoted to production. |
| General-purpose chatbot personality | "Make it conversational and fun" | Staff on phone calls need answers fast. Chatty responses waste time and reduce trust in a professional tool. | Professional, concise tone. Answer the question, cite the source, done. Personality in the greeting, not in the data delivery. |
| Pricing integration in POC | "Show the price alongside the part number" | Pricing comes from a different system (Spaparts pricing), changes frequently, and mixing sources in POC adds complexity without validating the core hypothesis. | Explicitly out of scope for POC. Design the response format to accommodate pricing later, but don't fetch it now. |
| Full-text search across all documents | "Let staff search through the raw PDFs" | Bypasses the structured data pipeline, returns unverified results, and reintroduces the manual lookup problem the system is solving. | All queries go through the structured data layer. If data isn't extracted yet, flag it as a gap rather than falling back to PDF search. |
| Voice input / phone integration | "Staff are on the phone, let them talk to it" | Adds speech-to-text complexity, introduces transcription errors (especially for model names and part numbers), and dramatically increases POC scope. | Text-based input only for POC. Evaluate voice integration after core accuracy is proven. |
| Multi-language support | "Some manufacturers have specs in other languages" | Translation introduces error risk. For 3 US-market manufacturers in POC, all source material is English. | English-only for POC. Flag as consideration for full solution if international manufacturers are added. |

---

## Feature Dependencies

```
[ETL Pipeline: PDF Extraction]
    |
    v
[ETL Pipeline: Schema Validation]
    |
    v
[ETL Pipeline: Human Verification] -----> [Data Completeness Tracking]
    |
    v
[Structured JSON Dataset]
    |
    +-------------------------------+
    |                               |
    v                               v
[MCP Tool Server]              [Source Document Management]
    |
    v
[Specialist Agent (Dex)]
    |
    +-------------------------------+
    |                               |
    v                               v
[Validator Agent]              [Concierge Agent]
    |                               |
    +-------------------------------+
    |
    v
[React Frontend] -------> [Query Analytics]
    |
    v
[Hosted Deployment]
```

### Dependency Notes

- **Specialist Agent requires Structured JSON Dataset:** The entire assistant layer is useless without extracted, verified data. ETL must produce data BEFORE the assistant can be built meaningfully.
- **Validator Agent requires Specialist Agent:** Validator checks the specialist's output; it cannot operate independently.
- **Concierge Agent requires Specialist Agent:** Concierge routes to specialist; needs specialist to exist first. However, concierge disambiguation logic can be developed in parallel with stub data.
- **Human Verification requires PDF Extraction:** Cannot verify what hasn't been extracted yet. The extraction pipeline is the critical path.
- **MCP Tool Server requires Structured JSON Dataset:** MCP tools expose the structured data; the data must exist and have a stable schema first.
- **React Frontend requires at least Concierge Agent:** Frontend needs an agent endpoint to interact with. Can be developed in parallel with mock responses.
- **Query Analytics enhances Frontend:** Not a hard dependency, but analytics require the frontend to be generating queries.
- **Bulk Query Mode requires MCP Tool Server:** Needs the same data access layer, just with different query patterns.
- **Compatibility Notes require cross-reference data in schema:** The schema must be designed to include cross-reference relationships from the start, even if populated later.

---

## MVP Definition

### Launch With (v1 -- POC)

Minimum viable product -- what's needed to prove the concept to Adam and Stephen.

- [ ] **ETL: PDF extraction for 19 models** -- Core hypothesis: can we reliably extract specs from manufacturer documents?
- [ ] **ETL: Structured JSON schema for 10 spec categories** -- Data must be consistently structured to enable reliable lookup
- [ ] **ETL: Human verification workflow (even if manual)** -- Every data point reviewed before going live. Can be a simple spreadsheet review for POC.
- [ ] **Assistant: Concierge agent with disambiguation** -- Staff type a question, system clarifies if ambiguous, routes to specialist
- [ ] **Assistant: Specialist agent with MCP tool queries** -- Deterministic lookup against structured JSON. No RAG, no vector search.
- [ ] **Assistant: Validator agent for response completeness** -- Catches missing fields, prevents partial answers from reaching staff
- [ ] **Assistant: Source attribution on every response** -- Staff see where the data came from
- [ ] **Assistant: "I don't know" for missing data** -- Honest gaps over hallucinated answers
- [ ] **Frontend: React chat interface** -- Clean, fast, scannable responses with part numbers prominent
- [ ] **Deployment: Hosted for remote testing** -- Adam and Stephen can access from anywhere

### Add After Validation (v1.x)

Features to add once Adam and Stephen confirm the core works.

- [ ] **Compatibility cross-references** -- Trigger: staff frequently ask "what else does this part fit?"
- [ ] **Bulk query / comparison tables** -- Trigger: staff need to compare specs across models in a series
- [ ] **Confidence indicators** -- Trigger: some data points are less certain than others and staff need to know
- [ ] **Query analytics dashboard** -- Trigger: need to understand usage patterns and identify data gaps
- [ ] **ETL: Web scraping for additional data sources** -- Trigger: some specs not available in PDFs
- [ ] **Contextual help suggestions** -- Trigger: staff follow predictable query patterns

### Future Consideration (v2+)

Features to defer until POC validates and full solution is scoped.

- [ ] **Expanded model coverage (all years, all manufacturers)** -- POC proves concept with 19 models; full solution scales to thousands
- [ ] **PostgreSQL data storage** -- JSON files work for 19 models; database needed at scale
- [ ] **Pricing integration** -- Separate system, separate data source, separate validation
- [ ] **ETL diff detection / version tracking** -- Important for ongoing maintenance, not for initial POC
- [ ] **Real-time inventory integration** -- Requires Spaparts system integration
- [ ] **Voice input / phone integration** -- Only after text-based accuracy is proven
- [ ] **End-customer access** -- Different UX, different trust model, different scope entirely

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| ETL: PDF extraction pipeline | HIGH | HIGH | P1 |
| ETL: Structured JSON schema | HIGH | MEDIUM | P1 |
| ETL: Human verification workflow | HIGH | MEDIUM | P1 |
| Exact part number retrieval | HIGH | MEDIUM | P1 |
| Model/series disambiguation | HIGH | MEDIUM | P1 |
| Spec category coverage (10 types) | HIGH | MEDIUM | P1 |
| Source attribution | HIGH | LOW | P1 |
| "I don't know" honesty | HIGH | LOW | P1 |
| Multi-turn conversation context | MEDIUM | MEDIUM | P1 |
| Fast response (< 3s) | HIGH | LOW | P1 |
| Clean response format | HIGH | LOW | P1 |
| Unsupported query handling | MEDIUM | LOW | P1 |
| Multi-agent validation pipeline | HIGH | HIGH | P1 |
| Compatibility cross-references | MEDIUM | MEDIUM | P2 |
| Guided disambiguation flow | MEDIUM | MEDIUM | P2 |
| Confidence indicators | MEDIUM | LOW | P2 |
| Bulk query mode | MEDIUM | MEDIUM | P2 |
| Query analytics | LOW | LOW | P2 |
| Contextual help suggestions | LOW | LOW | P3 |
| ETL diff detection | MEDIUM | HIGH | P3 |
| Data completeness dashboard | LOW | LOW | P2 |
| Source document management | LOW | LOW | P2 |

**Priority key:**
- P1: Must have for POC launch -- proves the concept
- P2: Should have, add once core is validated
- P3: Nice to have, future consideration

---

## Competitor / Alternative Feature Analysis

| Feature | Manual Lookup (Current) | Generic AI Chatbot (e.g., ChatGPT) | Parts Catalog Software (e.g., Intellinet, PTC) | Dex (Our Approach) |
|---------|------------------------|--------------------------------------|------------------------------------------------|---------------------|
| Exact part numbers | Yes (but slow, error-prone) | No (hallucinations likely) | Yes (pre-loaded catalog) | Yes (structured lookup + validation) |
| Natural language input | No | Yes | No (form-based search) | Yes |
| Source attribution | Manual (staff know which PDF) | No | Limited | Yes (every response) |
| Disambiguation | Staff judgment | Attempts but often wrong | Dropdown filters | Guided multi-turn clarification |
| Multi-spec lookup | Very slow (check each PDF) | Unreliable | Possible but rigid | Bulk query mode |
| Data freshness | Manual updates | Training cutoff | Manual catalog updates | ETL pipeline + human review |
| Accuracy guarantee | Depends on staff expertise | None | High (if data correct) | Structured lookup + validator agent |
| Speed | Minutes per lookup | Seconds (but wrong) | Seconds | Seconds (and right) |
| Setup cost | None | None | High (enterprise licensing) | Medium (ETL pipeline development) |

**Key insight:** Dex occupies a unique position: natural language UX (like a chatbot) with deterministic accuracy (like a catalog system). The multi-agent validation pipeline is what makes this possible -- no single component achieves both.

---

## Sources

- [Circuitry.AI Parts Aidvisor](https://circuitry.ai/intelligent-parts-lookup-with-parts-aidvisor) -- AI parts lookup features
- [Squirro: GraphRAG Deterministic AI](https://squirro.com/squirro-blog/graphrag-deterministic-ai-accuracy) -- Deterministic retrieval over structured data
- [Smile.eu: Retrieval for Structured Data](https://smile.eu/en/publications-and-events/retrieval-structured-data-precision-first-alternative-vector-only-rag-excel) -- Why vector search fails for exact matches
- [Exxact: Alternative RAG Models](https://www.exxactcorp.com/blog/deep-learning/alternative-rag-models) -- Structured Retrieval RAG over SQL/JSON
- [AI21: RAG for Structured Data](https://www.ai21.com/knowledge/rag-for-structured-data/) -- Structured data accuracy vs. vector search
- [LangGraph Documentation](https://www.langchain.com/langgraph) -- Multi-agent orchestration patterns
- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) -- MCP tool definitions for structured data access
- [LangGraph Multi-Turn Conversation](https://langchain-ai.github.io/langgraph/how-tos/multi-agent-multi-turn-convo-functional/) -- Conversation context in multi-agent systems
- [Explosion.ai: PDFs to Structured Data](https://explosion.ai/blog/pdfs-nlp-structured-data) -- PDF extraction pipeline approaches
- [NVIDIA: PDF Data Extraction](https://developer.nvidia.com/blog/approaches-to-pdf-data-extraction-for-information-retrieval/) -- PDF extraction accuracy and approaches
- [Intellinet Parts Catalog](https://www.intellinetsystem.com/blogs/parts-lookup-module-of-intellinet-electronic-part-catalog-software) -- Traditional parts catalog features
- [PTC Electronic Parts Catalog](https://www.ptc.com/en/technologies/service-lifecycle-management/electronic-parts-catalog-software) -- Enterprise catalog feature set
- [Kapa.ai: RAG Best Practices](https://www.kapa.ai/blog/rag-best-practices) -- Lessons from 100+ technical teams
- [Help Scout: AI Knowledge Base Software 2026](https://www.helpscout.com/blog/ai-knowledge-base/) -- Current AI knowledge base features
- [Talkdesk Copilot](https://www.talkdesk.com/cloud-contact-center/omnichannel-engagement/copilot/) -- AI assistant for call center agents

---
*Feature research for: AI-powered technical knowledge assistant / parts lookup (Dex)*
*Researched: 2026-02-14*
