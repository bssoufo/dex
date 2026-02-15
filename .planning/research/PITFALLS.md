# Pitfalls Research

**Domain:** AI-powered technical knowledge assistant / spa parts lookup (Dex POC)
**Researched:** 2026-02-14
**Confidence:** HIGH (multiple verified sources, domain-specific analysis)

## Critical Pitfalls

These are project-killing mistakes. Each one can cause a rewrite, a failed demo, or a fundamentally broken product.

### Pitfall 1: The LLM Fills the Gap with a Plausible Guess

**What goes wrong:**
When the structured data lookup returns no result (missing data, slightly misspelled query, model/year mismatch), the LLM does what LLMs do: it generates a plausible-sounding answer instead of saying "I don't know." In the spa parts domain, this means returning a part number that *looks* right -- correct format, correct manufacturer prefix -- but is actually for a different model year or a different series. A part number off by one digit ships the wrong physical component. This is the single most dangerous failure mode for Dex.

**Why it happens:**
LLMs are trained on next-token prediction with no fact-checking mechanism. They are "programmed to respond to prompts as best they can, even if they don't have the required data." When retrieval fails or returns partial results, the model fills the gap with its training data or pattern-matches to something similar. With spa parts, part numbers follow predictable patterns (manufacturer prefixes, sequential numbering), making hallucinated numbers extra convincing.

**How to avoid:**
1. **Never let the LLM generate part numbers.** Part numbers must come exclusively from the structured JSON data store via MCP tool calls. The LLM's role is intent parsing and response formatting, never data generation.
2. **Implement hard "no data" responses.** When an MCP tool returns no match, the system MUST respond with "I don't have that information" -- not pass the question to the LLM for a best guess.
3. **Validate every response against the data store.** The Validator agent must verify that every part number, spec value, and dimension in the final response exists verbatim in the structured data. Any value not traceable to a specific JSON field is rejected.
4. **Constrain LLM output with structured schemas.** Use Pydantic models or JSON schema constraints so the LLM can only populate fields from a controlled vocabulary, never free-text part numbers.

**Warning signs:**
- The assistant gives answers for models not in the 19-model POC dataset
- Responses contain part numbers not found in any JSON file
- The system never says "I don't know" during testing
- Part numbers in responses differ slightly from the data store (transposed digits, wrong suffix)

**Phase to address:**
Phase 1 (Data + Architecture). The "never generate, only retrieve" constraint must be baked into the system architecture from day one. This is not a later-phase polish item -- it is the foundational design principle.

---

### Pitfall 2: PDF Extraction Looks Right but Has Silent Data Corruption

**What goes wrong:**
AI-assisted extraction from manufacturer PDFs produces structured JSON that *appears* correct on spot-check but contains subtle errors: transposed digits in part numbers, merged cell values attributed to the wrong model, HP values from one column shifted to an adjacent column, or dimension values with wrong units. These errors are invisible until a technician orders the wrong part.

**Why it happens:**
Manufacturer spec sheets are semi-structured with inconsistent formatting. Tables have merged cells, nested headers, model-specific footnotes, and irregular layouts. OCR engines and LLMs both struggle with these: "OCR engines extract all text without preserving logical reading order" and "tables in spec sheets vary in complexity with nested information, merged cells, or irregular layouts." The three POC manufacturers (Sundance, Hot Spring, Bullfrog) each use different PDF layouts, so extraction logic that works for one manufacturer fails silently on another.

**How to avoid:**
1. **Human verification is mandatory, not optional.** Every extracted data point for all 19 models must be verified against the source PDF by a human before entering the production data store. This is already in the project plan -- do not skip it under time pressure.
2. **Build a verification UI, not just a JSON diff.** Show the extracted value side-by-side with the relevant section of the source PDF so the verifier can visually confirm. A JSON file alone is not verifiable.
3. **Manufacturer-specific extraction templates.** Do not try to build one universal PDF parser. Build three separate extraction configurations tuned to Sundance, Hot Spring, and Bullfrog document formats.
4. **Automated consistency checks.** After extraction, run sanity checks: part numbers match expected format patterns, HP values are within plausible ranges, dimensions are internally consistent (length > width for rectangular covers).
5. **Track extraction provenance.** Each data field should reference its source: which PDF, which page, which table/section. This enables re-verification and debugging.

**Warning signs:**
- Extraction pipeline produces clean results on first try with no errors flagged (suspiciously clean)
- Different extraction runs on the same PDF produce slightly different values
- Part numbers extracted don't match the format patterns used by that manufacturer
- Numeric values have unusual precision (e.g., 5.000001 HP instead of 5.0 HP)

**Phase to address:**
Phase 1 (Data/ETL). The extraction pipeline and verification workflow must be built together. Extraction without verification is not "done" -- it is dangerous.

---

### Pitfall 3: Multi-Agent Orchestration Becomes a Debugging Nightmare

**What goes wrong:**
The three-agent design (Concierge, Dex Specialist, Validator) creates interaction patterns that are hard to observe and debug. A user asks "What pump does the 2026 Cameo use?" and gets an incorrect answer. Was the intent parsed wrong by Concierge? Did the Specialist query the wrong model? Did the Validator fail to catch a mismatch? The state passed between agents makes it hard to isolate which agent failed and why. "A single agent failure can disrupt shared states or trigger unexpected behaviors in downstream agents, causing cascading issues that are difficult to isolate."

**Why it happens:**
Multi-agent systems are inherently harder to debug than single-agent systems because:
- Agents are non-deterministic -- the same input can produce different execution paths
- State transforms are implicit -- each agent reads/writes shared state, and the transformation logic is buried in LLM reasoning
- Error propagation is silent -- Concierge misinterprets "Cameo" as "Capri" and passes it downstream; Specialist dutifully looks up Capri specs; Validator confirms Capri specs are valid; user gets a confidently wrong answer
- LangGraph's graph-based execution adds its own debugging complexity with "steep learning curve, debugging complexity, and significant infrastructure needs"

**How to avoid:**
1. **Start with a single agent that works, then split.** Get one agent doing intent parsing + data lookup + response formatting correctly for all 10 spec categories. Only then factor into Concierge/Specialist/Validator roles. This validates the core logic before adding orchestration complexity.
2. **Log every agent hand-off.** At each transition point, log: the full state being passed, which agent is sending, which is receiving, and the "contract" being fulfilled. Use LangGraph's built-in tracing or LangSmith.
3. **Make agent boundaries deterministic where possible.** Concierge extracts structured intent (manufacturer, series, model, year, spec_category) into a typed schema. Specialist receives this schema and executes a deterministic MCP tool call. The less LLM reasoning happens at boundary crossings, the more debuggable the system.
4. **Build a "replay" capability.** Save conversation traces and be able to replay them to reproduce issues. Non-determinism means you need the actual execution trace, not just the input.

**Warning signs:**
- You cannot explain *why* the system gave a particular answer by reading the logs
- Fixing a bug in one agent causes regressions in another agent's behavior
- Different runs of the same question produce different answers
- You spend more time debugging agent interactions than building features

**Phase to address:**
Phase 2 (Agent Architecture). But the mitigation strategy of "start with single agent" means Phase 2 should begin with a monolithic agent and refactor into multi-agent only after core accuracy is proven. Do not design multi-agent from the start.

---

### Pitfall 4: Confusing "Demo Works" with "System Is Accurate"

**What goes wrong:**
The POC demo works well for the 5 questions tested during development. Adam and Stephen start testing and within 30 minutes find failures: edge cases like models with multiple pump configurations, year-specific part number changes, ambiguous queries ("What filter does a Grandee use?" -- which Grandee? which filter position?). The system looked done because development testing covered the happy path, not the combinatorial space of 19 models x 10 spec categories x ambiguous query variations.

**Why it happens:**
AI POC testing suffers from confirmation bias. You test the queries that you know work. With 19 models and 10 spec categories, there are 190 minimum data points, each queryable in multiple natural language variations. A demo that handles 10 queries correctly covers ~5% of the space. "What begins as a simple test often balloons" -- but the problem here is the opposite: what begins as a simple test stays too simple.

**How to avoid:**
1. **Build a systematic test matrix.** 19 models x 10 categories = 190 required test cases minimum. Each test case has: input query, expected output (exact part number/spec), actual output, pass/fail. This is not optional polish -- it is the definition of 100% accuracy.
2. **Test with adversarial queries.** Include: misspelled model names, ambiguous queries missing manufacturer/year, queries for models NOT in the dataset (should return "not available"), queries mixing information from multiple categories.
3. **Let the client define test cases.** Ask Adam and Stephen to provide the 20 questions they would ask on day one. These will be different from developer-designed test cases and will expose real-world failure modes.
4. **Automate regression testing.** Every query that fails becomes a permanent test case. Run the full test suite after every change.

**Warning signs:**
- No formal test matrix exists
- Testing is done by the developer who built the system (confirmation bias)
- "It works" is based on < 20 manual queries
- No one has tested with intentionally tricky or ambiguous inputs

**Phase to address:**
Phase 3 (Testing/Validation). But the test matrix structure should be designed in Phase 1 (what does "correct" look like for each model x category combination?), and test cases should be written alongside data extraction, not after.

---

### Pitfall 5: Treating Structured Lookup as Simple When the Schema Is Complex

**What goes wrong:**
The project assumes that structured JSON lookup is straightforward: query the right model, return the right spec. But spa parts data has relational complexity that flat JSON struggles with:
- A model has multiple pump positions, each with different specs
- Jet counts and part numbers vary by configuration option (e.g., with/without a specific jet package)
- Some specs are shared across a series (same heater for all 880 Series) while others are model-specific
- Part numbers have supersession chains (old part replaced by new part)
- Compatibility notes create conditional relationships ("use part X with serial numbers before Y, part Z after")

Flat JSON either duplicates data (causing consistency issues) or loses these relationships (causing incorrect lookups).

**Why it happens:**
The POC starts with "just put the specs in JSON" because it is the simplest approach for 19 models. But manufacturer data is inherently relational. Flattening it loses information. The decision to use JSON for the POC (with PostgreSQL later) is correct for velocity, but the JSON schema must be designed to handle relational complexity, not just key-value pairs.

**How to avoid:**
1. **Design the JSON schema before extracting data.** Map the actual data relationships across all 3 manufacturers first. Understand the full complexity of the domain before committing to a schema.
2. **Model the relational aspects explicitly.** Use nested structures, arrays of variants, and explicit relationship fields rather than flattening everything into simple key-value pairs.
3. **Design for the PostgreSQL migration.** The JSON schema should map cleanly to future relational tables. If the JSON schema cannot express the data correctly, the relational schema will inherit the same problems.
4. **Validate schema against real data early.** Take 3 models (one per manufacturer) and fully populate the schema. Identify where the schema breaks before extracting all 19 models.

**Warning signs:**
- The JSON schema is a flat object with 50+ top-level fields
- Different models require different schema structures (sign of under-modeling)
- Queries require combining data from multiple places in the JSON (sign of poor normalization for lookup)
- "Edge case" data does not fit the schema without hacks

**Phase to address:**
Phase 1 (Data Architecture). Schema design must happen before ETL begins. Getting the schema wrong means re-extracting all data.

---

### Pitfall 6: MCP Tool Design That Leaks LLM Judgment Into Data Retrieval

**What goes wrong:**
The MCP tools are designed with broad query interfaces like `search_parts(query: str)` that rely on the LLM to formulate good search terms. This reintroduces the hallucination risk that structured lookup was meant to eliminate. The LLM decides *how* to query, and if it queries incorrectly (wrong model name format, wrong parameter), it gets wrong results or no results -- and then guesses.

**Why it happens:**
It feels natural to design tools that accept natural language queries because LLMs are good at generating natural language. But this conflates two concerns: intent extraction (what does the user want?) and data retrieval (get the exact data). The LLM should handle the first; the tool should handle the second with zero ambiguity.

**How to avoid:**
1. **Design MCP tools with strongly-typed, enumerated parameters.** Not `search_parts(query: str)` but `get_pump_spec(manufacturer: Literal["sundance", "hotspring", "bullfrog"], model: str, year: int, pump_position: Optional[int])`. The LLM's job is to map user intent to these parameters, not to formulate a search query.
2. **Enumerate valid values.** The tool descriptions should list valid manufacturers, model names, and spec categories. This gives the LLM a closed vocabulary to map to, not an open-ended query interface.
3. **Return explicit "not found" responses.** Tools should return structured error responses (`{"found": false, "reason": "model 'Camero' not recognized, did you mean 'Cameo'?"}`) rather than empty results that the LLM must interpret.
4. **Keep tool count small and specific.** One tool per spec category (or a small set of well-defined tools) is better than one large flexible tool. More specific tools = less room for LLM error.

**Warning signs:**
- MCP tools accept free-text string parameters for data that has a finite set of valid values
- The LLM must "figure out" how to call the tool rather than mapping to an obvious parameter set
- Tool calls sometimes return empty results that the LLM then "fills in"
- Tool descriptions are vague about what valid inputs look like

**Phase to address:**
Phase 1 (Architecture) and Phase 2 (Agent/Tool Implementation). Tool interface design is an architectural decision that must be made before agent development begins.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding model names in agent prompts instead of reading from data store | Fast to prototype | Adding a new model requires prompt changes across all agents | POC only, but must be flagged for refactor before production |
| Skipping human verification for "obviously correct" extractions | Saves verification time | Silent data errors that erode trust when discovered by client | Never. 100% accuracy requirement means 100% verification. |
| Single flat JSON file per manufacturer instead of per-model files | Simple file management | Large files become unwieldy; partial updates require full file reads; merge conflicts | POC only, acceptable if schema is correct |
| No automated test suite -- manual testing only | Faster initial development | Every change risks regression; cannot prove 100% accuracy claim | Never for this project. The accuracy claim demands automated verification. |
| Using LLM to fuzzy-match model names instead of strict matching | Handles typos gracefully | "Cameo" matches to "Capri" when both exist; false confidence in results | Only with explicit disambiguation step and user confirmation |
| Storing extraction provenance as comments in JSON | Quick to add | Comments stripped by JSON parsers; provenance data lost | Never. Use a separate provenance tracking structure. |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LangGraph state management | Passing full conversation history between agents, causing token bloat and context confusion | Pass only the structured intent object and relevant data between agents. Summarize conversation history. |
| FastMCP server | Using SSE transport (deprecated since Nov 2025 protocol update) | Use Streamable HTTP transport. SSE is backward-compatible but not recommended for new projects. |
| FastMCP + MCP SDK | Not pinning FastMCP version; MCP SDK 1.23 broke FastMCP patches | Pin FastMCP to 3.x (released Jan 2026). Check compatibility with MCP SDK version before upgrading. |
| LLM API (Claude/OpenAI) | Not handling rate limits or API errors gracefully | Implement retry logic with exponential backoff. Return "service temporarily unavailable" rather than crashing. |
| PDF extraction libraries | Using a single extraction library for all PDF types | Different manufacturers need different extraction approaches. Evaluate per-manufacturer: some may need OCR, others have selectable text. |
| Deployment (hosted for client) | Exposing MCP server without authentication | All MCP servers must have authentication. Research found ~2,000 MCP servers exposed without auth in 2025. Even for POC, use at minimum API key auth. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all JSON data into LLM context per query | Slow responses, high token costs | Load only the relevant model's data via MCP tool call | When data exceeds 19 models (POC scale is fine, but architecture should not assume all data fits in context) |
| No response caching | Same question asked 10 times = 10 full LLM round-trips | Cache MCP tool responses (same query = same data). LLM response caching is harder due to non-determinism but tool response caching is deterministic. | At client testing scale when multiple staff ask similar questions |
| Synchronous multi-agent execution | User waits while Concierge -> Specialist -> Validator run sequentially | For POC this is acceptable. For production, consider streaming partial responses. | When response latency exceeds 10-15 seconds and users lose patience |
| Storing all conversation history in LangGraph state | State objects grow unbounded, LLM calls slow down | Implement conversation window or summarization. For POC, a reasonable limit of ~20 exchanges. | After extended conversations with the same user (15+ exchanges) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| MCP server exposed without authentication | Anyone can query internal parts data, tool listings, and potentially exfiltrate data | Implement API key auth at minimum. FastMCP 3.0 supports granular authorization. |
| Manufacturer data (PDFs, spec sheets) stored in public repo | Proprietary manufacturer specifications leaked | Store data files outside git repo or in encrypted storage. Use .gitignore for all data directories. |
| LLM prompt containing business logic visible to users | Competitor could reverse-engineer the system's approach | Do not expose system prompts in frontend. Keep agent prompts server-side only. |
| No input sanitization on user queries | Prompt injection could cause the agent to ignore constraints and generate fabricated specs | Sanitize inputs, implement prompt injection detection, and ensure system prompts have strong guardrails. |
| API keys for LLM services hardcoded or in frontend | Key theft, unauthorized usage, cost exposure | Use environment variables server-side. Never expose API keys to the frontend. |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Returning raw JSON or unformatted data | Staff cannot quickly parse technical specs from wall of text | Format responses with clear labels, units, and visual hierarchy. "Jet pump: Wavemaster 9000, 2.5 HP, Part #6500-352" |
| Not distinguishing between "no data available" and "system error" | Staff unsure if the answer is missing or the system is broken | Explicit messaging: "This spec is not yet available for the 2026 Cameo" vs "I encountered an error, please try again" |
| Requiring exact model name spelling | Staff type "jetsetter" and get no result because data says "Jetsetter LX" | Implement fuzzy matching with confirmation: "Did you mean Jetsetter LX?" -- but NEVER assume the match silently |
| No indication of data source or confidence | Staff cannot verify the answer or know how much to trust it | Include source reference: "Source: Sundance 2026 880 Series Spec Sheet, Page 4" |
| Overly chatty responses for simple lookups | A technician asking "What filter does a Cameo use?" does not want three paragraphs | Match response length to query type. Simple spec lookup = concise answer. Complex compatibility question = more detail. |
| Not handling multi-part answers | "What are the jets in a Cameo?" has multiple jet types across multiple positions | Present structured lists/tables for multi-value responses, not run-on sentences |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **ETL Pipeline:** Extraction runs successfully -- but verify that *every* extracted field has been human-verified against the source PDF, not just spot-checked
- [ ] **Model coverage:** "All 19 models are in the data store" -- but verify all 10 spec categories are populated for each model (190 data points minimum), not just the easy ones
- [ ] **Agent accuracy:** "The agent answers correctly" -- but verify it also correctly refuses to answer when data is missing (ask about a model NOT in the dataset)
- [ ] **Multi-agent flow:** "Concierge routes to Specialist correctly" -- but verify the Validator actually catches errors (intentionally corrupt a data point and confirm the Validator flags it)
- [ ] **Deployment:** "The app is hosted and accessible" -- but verify it works on the client's network/browser, not just your development environment
- [ ] **Disambiguation:** "The agent handles ambiguous queries" -- but verify it asks for clarification rather than guessing (ask "What pump?" without specifying a model)
- [ ] **Error handling:** "The system handles errors" -- but verify it handles LLM API downtime, MCP server crashes, and malformed data gracefully
- [ ] **Data completeness:** "Manufacturer X data is extracted" -- but verify part numbers include all variants (pump position 1 vs position 2, with/without optional jet package)

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| LLM hallucinated part numbers shipped to client | HIGH | Audit all responses given during testing. Cross-reference every part number against data store. Implement Validator agent if missing. Rebuild trust with client through transparent error report. |
| Silent PDF extraction errors in data store | MEDIUM | Re-verify all data for affected manufacturer. Build automated consistency checks. Fix extraction pipeline for that manufacturer's format. Re-run extraction. |
| Multi-agent orchestration too complex to debug | MEDIUM | Collapse back to single agent. Re-prove accuracy. Then carefully re-introduce agent separation with full tracing. |
| Scope creep beyond 19 models / 10 categories | LOW | Revert scope document. Park all out-of-scope requests in a backlog. Refocus on proving the core 19x10 matrix works at 100% accuracy. |
| JSON schema does not fit real data | HIGH | Redesign schema based on actual data relationships. Re-extract all data. This is why schema design must happen before bulk extraction. |
| MCP tool design requires rework | MEDIUM | Redesign tool interfaces. Update agent prompts. Re-test all 190 data points. Less costly if tool interfaces are well-separated from agent logic. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| LLM hallucinating part numbers | Phase 1 (Architecture) | Test: ask about a model not in dataset. System must refuse, not guess. |
| Silent PDF extraction errors | Phase 1 (ETL + Verification) | 100% of extracted fields verified by human against source PDF |
| Multi-agent debugging complexity | Phase 2 (Agent Development) | Start single-agent, split only when core accuracy proven. Full tracing in place before splitting. |
| "Demo works" false confidence | Phase 3 (Testing) | 190-cell test matrix (19 models x 10 categories) with automated pass/fail. Adversarial test cases included. |
| Schema does not fit relational data | Phase 1 (Data Architecture) | Validate schema against 3 pilot models (one per manufacturer) before bulk extraction |
| MCP tool design leaks LLM judgment | Phase 1 (Architecture) + Phase 2 (Implementation) | All MCP tool parameters are typed/enumerated. No free-text query parameters for lookup operations. |
| POC scope creep | All phases | Scope document with explicit boundaries. Any addition requires removing something else. |
| Deployment security gaps | Phase 4 (Deployment) | Auth on all endpoints. Data not in public repo. API keys not exposed. |
| No regression testing | Phase 3 (Testing) ongoing | Automated test suite runs on every change. Every bug becomes a test case. |
| Flat JSON loses relational complexity | Phase 1 (Data Architecture) | Schema handles multi-pump models, series-level shared specs, conditional compatibility |

## Sources

- [MIT News: LLM reliability shortcoming (2025)](https://news.mit.edu/2025/shortcoming-makes-llms-less-reliable-1126)
- [Lightup: 4 out of 4 LLMs got data inconsistency wrong](https://lightup.ai/data-inconsistency-unstructured-data)
- [AWS: Choosing the right approach for AI-powered structured data retrieval](https://aws.amazon.com/blogs/machine-learning/choosing-the-right-approach-for-generative-ai-powered-structured-data-retrieval/)
- [LangChain Blog: How and when to build multi-agent systems](https://blog.langchain.com/how-and-when-to-build-multi-agent-systems/)
- [Latenode: LangGraph Multi-Agent Orchestration Guide 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [GdPicture: Table extraction challenges](https://www.gdpicture.com/blog/table-extraction-challenges/)
- [Unstract: LLMs for structured data extraction from PDFs](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/)
- [Gartner: 30% of GenAI projects abandoned after POC](https://www.gartner.com/en/newsroom/press-releases/2024-07-29-gartner-predicts-30-percent-of-generative-ai-projects-will-be-abandoned-after-proof-of-concept-by-end-of-2025)
- [CIO: 88% of AI pilots fail to reach production](https://www.cio.com/article/3850763/88-of-ai-pilots-fail-to-reach-production-but-thats-not-all-on-it.html)
- [Parseur: HITL best practices and common pitfalls](https://parseur.com/blog/hitl-best-practices)
- [FastMCP GitHub releases](https://github.com/jlowin/fastmcp/releases)
- [Ekamoira: Deploy MCP Servers to Production 2025](https://www.ekamoira.com/blog/mcp-servers-cloud-deployment-guide)
- [Appsmith: How to de-hallucinate AI agents](https://www.appsmith.com/blog/de-hallucinate-ai-agents)
- [AI21: RAG for structured data](https://www.ai21.com/knowledge/rag-for-structured-data/)
- [Airbyte: 5 critical ETL pipeline design pitfalls](https://airbyte.com/data-engineering-resources/etl-pipeline-pitfalls-to-avoid)

---
*Pitfalls research for: Dex -- AI-powered spa parts technical knowledge assistant*
*Researched: 2026-02-14*
