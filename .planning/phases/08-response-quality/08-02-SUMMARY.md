---
phase: 08-response-quality
plan: 02
subsystem: agent-response-quality
tags: [prompt-engineering, validator, source-attribution, response-format]
depends_on:
  requires: [07-01, 07-02, 08-01]
  provides: [specialist-response-template, source-attribution-validator, scannable-format-validator]
  affects: [08-03]
tech-stack:
  added: []
  patterns: [structured-response-template, deterministic-validation-pipeline]
key-files:
  created: []
  modified:
    - backend/src/agent/prompts.py
    - backend/src/agent/validator.py
    - backend/src/agent/config.py
    - backend/tests/test_agent.py
decisions:
  - id: "08-02-01"
    decision: "Response format uses 4-section structure: Direct Answer, Details, Cross-References, Source"
    rationale: "Gemini 2.5 Flash follows explicit templates reliably; 4 sections cover all RESP requirements"
  - id: "08-02-02"
    decision: "Source attribution regex uses [Ss]ources?: to match Source: and Sources: variants"
    rationale: "LLM may pluralize; case-insensitive first letter covers common patterns"
  - id: "08-02-03"
    decision: "Prose density threshold: >200 chars with <3 lines triggers warning"
    rationale: "200 chars is roughly 2 sentences -- enough to expect line breaks for readability"
  - id: "08-02-04"
    decision: "max_output_tokens bumped from 1024 to 2048"
    rationale: "Attribution + cross-references add ~50-100 tokens; 2048 prevents truncation at negligible cost with Flash"
metrics:
  duration: "7 min"
  completed: "2026-02-16"
---

# Phase 8 Plan 2: Response Format and Validator Expansion Summary

Enhanced Specialist prompt with explicit 4-section response template (Direct Answer / Details / Cross-References / Source), added 2 new validator checks (source attribution + scannable format), and bumped max_output_tokens to 2048.

## What Was Done

### Task 1: Rewrite SPECIALIST_PROMPT response format and bump max_output_tokens
- Added rules 6 (source attribution is non-negotiable) and 7 (use find_cross_references tool) to CRITICAL RULES
- Replaced the 4-line RESPONSE FORMAT section with a full structured template including:
  - Structure section: Direct Answer, Details, Cross-References, Source
  - Formatting Rules: bold for part numbers, bulleted lists, 3-15 line range
  - Source Attribution: explicit instructions for PDF and website sources
  - Example response showing all sections in use
- Bumped max_output_tokens from 1024 to 2048 in config.py
- Commit: `85d6f0e`

### Task 2: Expand validator and update tests
- Added check 4: source attribution -- warns when tool messages present but response lacks "Source:" line
- Added check 5: prose density -- warns when response >200 chars has <3 lines (wall of text)
- Updated existing `test_validate_response_clean` to include Source: line so it passes new checks
- Added 8 new tests covering all new validator checks, prompt content assertions, and config verification
- Total test_agent.py: 70 tests (was 62, net +8)
- Commit: `62c8d5e`

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| 08-02-01 | 4-section response structure (Direct Answer / Details / Cross-References / Source) | Explicit template that Gemini 2.5 Flash follows reliably |
| 08-02-02 | Source attribution regex `[Ss]ources?:` for flexible matching | LLM may pluralize or capitalize differently |
| 08-02-03 | Prose density: >200 chars with <3 lines triggers warning | 200 chars ~2 sentences, enough to expect line breaks |
| 08-02-04 | max_output_tokens 1024 -> 2048 | Attribution + cross-refs add tokens; Flash pricing negligible |

## Test Results

```
70 passed in 12.44s (test_agent.py)
309 passed, 18 deselected in 19.91s (full non-integration suite)
```

No regressions. All 8 new tests pass.

## Next Phase Readiness

Plan 08-03 (integration testing) can proceed. The prompt, validator, and config changes are committed and tested at unit level. Integration tests will verify that Gemini actually produces responses matching the new template format.
