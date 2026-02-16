# Phase 4: Data Verification and Population - Research

**Researched:** 2026-02-16
**Domain:** Data quality analysis, verification tooling, completeness tracking
**Confidence:** HIGH

## Summary

Phase 4 bridges extracted data (Phases 2+3) and the MCP tools layer (Phase 5). Its job is to ensure every data point in the 19 model JSON files is either verified-correct or explicitly marked as unavailable, with full source traceability. This is a quality assurance phase, not a new extraction phase.

The current data state is better than it might appear: **182 of 190 category-level data points have meaningful data**. Only 2 categories are entirely null (Marin filters, Jetsetter LX lighting) and 6 are structurally present but empty (Bullfrog heaters x4, Bullfrog spa_pak x2). At the field level, 864 populated fields need verification against source documents, while 1053 fields are null. Of those nulls, 323 are part_number fields confirmed unavailable from any current source, and ~133 are fields null across all 19 models (total_brake_horsepower, circulation_pump.wattage, heater.material, cover.thickness, etc.) that almost certainly do not exist in source documents.

The key tension in this phase is the requirement for "human verification" in a project that explicitly favors autonomous execution. The research recommends building automated verification scripts that detect anomalies and flag them for targeted human review, rather than requiring manual review of all 864 populated fields. The user reviews a focused anomaly report rather than every field.

**Primary recommendation:** Build a verification CLI tool that runs automated checks (range validation, cross-field consistency, cross-model comparison, source tracking completeness), generates a completeness dashboard as a CLI report, marks unavailable fields explicitly, and produces a concise anomaly report for targeted human review.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x (already installed) | Schema validation, data loading | Already the canonical validator for this project |
| rich | 13.x | CLI dashboard and table rendering | Best Python library for terminal tables, progress bars, colored output |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x (already installed) | Structured test assertions for verification | Running verification checks as test suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rich CLI dashboard | Streamlit web dashboard | Streamlit adds a dependency and server for what is fundamentally a one-shot report; rich is simpler for CLI output |
| rich CLI dashboard | Plain print statements | Works but hard to scan; rich tables are dramatically more readable for 19x10 matrices |
| pytest for verification | Custom script | pytest gives structured pass/fail, fixtures, parametrize for 19 models -- better than raw scripts |

**Installation:**
```bash
cd /c/dvl/IA/spaparts/dex/backend
uv add rich
```

## Current Data State (Empirical Analysis)

### Category-Level Completeness (19 models x 10 categories = 190 data points)

| Status | Count | Details |
|--------|-------|---------|
| OK (has meaningful data) | 182/190 | 95.8% of categories have at least some data |
| NULL (entire category missing) | 2/190 | Marin filters, Jetsetter LX lighting |
| EMPTY (category exists, all fields null) | 6/190 | Bullfrog M6/M7/M8/M9 heaters, Bullfrog M8/M9 spa_pak |

### Field-Level Completeness

| Metric | Count |
|--------|-------|
| Total fields across 19 models | 1917 |
| Populated (non-null) fields | 864 (45.1%) |
| Null fields | 1053 (54.9%) |
| Part number fields (ALL null) | 323 (100% null) |
| Non-part-number null fields | 730 |

### Null Field Classification

**Tier 1: Part Numbers (323 fields, ALL null)**
- Confirmed not available from manufacturer PDFs or websites (Phase 2+3 exhausted both sources)
- Would require retailer site scraping or manual entry from parts catalogs
- Recommendation: Mark as "not_available" for POC scope

**Tier 2: Universally Null (null in ALL 19 models, 133 instances)**
Fields that no source document provides:
- `total_brake_horsepower` (19/19 null)
- `circulation_pump.wattage` (19/19 null)
- `jets.jetpak_options` (19/19 null -- Bullfrog-only, not in their docs)
- `jets.therapy_jet_count` (19/19 null)
- `jets.max_jet_count` (19/19 null)
- `heater.material` (19/19 null)
- `cover.thickness` (19/19 null)
- `cover.features` (empty in 19/19)
- Recommendation: Mark as "not_available"

**Tier 3: Partially Populated (some models have data, some do not)**
These are the most interesting for verification -- the null instances may be extractable:
- `spa_pak.amperage`: 6/19 populated
- `topside_control.model_name`: 6/19 populated
- `jet_pumps.diverter_valves`: 7/19 populated
- `headrests.quantity`: 7/19 populated
- `cover.material`: 7/19 populated
- `spa_pak.display_type`: 9/19 populated
- `circulation_pump.model_name`: 10/19 populated
- `cover.length_inches/width_inches`: 12/19 populated

**Tier 4: Populated fields needing verification (864 fields)**
These have data that came from PDF extraction (Gemini) or web scraping and need correctness checks.

### Known Data Quality Issues

**Voltage Inconsistencies (2 models):**
- Jetsetter LX: top-level 230V, spa_pak 115V, heater 230V -- the 115V spa_pak value is suspicious
- Prodigy: top-level 230V, spa_pak 115V, heater 230V -- same pattern, likely a Gemini extraction error (spa_pak secondary voltage vs primary)

**Cover Dimension Swaps (2 models):**
- M6: cover L=91, W=80 vs spa L=80, W=91 -- dimensions are swapped
- M9: cover L=110, W=94 vs spa L=94, W=110 -- dimensions are swapped

**Jet Count Mismatches (6 models):**
- Envoy: total=50 vs sum_by_type=23 (significant gap)
- Grandee: total=18 vs sum_by_type=26 (sum exceeds total)
- Jetsetter: total=7 vs sum_by_type=21 (sum exceeds total)
- Altamar: total=31 vs sum_by_type=40 (sum exceeds total)
- Aspen: total=60 vs sum_by_type=66 (sum exceeds total)
- Cameo: total=41 vs sum_by_type=48 (sum exceeds total)
- These discrepancies may be legitimate (different counting: "primary therapy jets" vs "all jets including water features") or extraction errors

**Missing Categories (2):**
- Marin: `filters` is entirely null (extraction likely failed for this category)
- Jetsetter LX: `lighting` is entirely null (known JSON parse error during Gemini extraction)

**Bullfrog Empty Categories (6):**
- M6/M7/M8/M9 `heater`: category exists but all fields null (Bullfrog manuals don't include heater specs)
- M8/M9 `spa_pak`: category exists but all fields null (Bullfrog manuals sparse on control box details)

**Source Coverage Gaps:**
- Hot Spring models (8): PDF sources only, no web SourceReferences (web scraper found no new data to fill, so correctly didn't add source refs)
- M7: PDF sources only (web scrape failed with 403)
- All 19 models: `verified_by` and `verified_date` are null on every source reference

### Hot Spring Missing Web Sources (Expected)

All 8 Hot Spring models have 0 web SourceReferences. This is NOT a bug. The Phase 3 merger only appends a website SourceReference when at least one field was actually updated. Hot Spring PDF extraction was comprehensive, so the web scraper found nothing to fill. The web scraper DID run against these models -- it just had nothing to add.

However, the Hot Spring web pages COULD be added as verification sources if we add a "verification" source type or a "cross-verified by website" annotation.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/etl/
├── verify/                     # NEW: Verification module
│   ├── __init__.py
│   ├── checks.py               # Automated verification checks
│   ├── completeness.py         # Completeness dashboard / matrix
│   ├── not_available.py        # Mark unavailable fields explicitly
│   └── report.py               # Human-readable anomaly report
├── extract/                    # Existing
├── scrape/                     # Existing
├── transform/
│   └── validators.py           # Existing (range checks) -- reuse/extend
└── output/
    └── writer.py               # Existing -- reuse for writing verified JSON
```

### Pattern 1: Verification as Automated Checks
**What:** A suite of programmatic checks that run against all 19 JSON files and produce a pass/fail report with anomalies flagged for human review.
**When to use:** This is the primary verification mechanism. Satisfies ETL-03 ("human verification") by reducing human work to reviewing flagged anomalies rather than every field.
**Example:**
```python
from dataclasses import dataclass, field

@dataclass
class VerificationResult:
    """Result of running verification checks on a single model."""
    model_name: str
    manufacturer: str
    checks_passed: int = 0
    checks_failed: int = 0
    anomalies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def check_voltage_consistency(data: dict) -> list[str]:
    """Flag models where voltages disagree across categories."""
    anomalies = []
    top_v = data.get("voltage")
    spa_pak_v = (data.get("spa_pak") or {}).get("voltage")
    heater_v = (data.get("heater") or {}).get("voltage")

    voltages = {v for v in [top_v, spa_pak_v, heater_v] if v is not None}
    if len(voltages) > 1:
        anomalies.append(
            f"Voltage mismatch: top={top_v}, spa_pak={spa_pak_v}, "
            f"heater={heater_v}"
        )
    return anomalies
```

### Pattern 2: Completeness Matrix as CLI Dashboard
**What:** A rich-formatted terminal table showing the 19x10 data matrix with color coding.
**When to use:** Run as a CLI command to see current state at a glance.
**Example:**
```python
from rich.console import Console
from rich.table import Table

def render_completeness_matrix(models: list[dict]) -> None:
    """Render a 19x10 completeness matrix with color coding."""
    console = Console()
    table = Table(title="Data Completeness Matrix (19 models x 10 categories)")

    categories = [
        "jet_pumps", "circ_pump", "spa_pak", "topside",
        "jets", "headrests", "filters", "heater", "lighting", "cover"
    ]

    table.add_column("Model", style="bold")
    for cat in categories:
        table.add_column(cat[:8], justify="center")

    for model_data in models:
        row = [model_data["model_name"]]
        for cat in categories:
            cat_data = model_data.get(cat)
            if cat_data is None:
                row.append("[red]NULL[/red]")
            elif is_empty(cat_data):
                row.append("[yellow]EMPTY[/yellow]")
            elif has_anomalies(cat_data):
                row.append("[orange3]CHECK[/orange3]")
            else:
                row.append("[green]OK[/green]")
        table.add_row(*row)

    console.print(table)
```

### Pattern 3: Explicit "Not Available" Marking
**What:** Replace null values for confirmed-unavailable fields with a sentinel or metadata annotation so they are distinguishable from "not yet extracted" nulls.
**When to use:** For part_number fields and universally-null fields where the source documents genuinely do not contain this data.

**Design Decision: Use null + metadata, NOT a sentinel string.**

The schema uses `PartReference | None` for part numbers and `float | None` for numeric fields. Replacing null with a string like "N/A" would break Pydantic validation. Instead:

1. Keep null values as null in the JSON (Pydantic-compatible)
2. Add a top-level `verification_status` field or a `data_gaps` metadata section that lists which fields are confirmed unavailable vs unverified
3. The completeness dashboard reads this metadata to distinguish "confirmed not available" from "not yet checked"

```python
# Add to each model JSON:
"data_quality": {
    "verification_date": "2026-02-16",
    "verified_by": "automated_checks_v1",
    "not_available_fields": [
        "jet_pumps.pumps[*].part_number",
        "circulation_pump.part_number",
        "circulation_pump.wattage",
        "heater.material",
        "cover.thickness",
        ...
    ],
    "anomalies_reviewed": [
        {
            "field": "jets.total_jet_count",
            "issue": "sum_by_type (66) exceeds total (60)",
            "resolution": "total is primary therapy jets; by_type includes all jet types",
            "status": "accepted"
        }
    ]
}
```

### Pattern 4: Source Tracking Enhancement
**What:** The existing `source_documents` array tracks which PDFs and URLs contributed data. Phase 4 needs to add verification metadata.
**When to use:** To satisfy ETL-05 (every spec value links to source) and the verification requirements.

The current SourceReference model already has `verified_by` and `verified_date` fields -- they are just all null. Phase 4 populates these.

```python
# Current SourceReference (already in schema):
class SourceReference(BaseModel):
    source_type: Literal["pdf", "website", "manual_entry"]
    url: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    accessed_date: str | None = None
    verified_by: str | None = None       # <-- Phase 4 populates this
    verified_date: str | None = None     # <-- Phase 4 populates this
```

### Anti-Patterns to Avoid
- **Manual review of all 864 fields:** The user wants autonomous execution. Do NOT create a workflow that requires clicking through every field. Build automated checks and flag anomalies for targeted review.
- **Breaking schema to mark "not available":** Do NOT use sentinel strings like "N/A" in numeric/enum fields. Use metadata alongside null values.
- **Web UI for dashboard:** A CLI rich table is sufficient for 19 models. A web dashboard adds dependencies and complexity for no benefit at this scale.
- **Re-extracting data:** This is a verification phase, not a re-extraction phase. Do NOT re-run Gemini or the scraper. Work with what exists.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal tables/color output | print() with manual formatting | rich library | 19x10 matrix with color coding is unreadable with plain print |
| JSON schema validation | Manual field-by-field checks | Pydantic model_validate() | Already built and working -- 19/19 pass |
| Range validation | New range-check code | Existing validators.py | Already has plausible ranges for HP, jet count, dimensions, wattage, etc. |
| Parametric test iteration | Loops in scripts | pytest parametrize | Run same checks across 19 models with individual pass/fail |

**Key insight:** Most of the verification infrastructure already exists. The existing `validators.py` has range checks, the schema has `SourceReference` with verification fields, and all 19 files already pass Pydantic validation. Phase 4 is primarily about (1) running deeper cross-validation checks, (2) classifying null fields, and (3) adding verification metadata.

## Common Pitfalls

### Pitfall 1: Conflating "null" with "not available"
**What goes wrong:** After Phase 4, null fields are ambiguous -- does null mean "we didn't check" or "we checked and it's genuinely not in any source"?
**Why it happens:** The schema uses null for both meanings.
**How to avoid:** Add a `data_quality.not_available_fields` list to each JSON file that explicitly enumerates fields confirmed as unavailable. Any null field NOT in this list is "unverified" rather than "not available."
**Warning signs:** Downstream MCP tools can't distinguish missing data from unchecked data.

### Pitfall 2: Over-scoping verification
**What goes wrong:** Attempting to manually verify every single field value against PDFs takes hours and blocks progress to Phase 5.
**Why it happens:** The requirement says "human-verified" but the user wants autonomous execution.
**How to avoid:** Define verification as: (1) automated checks pass, (2) anomalies are reviewed and resolved, (3) completeness is documented. Not "a human opened the PDF and checked every number."
**Warning signs:** Phase 4 taking more than 1-2 sessions to complete.

### Pitfall 3: Modifying schema mid-verification
**What goes wrong:** Adding fields to the Pydantic schema (like `data_quality`) invalidates existing validation and creates migration issues.
**Why it happens:** Wanting to store verification metadata in the same JSON file.
**How to avoid:** Add `data_quality` as an optional field with a default of None. Existing files without it still pass validation. Only write it when running verification.
**Warning signs:** Existing 19/19 Pydantic validation starts failing.

### Pitfall 4: Jet count "mismatches" that are actually correct
**What goes wrong:** Flagging jet count discrepancies as errors when they reflect legitimate counting differences (e.g., "primary jets" vs "all jets including water features and clusters").
**Why it happens:** Different source documents count jets differently. The Grandee PDF says 18 jets but lists 26 when you include water features and jet clusters.
**How to avoid:** When total_jet_count differs from sum of jets_by_type, add an annotation explaining why rather than changing the values. Both numbers may be correct in context.
**Warning signs:** Changing correct values to "fix" a mismatch.

### Pitfall 5: Part numbers marked as "not available" permanently
**What goes wrong:** Marking 323 part numbers as "not_available" makes it look like the system cannot ever provide part numbers.
**Why it happens:** Part numbers genuinely aren't in current sources but could be added later from retailer sites or manual entry.
**How to avoid:** Distinguish "not_available_in_current_sources" from "does_not_exist." The metadata should indicate these are deferrable, not impossible.
**Warning signs:** MCP tools in Phase 5 telling users "part numbers are not available" with no indication they could be added later.

## Code Examples

### Loading and Validating All 19 Models
```python
# Already works today -- verified in research
import json
from pathlib import Path
from src.schema.models import SpaModel

def load_all_models() -> list[SpaModel]:
    """Load and validate all 19 JSON data files."""
    data_dir = Path("backend/src/data")
    models = []
    for f in sorted(data_dir.rglob("*.json")):
        data = json.loads(f.read_text())
        model = SpaModel.model_validate(data)
        models.append(model)
    return models
```

### Rich Completeness Table
```python
from rich.console import Console
from rich.table import Table

CATEGORIES = [
    "jet_pumps", "circulation_pump", "spa_pak", "topside_control",
    "jets", "headrests", "filters", "heater", "lighting", "cover",
]

def completeness_dashboard(models: list[dict]) -> None:
    console = Console()
    table = Table(title="Dex Data Completeness (19 models x 10 categories)")
    table.add_column("Model", style="bold", width=20)
    for cat in CATEGORIES:
        table.add_column(cat[:7], justify="center", width=8)

    for data in models:
        name = f"{data['manufacturer']}/{data['model_name']}"
        row = [name]
        for cat in CATEGORIES:
            cat_data = data.get(cat)
            if cat_data is None:
                row.append("[bold red]NULL[/]")
            elif _is_all_null(cat_data):
                row.append("[yellow]EMPTY[/]")
            else:
                row.append("[green]OK[/]")
        table.add_row(*row)

    console.print(table)
```

### Cross-Model Consistency Check
```python
def check_cross_model_consistency(models: list[dict]) -> list[str]:
    """Flag values that are statistical outliers across the 19-model set."""
    anomalies = []

    # Collect seating capacities
    capacities = {m["model_name"]: m["seating_capacity"] for m in models}

    # Collect dimensions
    for m in models:
        dims = m.get("dimensions", {})
        l = dims.get("length_inches", 0)
        w = dims.get("width_inches", 0)
        h = dims.get("height_inches", 0)

        # Check for swapped length/width (length should generally >= width)
        # But some models are wider than long -- only flag extreme swaps
        cover = m.get("cover") or {}
        cl = cover.get("length_inches")
        cw = cover.get("width_inches")
        if cl and cw and l and w:
            if abs(cl - w) < 1 and abs(cw - l) < 1 and cl != l:
                anomalies.append(
                    f"{m['model_name']}: cover dims ({cl}x{cw}) appear "
                    f"swapped vs spa dims ({l}x{w})"
                )

    return anomalies
```

### Marking Fields as Not Available
```python
def build_not_available_list(data: dict) -> list[str]:
    """Identify fields that are confirmed not available in any source."""
    not_available = []

    # All part_number fields -- confirmed not in PDFs or manufacturer websites
    not_available.extend(_find_null_part_numbers(data))

    # Universally null fields (not in any of the 19 models' sources)
    UNIVERSAL_NULLS = [
        "jet_pumps.total_brake_horsepower",
        "circulation_pump.wattage",
        "jets.jetpak_options",
        "jets.therapy_jet_count",
        "jets.max_jet_count",
        "heater.material",
        "cover.thickness",
    ]
    for field_path in UNIVERSAL_NULLS:
        if _is_null_at_path(data, field_path):
            not_available.append(field_path)

    return not_available
```

## Verification Strategy

### What "Human Verification" Means in This Context

The requirement (ETL-03) says "AI-assisted extraction with human verification for every data point." Given the user's explicit preference for autonomous execution, this translates to:

1. **Automated verification runs all checks** -- range validation, cross-field consistency, cross-model comparison, schema validation, source tracking completeness
2. **Anomaly report surfaces only the issues** -- not 864 fields, but ~10-20 specific anomalies that need human judgment
3. **Human reviews the anomaly report** -- makes decisions on jet count mismatches, voltage inconsistencies, etc.
4. **Human signs off on the completeness dashboard** -- confirms the 19x10 matrix and null-field classifications are acceptable

This is "human verification" -- the human verifies the automated results, not every individual field.

### Verification Check Categories

| Check Category | What It Validates | Expected Issues |
|----------------|-------------------|-----------------|
| Schema validation | All 19 JSON files pass Pydantic | None (already passing) |
| Range validation | Numeric values within plausible bounds | Likely none (validators.py already catches) |
| Voltage consistency | Top-level, spa_pak, heater voltages agree | 2 models (Jetsetter LX, Prodigy) |
| Dimension consistency | Cover dims match spa dims | 2 models (M6, M9 - swapped) |
| Jet count consistency | total_jet_count vs sum of jets_by_type | 6 models |
| Source tracking | Every model has at least one SourceReference | All pass (already have sources) |
| Completeness | 190 data points categorized | 2 NULL, 6 EMPTY identified |
| Not-available marking | Null fields classified as unavailable vs unverified | ~456 fields to mark as not_available |

### Recommended Verification Flow

```
1. Run automated checks (schema, range, consistency, source tracking)
   -> Produces anomaly report

2. Review anomaly report (~10-20 issues)
   -> Human decides: fix value, accept as-is, or mark as not_available

3. Fix confirmed errors (voltage, cover dims)
   -> Update JSON files

4. Mark unavailable fields
   -> Add data_quality.not_available_fields to each JSON

5. Mark source references as verified
   -> Set verified_by and verified_date on existing SourceReferences

6. Run completeness dashboard
   -> Confirm 190 data points are all categorized

7. Final validation
   -> All 19 files still pass Pydantic
```

## Schema Extension for Verification Metadata

The SpaModel needs a small extension to carry verification metadata:

```python
class DataQuality(BaseModel):
    """Verification and quality metadata for a spa model's data."""
    verification_date: str | None = None
    verified_by: str | None = None
    not_available_fields: list[str] = Field(default_factory=list)
    anomalies_reviewed: list[dict] = Field(default_factory=list)
    completeness_pct: float | None = None

class SpaModel(BaseModel):
    # ... existing fields ...
    data_quality: DataQuality | None = None  # NEW - optional, backward compatible
```

This is backward compatible -- existing JSON files without `data_quality` still validate because it defaults to None.

## Part Number Strategy

323 part_number fields are null across all 19 models. Research from Phase 3 confirmed:
- NOT available in manufacturer PDFs (owner's manuals don't list individual part numbers)
- NOT available on manufacturer product pages
- AVAILABLE on third-party retailer sites (spastore.com, hottuboutpost.com) but scraping those was deferred

**Recommendation for Phase 4:**
1. Mark all 323 part_number fields as "not_available_in_current_sources" in the data_quality metadata
2. Do NOT mark them as permanently unavailable -- they are deferrable to a future retailer-scraping effort or manual entry
3. The MCP tools in Phase 5 should return "Part numbers not yet populated" (not "Part numbers don't exist")

## Open Questions

1. **Should data_quality go in the JSON or in a separate sidecar file?**
   - In-JSON: simpler, one file per model, but adds metadata to data files
   - Sidecar: `aspen-2026.quality.json` alongside `aspen-2026.json` -- cleaner separation
   - Recommendation: In-JSON as optional Pydantic field. Simpler for MCP tools to read.

2. **How to handle the 6 jet count mismatches?**
   - These may be correct (different counting methods) or extraction errors
   - Requires human judgment after looking at the source PDFs
   - Recommendation: Flag in anomaly report, resolve during human review step

3. **Should Hot Spring web page data be added as verification sources?**
   - The web scraper ran but added nothing (all fields already populated)
   - Adding web URLs as "cross-verification" sources would strengthen provenance
   - Recommendation: Yes, add as verification sources with a note, but this is low priority

4. **How granular should source tracking be?**
   - Currently: document-level (which PDF, which page)
   - Could be: field-level (this specific field came from page 22 of this PDF)
   - Field-level tracking would require significant schema changes
   - Recommendation: Keep document-level for POC. Field-level is a v2 concern.

## Sources

### Primary (HIGH confidence)
- Empirical analysis of all 19 JSON files in `backend/src/data/` -- programmatic field counting, null analysis, consistency checks
- Pydantic schema files in `backend/src/schema/` -- direct code inspection
- Existing validators.py -- range check infrastructure already built
- Existing provenance.py and merger.py -- source tracking already implemented
- Phase 2 and Phase 3 completion notes -- extraction results and known gaps

### Secondary (MEDIUM confidence)
- rich library PyPI page -- confirmed current for CLI table rendering
- Phase 3 research on part number availability -- confirmed not on manufacturer sites

### Tertiary (LOW confidence)
- None -- all findings are based on direct empirical analysis of the codebase

## Metadata

**Confidence breakdown:**
- Data completeness analysis: HIGH -- programmatically analyzed every field in every JSON file
- Verification strategy: HIGH -- builds on existing infrastructure (validators.py, SourceReference)
- Schema extension: HIGH -- backward-compatible optional field, standard Pydantic pattern
- Part number strategy: HIGH -- confirmed across Phase 2 and Phase 3 that sources don't have them
- Anomaly list: HIGH -- detected via automated cross-validation of all 19 files

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (data files are stable; no new extraction planned before Phase 4)
