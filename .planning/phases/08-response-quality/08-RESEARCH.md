# Phase 8: Response Quality - Research

**Researched:** 2026-02-16
**Domain:** LLM prompt engineering for structured output, source attribution, cross-reference data lookup
**Confidence:** HIGH

## Summary

Phase 8 enhances the Specialist agent's response format to satisfy three requirements: source attribution (RESP-01), cross-reference information (RESP-04), and clean scannable formatting (RESP-05). The existing system already has all the data infrastructure needed -- `source_documents` arrays are returned by `get_spec_category`, `PartReference.fits_models` exists in the schema, and the Specialist prompt already has basic formatting instructions.

The implementation is primarily **prompt engineering + MCP tool enhancements + validator expansion**. No new libraries are needed. The approach is: (1) add a new `find_cross_references` MCP tool that computes which other models share a given component, (2) rewrite the Specialist prompt's RESPONSE FORMAT section with explicit structured output templates, and (3) extend the deterministic validator to check for source attribution and formatting compliance.

**Primary recommendation:** This is a prompt-and-tool phase, not a library phase. The entire implementation lives in 4 files: `prompts.py` (prompt rewrite), `server.py` (new MCP tool), `data_store.py` (cross-reference lookup), and `validator.py` (new checks). Keep it simple.

## Standard Stack

No new libraries needed. Phase 8 uses the existing stack exclusively.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | current | Agent orchestration | Already in use since Phase 6 |
| FastMCP v2 | 2.14.x | MCP tool definitions | Already in use since Phase 5 |
| Gemini 2.5 Flash | current | LLM for Specialist agent | Already configured in agent/config.py |
| Pydantic | v2 | Data validation | Already in use for schema |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.x | Testing | Validator and MCP tool tests |
| httpx | current | API testing | Integration tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Prompt-based formatting | LangChain structured output | Overkill -- we want natural language with structure, not JSON output |
| New cross-ref MCP tool | Prompt instruction to call get_spec_category multiple times | Too many LLM calls, slow, unreliable |
| Regex validator checks | Pydantic output parsing | Validator is deterministic Python, not LLM output -- regex is simpler and correct |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### What Changes (4 files only)

```
backend/src/
  agent/
    prompts.py       # MODIFY: Rewrite SPECIALIST_PROMPT response format section
    validator.py     # MODIFY: Add source attribution + formatting checks
  mcp/
    server.py        # MODIFY: Add find_cross_references tool
    data_store.py    # MODIFY: Add cross-reference lookup function
```

### Pattern 1: Prompt-Driven Response Formatting

**What:** The Specialist prompt defines an explicit response template with sections for the answer, source attribution, and cross-references. The LLM follows the template naturally.

**When to use:** When you want structured but natural-language output from an LLM (not JSON).

**Why this works:** Gemini 2.5 Flash excels at following structured markdown templates in system prompts. The key is to provide explicit section headers, ordering rules, and examples. Direct and specific prompts work better than vague instructions for Flash models.

**Template approach for SPECIALIST_PROMPT:**
```
## RESPONSE FORMAT

Structure every response as follows:

### 1. Direct Answer
- Lead with the specific answer (part number, spec value, measurement)
- Use **bold** for part numbers and key values
- Present specs as a bulleted list, NOT prose paragraphs

### 2. Source Attribution
- End every response with a source line
- Format: "Source: [document_name], page [page_number]" for PDFs
- Format: "Source: [url]" for websites
- Use the source_documents field from tool responses

### 3. Cross-References (when applicable)
- If a component is shared across models, mention it
- Format: "This [component] is also used in: [Model1], [Model2]"
- Only include when find_cross_references returns other models

### Example Response:
The Sundance Aspen uses two **1.1 HP** jet pumps:
- Pump 1: 1.1 HP continuous, 1-speed, 56 Frame, 11A max
- Pump 2: 1.1 HP continuous, 1-speed, 56 Frame, 11A max
- Diverter valves: 2

This pump configuration is also used in: Altamar, Cameo, Optima

Source: 880-series-2026.pdf, page 22
```

### Pattern 2: Cross-Reference MCP Tool

**What:** A new `find_cross_references` MCP tool that accepts a manufacturer, model name, and category, then scans all models in the same manufacturer to find which ones share the same component configuration.

**When to use:** After the Specialist retrieves spec data via `get_spec_category`, it calls `find_cross_references` to find models with matching specs.

**How it works:**
1. Load the queried model's category data
2. Iterate all models from the same manufacturer
3. Compare category data (excluding part_number and shared_with_series fields)
4. Return list of model names that share the same component

**Data analysis confirms cross-references exist across the 19 models:**
- Sundance heater (5500W): shared across ALL 7 Sundance models
- Hot Spring heater (4000W): shared across Aria, Envoy, Grandee, Vanguard
- Sundance circulation pump: shared across ALL 7 Sundance models
- Bullfrog circulation pump: shared across ALL 4 Bullfrog models
- Hot Spring cover specs: shared in pairs (Envoy+Grandee, Jetsetter+Jetsetter LX, Aria+Vanguard)
- Sundance cover: shared across 5 models (Altamar, Aspen, Cameo, Optima, Vistamar)
- Sundance topside_control: shared between Aspen and Capris
- Pump configurations: multiple models share identical HP/count configs

### Pattern 3: Enhanced Deterministic Validator

**What:** Extend `validate_response()` with new checks for source attribution and formatting quality.

**When to use:** Called by the API layer after every agent response (already wired).

**New checks to add:**
1. **Source attribution check:** Response must contain "Source:" or "source:" with a document name or URL
2. **Part number prominence check:** If tool response contained part numbers, they should appear with formatting emphasis (bold markers `**` around them)
3. **Prose density check:** Warn if response has very long lines without bullet points or line breaks (indicates paragraph-form answers instead of scannable format)

### Anti-Patterns to Avoid

- **Over-constraining the prompt:** Do NOT use LangChain `with_structured_output()` for this. We want natural language with structure, not rigid JSON. The technician audience needs readable text.
- **Multiple sequential tool calls for cross-references:** Do NOT instruct the agent to call `get_spec_category` for every other model to find matches. This would require 6-18 additional LLM+MCP calls. Instead, provide a single `find_cross_references` tool that returns the answer directly.
- **Hardcoded cross-reference tables:** Do NOT build a static lookup table of shared components. Use the data store dynamically so it stays correct as data changes.
- **LLM-based validation:** Do NOT add an LLM-powered validator step. The current deterministic validator pattern (pure Python, no API call) is correct and fast. Keep it that way.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-reference computation | Manual comparison logic per category | Generic field-comparison function that works across all 10 categories | Each category has different fields; a generic comparator using model_dump() with exclude keys handles all |
| Source document formatting | Category-specific source lookup | Use the source_documents already returned by get_spec_category | Data is already there in tool response; just instruct the prompt to use it |
| Response format enforcement | Custom output parser or post-processor | Prompt engineering + deterministic validator | Gemini follows structured prompts well; validator catches failures |

**Key insight:** The source_documents data is already returned by `get_spec_category` (line 88 of server.py). The Specialist just needs prompt instructions to include it in the response. This is a prompt gap, not a data gap.

## Common Pitfalls

### Pitfall 1: Source Documents Are Model-Level, Not Category-Level

**What goes wrong:** Each model has a single `source_documents` array at the top level, not per-category. The same PDF (e.g., "880-series-2026.pdf") contains data for multiple categories across multiple pages. The `get_spec_category` tool returns ALL source documents for the model, not just the one relevant to the queried category.

**Why it happens:** During extraction (Phase 2), source references were tracked per-extraction-call, but multiple categories were extracted from the same document. The source_documents array contains entries with different page_number values, some with section names.

**How to avoid:** The prompt should instruct the Specialist to include the document name and note that the page number is approximate. Do NOT try to match source documents to specific categories -- the data does not support that granularity reliably.

**Warning signs:** Agent citing "page 22" for a filter question when page 22 is about pumps.

### Pitfall 2: fits_models Is Empty for All 19 Models

**What goes wrong:** The `PartReference.fits_models` field exists in the schema but is empty (`[]`) for every part across all 19 JSON files. Part numbers themselves are also mostly null (460 not-available fields, 323 of which are part_numbers).

**Why it happens:** Manufacturer PDFs and websites do not provide cross-model compatibility data for individual parts. This data would require a separate parts catalog or retailer database.

**How to avoid:** Cross-references must be computed dynamically by comparing component specs across models (same heater wattage, same pump config, etc.), NOT by reading `fits_models` from the data. The `find_cross_references` tool must implement comparison logic.

**Warning signs:** Agent says "no cross-reference data available" for every query because it only checks fits_models.

### Pitfall 3: LLM Ignoring or Truncating Source Attribution

**What goes wrong:** Despite prompt instructions, Gemini may omit the "Source:" line, especially for short answers or when it deems the attribution unnecessary.

**Why it happens:** LLMs optimize for conciseness and may skip parts of the template they consider redundant. This is especially true with Gemini Flash, which is optimized for speed.

**How to avoid:** (1) Place the source attribution instruction as a CRITICAL RULE (high priority in prompt), not just in the format section. (2) Include it in the example response. (3) Add a validator check that warns when "Source:" is missing. (4) Consider adding "ALWAYS include a Source: line" as a separate numbered rule.

**Warning signs:** Validator catches "No source attribution" warnings in > 30% of responses.

### Pitfall 4: Cross-Reference Tool Returning Too Many Results

**What goes wrong:** For categories like heater (shared across all 7 Sundance models) or circulation_pump (shared across entire manufacturer), the cross-reference list is long and clutters the response.

**Why it happens:** Many components are series-level shared specs -- all models in a series share the same heater, same circulation pump, etc.

**How to avoid:** When the cross-reference returns all models in a manufacturer, the prompt should instruct the agent to say "This is shared across all [Series] models" instead of listing every name. The tool should return a `shared_count` and `total_in_manufacturer` so the agent can make this judgment.

**Warning signs:** Response says "also used in: Altamar, Aspen, Cameo, Capris, Marin, Optima" for every Sundance query.

### Pitfall 5: max_output_tokens=1024 May Truncate Longer Responses

**What goes wrong:** The current Gemini config sets `max_output_tokens=1024`. Adding source attribution and cross-references to every response increases output length. Complex queries (e.g., jet pump details with 3+ pumps) may get truncated.

**Why it happens:** The token limit was set in Phase 6 for concise single-category answers. Phase 8 adds more content to each response.

**How to avoid:** Increase `max_output_tokens` to 2048 in `agent/config.py`. This provides headroom for attribution + cross-refs without being wasteful. Monitor actual response lengths to verify.

## Code Examples

### Cross-Reference Lookup Function (data_store.py)

```python
def find_cross_references(
    manufacturer: str,
    model_name: str,
    category: str,
    exclude_keys: tuple[str, ...] = ("part_number", "shared_with_series", "model_name"),
) -> list[str]:
    """Find other models with the same component specs in a given category.

    Compares the category data (via model_dump) of the target model against
    all other models from the same manufacturer, excluding specified keys
    (part_number, shared_with_series, model_name) from the comparison.

    Returns a list of model names that share the same component configuration.
    """
    store = get_store()
    target = get_model(manufacturer, model_name)
    if target is None:
        return []

    target_data = getattr(target, category, None)
    if target_data is None:
        return []

    # Create comparison signature from target
    target_dump = target_data.model_dump()
    for key in exclude_keys:
        target_dump.pop(key, None)

    matches = []
    for (mfr, _), other_model in store.items():
        if mfr != manufacturer.lower():
            continue
        if other_model.model_name.lower() == model_name.lower():
            continue

        other_data = getattr(other_model, category, None)
        if other_data is None:
            continue

        other_dump = other_data.model_dump()
        for key in exclude_keys:
            other_dump.pop(key, None)

        if target_dump == other_dump:
            matches.append(other_model.model_name)

    return sorted(matches)
```

### Cross-Reference MCP Tool (server.py)

```python
@mcp.tool
def find_cross_references(
    manufacturer: Manufacturer,
    model_name: Annotated[ModelName, Field(description="Spa model name")],
    category: Annotated[SpecCategory, Field(description="Spec category to cross-reference")],
) -> dict:
    """Find other models that share the same component specs for a given category.

    Compares the target model's category data against all other models from
    the same manufacturer. Useful for answering "What other models use this
    same pump/heater/filter?" Returns the list of matching model names and
    the total count of models from that manufacturer for context.
    """
    from backend.src.mcp.data_store import find_cross_references as _find_xref

    matches = _find_xref(manufacturer.value, model_name, category.value)

    # Count total models for this manufacturer (for "shared across all" context)
    store = get_store()
    total = sum(1 for (mfr, _) in store if mfr == manufacturer.value)

    return {
        "success": True,
        "manufacturer": manufacturer.value,
        "model_name": model_name,
        "category": category.value,
        "matching_models": matches,
        "match_count": len(matches),
        "total_manufacturer_models": total,
    }
```

### Enhanced Validator Checks (validator.py)

```python
def validate_response(state: dict) -> list[str]:
    warnings: list[str] = []
    messages = state.get("messages", [])
    # ... existing checks ...

    if ai_messages:
        last_ai = ai_messages[-1]
        content = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content)

        # NEW: Check for source attribution
        if tool_messages and not re.search(r"[Ss]ource[s]?:", content):
            warnings.append("No source attribution in response")

        # NEW: Check for scannable format (detect prose-heavy responses)
        lines = content.strip().split("\n")
        if len(content) > 200 and len(lines) < 3:
            warnings.append("Response may not be scannable (few line breaks for length)")

    return warnings
```

### Specialist Prompt Response Format Section

```python
SPECIALIST_PROMPT_RESPONSE_FORMAT = """
## RESPONSE FORMAT

CRITICAL: Every response MUST follow this structure. Never skip the Source line.

### Structure
1. **Direct Answer** -- Lead with the specific value (part number, HP, wattage, count)
2. **Details** -- Bulleted list of specs, NOT prose paragraphs
3. **Cross-References** -- If find_cross_references returns matches, include them
4. **Source** -- ALWAYS end with a Source: line from source_documents

### Formatting Rules
- Use **bold** for part numbers and key numeric values
- Use bulleted lists for multiple specs, never paragraph form
- Keep responses concise -- 3-8 lines typical, never more than 15
- When a component is shared across ALL models in a series, say "shared across all [Series] models"
- When shared across some models, list them: "Also used in: [Model1], [Model2]"

### Source Attribution
- ALWAYS include at the end: "Source: [document_name], page [page_number]"
- For website sources: "Source: [url]"
- Use the source_documents from the tool response
- If multiple sources, cite the most specific one (the one with a section name or relevant page)

### Example
The Sundance Aspen uses two **1.1 HP** jet pumps:
- Pump 1: **1.1 HP** continuous, 1-speed, 56 Frame, 11A max
- Pump 2: **1.1 HP** continuous, 1-speed, 56 Frame, 11A max
- Diverter valves: 2

This pump configuration is also used in: Altamar, Cameo, Optima

Source: 880-series-2026.pdf, page 22
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Basic "be concise" prompt instructions | Explicit response templates with section ordering | 2025-2026 | Gemini Flash follows structured templates reliably |
| Hardcoded cross-reference lookup tables | Dynamic field comparison across data store | N/A (new for this project) | Stays correct as data changes, no maintenance burden |
| LLM-based output validation | Deterministic regex/string checks in Python | Established pattern | Fast, reliable, no API cost, no non-determinism |
| Per-category source tracking | Model-level source_documents with page/section | Phase 2 (current) | Good enough for attribution, not per-field granular |

**Limitations to accept:**
- Source attribution is model-level, not per-field. The "page 22" citation may not correspond exactly to the queried category. This is acceptable for the POC -- technicians care about the document name, not exact page number.
- Cross-references are based on spec matching, not part number matching (since part numbers are mostly null). This means "same specs" not "same part."
- fits_models field remains empty. Dynamic comparison is the only path for cross-references.

## Open Questions

1. **Should cross-references be automatic or on-demand?**
   - What we know: The Specialist could call `find_cross_references` on every query, or only when the user asks "what other models use this?"
   - What's unclear: Will automatic cross-references clutter responses unnecessarily?
   - Recommendation: Make it automatic but instructed to keep it brief. "Also used in: X, Y" is one line and adds value. The prompt should handle the "shared across all" case gracefully.

2. **How specific should source attribution be?**
   - What we know: source_documents has document_name, page_number, and section for some entries. Multiple source docs per model (5-7 typical).
   - What's unclear: Should the agent cite the most relevant source doc, or all of them?
   - Recommendation: Instruct the agent to cite ONE source (the most specific) per response. Multiple citations would clutter the format. The prompt should say "cite the source document with a section name if available, otherwise the one with the most relevant page number."

3. **Token limit increase from 1024 to 2048**
   - What we know: Current limit is 1024. Adding attribution + cross-refs adds ~50-100 tokens per response.
   - What's unclear: Whether 1024 is already causing truncation on complex queries.
   - Recommendation: Increase to 2048. The cost difference is negligible with Flash pricing, and it prevents silent truncation.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `backend/src/agent/prompts.py` -- current SPECIALIST_PROMPT lacks response format template
- Codebase analysis: `backend/src/mcp/server.py` line 88 -- `source_documents` already returned by `get_spec_category`
- Codebase analysis: `backend/src/schema/parts.py` -- `PartReference.fits_models` exists but is empty across all 19 models
- Codebase analysis: `backend/src/agent/validator.py` -- current validator has 3 checks, extensible pattern
- Data analysis: All 19 JSON files analyzed for shared components -- significant cross-reference potential confirmed
- Codebase analysis: `backend/src/agent/config.py` line 36 -- `max_output_tokens=1024` may need increase

### Secondary (MEDIUM confidence)
- [Google AI Prompting Strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies) -- Gemini responds well to structured templates with clear delimiters
- [LangGraph Structured Output](https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output/) -- Confirms prompt-based formatting is standard for natural language responses
- [Markdown for Prompt Engineering](https://tenacity.io/snippets/supercharge-ai-prompts-with-markdown-for-better-results/) -- Markdown headings and lists in prompts improve output structure

### Tertiary (LOW confidence)
- None -- all findings verified against codebase or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing code analyzed
- Architecture: HIGH -- 4-file change verified against codebase, patterns proven in prior phases
- Pitfalls: HIGH -- data analysis confirmed fits_models empty, source_documents model-level, shared components computed
- Cross-reference logic: HIGH -- dynamic comparison tested against all 19 models with confirmed matches

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable -- no external dependencies changing)
