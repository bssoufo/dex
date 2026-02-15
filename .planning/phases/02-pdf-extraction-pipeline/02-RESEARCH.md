# Phase 2: PDF Extraction Pipeline - Research

**Researched:** 2026-02-15
**Domain:** PDF data extraction, LLM-assisted structured output, manufacturer specification parsing
**Confidence:** HIGH (stack/patterns) / MEDIUM (manufacturer PDF structure -- actual PDFs not yet analyzed)

## Summary

Phase 2 builds an automated extraction pipeline that reads manufacturer PDF owner's manuals and produces structured JSON conforming to the Phase 1 Pydantic schema. The pipeline targets 2026 owner's manuals from three manufacturers: Sundance (880 Series), Hot Spring (Highlife Collection), and Bullfrog (M Series), covering 19 spa models across 10 spec categories each (190 total data points).

Research identified a critical architectural decision: **use Claude's native PDF API rather than pdfplumber as the primary extraction engine**. Claude's PDF support (GA on all active models) converts each page to an image plus extracted text, enabling visual understanding of tables, charts, and multi-column layouts -- exactly the kind of complex formatting found in spa manufacturer manuals. Pdfplumber remains valuable as a **pre-extraction tool** for deterministic text/table extraction that can be fed alongside the PDF to Claude for structured output, providing a hybrid approach that combines deterministic parsing with LLM comprehension.

The extraction approach is: (1) download the 2026 manufacturer PDFs, (2) analyze their structure manually to build per-manufacturer extraction templates, (3) use Claude's PDF API with Pydantic-based structured outputs to extract spec data, (4) validate extracted data against the Phase 1 schema, (5) produce JSON files with full source provenance (page number, section reference). Human verification is deferred to Phase 4 but the pipeline must produce traceability metadata to support it.

**Primary recommendation:** Use Claude's native PDF API with structured outputs (`output_config.format` + Pydantic schema) as the primary extraction method. Use pdfplumber as a supplementary deterministic text extraction tool. Build per-manufacturer extraction templates. Output JSON files that pass Phase 1 Pydantic validation with full SourceReference metadata.

## Standard Stack

The established libraries/tools for this domain:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.79.0+ | Claude API client for PDF extraction | Native PDF support (GA) -- sends PDFs directly to Claude, handles page-to-image conversion, text+vision analysis. Structured outputs guarantee schema-compliant JSON. |
| pdfplumber | 0.11.9 | Deterministic PDF text/table extraction | Pre-extracts tables and text as structured data before LLM processing. Visual debugging with `debug_tablefinder()`. Handles explicit table borders well. |
| pydantic | 2.12.5 | Schema definition and validation | Already used in Phase 1 schema. `model_json_schema()` exports schemas for Claude structured outputs. `model_validate()` validates extraction results. |
| instructor | 1.8+ | Pydantic-based LLM extraction helper | Optional but recommended. Wraps Claude API with automatic Pydantic validation, retry on validation failure, streaming support. Simplifies extraction code. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyMuPDF (fitz) | 1.25+ | Fast PDF text extraction, page rendering | When pdfplumber fails on a specific PDF layout. Faster raw text extraction. Good for rendering pages as images. |
| pathlib | stdlib | File path handling | PDF file management, output directory structure |
| json | stdlib | JSON serialization | Writing extracted data to JSON files |
| hashlib | stdlib | PDF file hashing | Tracking which version of a PDF was used for extraction (provenance) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Claude PDF API | pdfplumber-only + Haiku text | Cheaper but loses visual understanding of complex table layouts. Claude PDF API "sees" the page visually, not just parsed text. |
| Claude PDF API | Docling (IBM) | Open-source, no API cost. But less accurate on complex layouts and requires more custom code. |
| instructor | Raw anthropic SDK | More control but more boilerplate. Instructor adds retry-on-validation-failure which is valuable for extraction. |
| Per-manufacturer templates | One generic extractor | Generic extractors fail silently on manufacturer-specific formatting. Templates are more work upfront but produce better results. |
| Claude Haiku 4.5 | Claude Sonnet 4.5 | Haiku is cheaper ($1/$5 vs $3/$15 per MTok) but may miss subtle table structures. Start with Sonnet for accuracy, downgrade to Haiku after validating results. |

**Installation:**
```bash
cd backend
uv add anthropic pdfplumber instructor
# Optional fallback
uv add pymupdf
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/etl/
    __init__.py
    pipeline.py              # Main orchestrator: run_extraction(manufacturer, pdf_path)
    config.py                # Extraction settings, model selection, paths
    extract/
        __init__.py
        base.py              # BaseExtractor protocol/ABC
        pdf_reader.py        # pdfplumber wrapper: extract raw text, tables per page
        claude_extractor.py  # Claude PDF API + structured outputs extraction
    templates/
        __init__.py
        base.py              # BaseTemplate: defines extraction prompts per category
        sundance.py          # Sundance 880 Series extraction template
        hotspring.py         # Hot Spring Highlife extraction template
        bullfrog.py          # Bullfrog M Series extraction template
    transform/
        __init__.py
        schema_mapper.py     # Maps extracted data to Phase 1 Pydantic models
        validators.py        # Post-extraction validation and sanity checks
    output/
        __init__.py
        writer.py            # Writes validated JSON to data/ directory
        provenance.py        # Builds SourceReference metadata
    pdf_store/               # Downloaded manufacturer PDFs (gitignored)
        sundance/
        hotspring/
        bullfrog/
```

### Pattern 1: Claude PDF API with Structured Outputs (Primary Extraction)

**What:** Send the manufacturer PDF directly to Claude's Messages API as a `document` content block, alongside a carefully crafted extraction prompt that includes the target Pydantic schema. Use `output_config.format` with `json_schema` to guarantee the response conforms to the schema.

**When to use:** For all initial extraction. This is the primary extraction method.

**Example:**
```python
# Source: Anthropic PDF support docs + Structured outputs docs
import anthropic
import base64
from pathlib import Path
from pydantic import BaseModel
from anthropic import transform_schema

from src.schema.models import JetPumpSpecs, SpaModel


class ExtractionResult(BaseModel):
    """Wrapper for a single spec category extraction."""
    manufacturer: str
    model_name: str
    year: int
    page_numbers: list[int]
    section_title: str | None = None
    data: dict  # The actual spec data, varies by category


def extract_spec_from_pdf(
    pdf_path: Path,
    manufacturer: str,
    model_name: str,
    spec_category: str,
    extraction_prompt: str,
    schema: type[BaseModel],
) -> dict:
    """Extract a specific spec category from a manufacturer PDF."""
    client = anthropic.Anthropic()

    pdf_data = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": extraction_prompt,
                    },
                ],
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": transform_schema(schema),
            }
        },
    )

    import json
    return json.loads(response.content[0].text)
```

### Pattern 2: Per-Manufacturer Extraction Templates

**What:** Each manufacturer gets its own template class that defines extraction prompts tailored to that manufacturer's PDF layout. Templates know which pages to focus on, how specs are organized, and what manufacturer-specific terminology to expect.

**When to use:** Always. Generic extraction prompts produce poor results on manufacturer-specific layouts.

**Example:**
```python
# Per-manufacturer template approach
from abc import ABC, abstractmethod


class ManufacturerTemplate(ABC):
    """Base class for manufacturer-specific extraction templates."""

    @property
    @abstractmethod
    def manufacturer_name(self) -> str: ...

    @property
    @abstractmethod
    def series_name(self) -> str: ...

    @property
    @abstractmethod
    def models(self) -> list[str]: ...

    @abstractmethod
    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        """Return a manufacturer-specific extraction prompt for this category."""
        ...

    @abstractmethod
    def get_page_hints(self, spec_category: str) -> str:
        """Return page number hints for where to find this category's data."""
        ...


class Sundance880Template(ManufacturerTemplate):
    manufacturer_name = "sundance"
    series_name = "880 Series"
    models = ["Aspen", "Optima", "Cameo", "Altamar", "Vistamar", "Marin", "Capris"]

    def get_extraction_prompt(self, model_name: str, spec_category: str) -> str:
        base = (
            f"Extract the {spec_category} specifications for the "
            f"Sundance {model_name} (880 Series, 2026) from this owner's manual.\n\n"
            "IMPORTANT RULES:\n"
            "- Extract ONLY data explicitly stated in the document\n"
            "- If a value is not present, use null\n"
            "- Include the page number(s) where you found each piece of data\n"
            "- Sundance uses Fluidix jets and SmartTub connectivity\n"
            "- The 880 Series shares some specs across all models (heater, "
            "  control system) while others are model-specific (jet count, "
            "  dimensions, pump configuration)\n"
        )
        return base + self._category_specific_prompt(spec_category)

    def _category_specific_prompt(self, category: str) -> str:
        prompts = {
            "jet_pumps": (
                "\nFor jet pumps, look for:\n"
                "- Number of jet pumps and their positions\n"
                "- Horsepower ratings (continuous duty HP)\n"
                "- Speed type (1-speed, 2-speed, variable)\n"
                "- Frame size (48 Frame, 56 Frame)\n"
                "- Voltage and amperage\n"
                "- Look in the specifications table or pump section\n"
            ),
            # ... prompts for each of the 10 categories
        }
        return prompts.get(category, "")
```

### Pattern 3: Hybrid Extraction (pdfplumber + Claude)

**What:** Use pdfplumber to pre-extract tables and text deterministically, then pass both the raw PDF and the pre-extracted structured data to Claude. This gives Claude both visual context and parsed tabular data.

**When to use:** When spec data is in well-structured tables (common for dimensions, electrical specs). The pre-extracted table data helps Claude map values correctly.

**Example:**
```python
import pdfplumber


def pre_extract_tables(pdf_path: str, page_numbers: list[int]) -> list[dict]:
    """Use pdfplumber to extract tables from specific pages."""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in page_numbers:
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]  # 0-indexed
                page_tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                        "intersection_tolerance": 3,
                    }
                )
                for table in page_tables:
                    tables.append({
                        "page": page_num,
                        "data": table,
                    })
    return tables


def build_hybrid_prompt(
    model_name: str,
    spec_category: str,
    pre_extracted_tables: list[dict],
) -> str:
    """Build a prompt that includes pre-extracted table data alongside the PDF."""
    prompt = f"Extract {spec_category} specs for the {model_name}.\n\n"
    if pre_extracted_tables:
        prompt += "I have pre-extracted the following table data from the PDF:\n\n"
        for table_info in pre_extracted_tables:
            prompt += f"--- Table from page {table_info['page']} ---\n"
            for row in table_info["data"]:
                prompt += " | ".join(str(cell) for cell in row) + "\n"
            prompt += "\n"
        prompt += (
            "Use BOTH the pre-extracted tables above AND the PDF itself to "
            "extract the specifications. The PDF provides visual context that "
            "the table extraction may have missed.\n"
        )
    return prompt
```

### Pattern 4: Extraction with Source Provenance

**What:** Every extracted value includes metadata about where it came from in the source PDF. This enables traceability back to the source document for human verification in Phase 4.

**When to use:** Always. This is a success criterion for Phase 2.

**Example:**
```python
from src.schema.parts import SourceReference


def build_source_reference(
    pdf_filename: str,
    page_numbers: list[int],
    section: str | None = None,
    accessed_date: str | None = None,
) -> SourceReference:
    """Build a SourceReference for a PDF extraction."""
    return SourceReference(
        source_type="pdf",
        document_name=pdf_filename,
        page_number=page_numbers[0] if len(page_numbers) == 1 else None,
        section=section,
        accessed_date=accessed_date or "2026-02-15",
    )
```

### Anti-Patterns to Avoid

- **One-shot full extraction:** Do NOT try to extract all 10 spec categories in a single LLM call. Extract one category at a time per model. This keeps prompts focused and makes debugging easier.
- **Generic prompts across manufacturers:** Do NOT use the same extraction prompt for Sundance, Hot Spring, and Bullfrog. Their PDF layouts, terminology, and spec organization differ significantly.
- **Trusting extraction output without validation:** Do NOT skip Pydantic validation of extracted results. Always run `model_validate()` on extraction output before writing JSON files.
- **Ignoring page numbers:** Do NOT extract data without recording which pages it came from. This is required for Phase 4 human verification.
- **Sending entire manual for each category:** The manuals may be 50-100 pages. Use page hints or crop relevant sections to reduce token cost and improve accuracy.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF to structured JSON | Custom PDF parser with regex | Claude PDF API + structured outputs | Regex breaks on varied layouts; Claude handles visual complexity. Structured outputs guarantee schema compliance. |
| Schema-constrained LLM output | Manual JSON parsing + validation | `output_config.format` with `json_schema` (Anthropic) or `instructor` library | Anthropic's structured outputs use constrained decoding -- the LLM literally cannot produce schema-violating JSON. Manual parsing has edge cases. |
| Pydantic to JSON Schema conversion | Manual schema writing | `model_json_schema()` / `transform_schema()` | Pydantic already generates JSON Schema. The Anthropic SDK's `transform_schema()` handles the conversion to structured output format. |
| Table detection in PDFs | Custom line-intersection algorithm | pdfplumber's `extract_tables()` | pdfplumber implements Nurminen's thesis algorithm for table detection. Handles explicit lines, implied borders, merged regions. |
| PDF page rendering for debugging | PIL/Pillow manual rendering | pdfplumber's `page.to_image()` + `debug_tablefinder()` | Visual debugging shows detected lines, intersections, and table boundaries overlaid on the page. |
| Retry on LLM validation failure | Custom retry loop | `instructor` library | Instructor automatically retries with the validation error message when Pydantic validation fails, giving the LLM a chance to correct itself. |

**Key insight:** The combination of Claude's PDF API (vision-based understanding) + structured outputs (schema-guaranteed JSON) + Pydantic (validation) makes the extraction pipeline significantly simpler than traditional pdfplumber-only approaches. The LLM handles the hard parts (understanding layout, resolving ambiguity) while structured outputs handle the reliability part (guaranteed schema compliance).

## Common Pitfalls

### Pitfall 1: Silent Extraction Errors -- Values Look Right But Are Wrong

**What goes wrong:** Claude extracts a pump HP of 2.5 when the actual value is 2.0, or transposes digits in a part number (6500-310 becomes 6500-301). The extracted JSON passes schema validation (correct type, plausible range) but the value is factually wrong.

**Why it happens:** The PDF has multiple models' specs in adjacent columns or rows. Claude picks the value from the wrong column. Or the OCR/vision misreads a digit. Or merged cells cause column alignment confusion.

**How to avoid:**
1. Extract one model at a time -- include the model name prominently in the prompt
2. Cross-validate: extract the same data from both the PDF and the manufacturer website (Phase 3). Flag discrepancies.
3. Include sanity checks: HP values between 0.5 and 10, jet counts between 10 and 100, dimensions between 50 and 120 inches
4. Always include page number references so human reviewers can spot-check

**Warning signs:** All models in a series extract identical specs (copy-paste error), numeric values have unusual precision (2.4999 HP), part numbers don't match manufacturer format patterns.

### Pitfall 2: Token Cost Explosion from Sending Full PDFs

**What goes wrong:** Each manufacturer manual is 50-100+ pages. Sending the full PDF for each of 10 categories for each of 7-8 models means 70-80 Claude API calls with 50-100 page PDFs. At ~2,000-3,000 tokens per page (text + image), a 100-page manual is 200K-300K input tokens per call.

**Why it happens:** The naive approach is "send the whole PDF, ask for what you need." Claude can handle it (100-page limit), but the cost adds up: 80 calls x 250K tokens x $3/MTok = ~$60 just for Sundance.

**How to avoid:**
1. Use prompt caching (`cache_control: {"type": "ephemeral"}`) -- the PDF is cached for the first call, subsequent calls against the same PDF are dramatically cheaper (90% discount on cached tokens)
2. Identify relevant pages first (either manually or with a cheap "page identification" call), then crop the PDF to relevant sections
3. Batch extractions: extract multiple categories from the same page range in one call where specs are co-located
4. Use Claude Haiku 4.5 for straightforward extractions, Sonnet for complex layouts
5. Use the Batch API for 50% cost reduction on non-urgent extractions

**Warning signs:** API costs exceed $20 for the full extraction run, individual calls timeout, extraction takes more than 30 minutes total.

### Pitfall 3: Manufacturer PDFs Change Format Between Years

**What goes wrong:** The extraction template works perfectly on the 2026 Sundance manual. Next year, the 2027 manual reorganizes the spec tables, moves information to different pages, or changes terminology. The template silently extracts wrong data or returns nulls.

**Why it happens:** Owner's manuals are marketing documents -- they get redesigned periodically. Table layouts, page numbering, and section organization change.

**How to avoid:**
1. Design templates with flexibility -- use semantic section names, not hardcoded page numbers
2. Include a "confidence" field in extraction results -- if the LLM is uncertain about a value, flag it
3. Build a template validation step: after extraction, check that critical fields (pump HP, jet count, dimensions) are non-null and plausible
4. Document which PDF version (filename, hash) each extraction was performed against

**Warning signs:** Extraction suddenly returns many null values for a manufacturer, template that worked before now produces validation errors.

### Pitfall 4: Bullfrog JetPak Modular System Requires Different Extraction Logic

**What goes wrong:** Sundance and Hot Spring have fixed jet configurations -- each model has a known number and type of jets. Bullfrog's M Series uses a modular JetPak system where customers choose from 16+ JetPak options, each with different jet types and counts. Extracting "total jet count" for a Bullfrog is meaningless without understanding the JetPak context.

**Why it happens:** The Phase 1 schema handles this (JetSpecs has `jet_system_type: modular_jetpak`, `jetpak_count`, `jetpak_options` fields), but the extraction template must know to look for completely different information in the Bullfrog PDF.

**How to avoid:**
1. The Bullfrog extraction template must be fundamentally different from Sundance/Hot Spring templates
2. Extract: number of JetPak bays, number of available JetPak options, base jet count (without JetPaks), max jet count (with all JetPaks)
3. Do NOT try to enumerate individual jet types for Bullfrog -- the combinations are too numerous

**Warning signs:** Bullfrog jet data looks identical to fixed-jet manufacturer data, JetPak-specific fields are all null.

### Pitfall 5: PDF Text Extraction Produces Garbage for Non-Selectable Text

**What goes wrong:** Some manufacturer PDFs contain scanned pages or embedded images where text is rendered as graphics, not selectable text. pdfplumber extracts nothing or garbled characters. Claude's PDF API handles this better (it processes pages as images) but may still struggle with low-resolution scans.

**Why it happens:** Older manuals or certain pages (spec diagrams, wiring schematics) are scanned images embedded in the PDF rather than native text.

**How to avoid:**
1. Test each manufacturer's PDF for text selectability before building extraction templates
2. For image-heavy pages, rely on Claude's vision capability rather than pdfplumber text extraction
3. If a specific page is a scanned image, increase the resolution hint or extract that page as an image via PyMuPDF and send as an image content block

**Warning signs:** pdfplumber returns empty strings for pages that visually contain text, extracted text has many unicode replacement characters.

## Code Examples

### Complete Extraction Pipeline for One Model

```python
# Source: Pattern synthesis from Anthropic PDF docs + structured outputs docs
import json
import base64
from pathlib import Path

import anthropic
from anthropic import transform_schema
from pydantic import BaseModel, ValidationError

from src.schema.models import SpaModel
from src.schema.parts import SourceReference


class CategoryExtraction(BaseModel):
    """Schema for extracting a single spec category."""
    page_numbers: list[int]
    section_title: str | None = None
    confidence: str  # "high", "medium", "low"
    notes: str | None = None
    data: dict


def extract_model(
    pdf_path: Path,
    manufacturer: str,
    series: str,
    model_name: str,
    year: int,
    template: "ManufacturerTemplate",
    output_dir: Path,
) -> SpaModel | None:
    """Extract all 10 spec categories for a single spa model."""
    client = anthropic.Anthropic()
    pdf_data = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")

    spec_categories = [
        "jet_pumps", "circulation_pump", "spa_pak", "topside_control",
        "jets", "headrests", "filters", "heater", "lighting", "cover",
    ]

    extracted = {}
    source_refs = []

    for category in spec_categories:
        prompt = template.get_extraction_prompt(model_name, category)

        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                            "cache_control": {"type": "ephemeral"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": transform_schema(CategoryExtraction),
                }
            },
        )

        result = CategoryExtraction.model_validate_json(
            response.content[0].text
        )
        extracted[category] = result.data
        source_refs.append(
            SourceReference(
                source_type="pdf",
                document_name=pdf_path.name,
                page_number=result.page_numbers[0] if result.page_numbers else None,
                section=result.section_title,
                accessed_date="2026-02-15",
            )
        )

    # Assemble into SpaModel
    model_data = {
        "manufacturer": manufacturer,
        "series": series,
        "model_name": model_name,
        "year": year,
        **extracted,
        "source_documents": [ref.model_dump() for ref in source_refs],
    }

    try:
        spa_model = SpaModel.model_validate(model_data)
    except ValidationError as e:
        print(f"Validation failed for {model_name}: {e}")
        # Write raw extraction for debugging
        raw_path = output_dir / f"{model_name.lower()}-{year}-RAW.json"
        raw_path.write_text(json.dumps(model_data, indent=2))
        return None

    # Write validated JSON
    out_path = output_dir / f"{model_name.lower()}-{year}.json"
    out_path.write_text(
        json.dumps(spa_model.model_dump(), indent=2)
    )
    return spa_model
```

### Using Instructor for Extraction with Retries

```python
# Source: Instructor docs (python.useinstructor.com/integrations/anthropic/)
import instructor
from pydantic import BaseModel, Field
from src.schema.models import JetPumpSpec, JetPumpSpecs
from src.schema.enums import PumpSpeed


class JetPumpExtraction(BaseModel):
    """Extraction result for jet pump specifications."""
    pumps: list[JetPumpSpec] = Field(min_length=1, max_length=4)
    diverter_valves: int | None = None
    total_brake_horsepower: float | None = None
    page_numbers: list[int] = Field(
        description="Page numbers where pump data was found"
    )


client = instructor.from_provider(
    "anthropic/claude-sonnet-4-5-20250514",
    mode=instructor.Mode.TOOLS,
)

result = client.create(
    messages=[
        {
            "role": "user",
            "content": [
                # PDF document block
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64,
                    },
                },
                {
                    "type": "text",
                    "text": "Extract jet pump specifications for the Sundance Aspen...",
                },
            ],
        }
    ],
    response_model=JetPumpExtraction,
    max_retries=2,  # Retry with validation errors if extraction fails
)
```

### pdfplumber Pre-Extraction with Visual Debugging

```python
# Source: pdfplumber GitHub README
import pdfplumber


def analyze_pdf_structure(pdf_path: str) -> dict:
    """Analyze a manufacturer PDF to understand its structure."""
    report = {"pages": [], "total_pages": 0}

    with pdfplumber.open(pdf_path) as pdf:
        report["total_pages"] = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            page_info = {
                "page_number": i + 1,
                "width": page.width,
                "height": page.height,
                "has_tables": False,
                "table_count": 0,
                "text_preview": "",
            }

            # Try table extraction
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }
            )
            if tables:
                page_info["has_tables"] = True
                page_info["table_count"] = len(tables)

            # Get text preview (first 200 chars)
            text = page.extract_text() or ""
            page_info["text_preview"] = text[:200]

            report["pages"].append(page_info)

            # Visual debugging: save annotated page images
            im = page.to_image(resolution=150)
            im.debug_tablefinder()
            im.save(f"debug/page_{i+1}.png")

    return report
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pdfplumber/Tabula only | Claude PDF API (vision + text) | Claude PDF support GA 2025 | LLM visually understands page layout, handles complex tables that rule-based extractors miss |
| tool_use for structured output | `output_config.format` with `json_schema` | Structured outputs GA Jan 2026 | Constrained decoding guarantees schema compliance. No more JSON parsing failures. |
| LangChain extraction chains | Direct Anthropic SDK + Pydantic | 2025-2026 | Simpler, fewer dependencies, native structured output support |
| Manual JSON validation | Pydantic model_validate() | Pydantic v2 (2023+) | Rust-powered validation, 5-50x faster, native JSON Schema export |
| Single extraction attempt | instructor with retry on validation | instructor 1.0+ (2024) | Automatic retry with error context when extraction output fails validation |

**Deprecated/outdated:**
- `output_format` parameter (use `output_config.format` instead -- old param still works temporarily)
- `structured-outputs-2025-11-13` beta header (no longer required, structured outputs are GA)
- SSE transport for MCP (replaced by Streamable HTTP, but not relevant to Phase 2)

## Manufacturer PDF Sources (Critical Finding)

Research identified the actual 2026 PDF download URLs for all three manufacturers:

### Sundance 880 Series (2026)
- **URL:** `https://links.imagerelay.com/cdn/574/ql/d3d8cc5af9e7477b817ca804ada71e50/25-880-ENG-Manual-Rev-D-103125-L.pdf`
- **Source:** sundancespas.com/en-us/manuals-and-user-guides.html
- **Format:** Single PDF covering all 880 Series models (Aspen, Optima, Cameo, Altamar, Vistamar, Marin, Capris)
- **Confidence:** HIGH -- direct link from official manufacturer website

### Hot Spring Highlife Collection (2026)
- **URL:** `https://d1oxc6ayqrhsgs.cloudfront.net/hot-spring/hot-spring-highlife-collection-owners-manual-2026.pdf`
- **Source:** hotspring.com/owners/manuals-and-resources/highlife
- **Format:** Single PDF covering all Highlife models (Grandee, Envoy, Aria, Vanguard, Sovereign, Prodigy, Jetsetter LX, Jetsetter)
- **Confidence:** HIGH -- direct link from official manufacturer website

### Bullfrog M Series (2025 -- 2026 may not be published yet)
- **URL:** Available at bullfrogspas.com/manuals/ -- direct link not extracted (JavaScript-rendered page)
- **Source:** bullfrogspas.com/manuals/
- **Format:** Separate M Series manual covering M9, M8, M7, M6
- **Confidence:** MEDIUM -- 2025 manual confirmed available, 2026 version may need to be checked manually
- **Note:** If 2026 manual is not yet available, use 2025 as baseline (specs typically carry forward with minor changes)

### Key Insight: Manual Structure

All three manufacturers publish a **single series-level owner's manual** that covers all models in that series. This means:
- Sundance: 1 PDF covers 7 models (880 Series)
- Hot Spring: 1 PDF covers 8 models (Highlife Collection)
- Bullfrog: 1 PDF covers 4 models (M Series)

Total PDFs to process: **3** (not 19). Each PDF contains specs for multiple models, typically in comparison tables or model-specific sections. This is a major efficiency gain -- prompt caching means the PDF is loaded once and queried multiple times.

## Extraction Strategy by Manufacturer

### Sundance 880 Series
- **Expected layout:** Specs likely in comparison table format (models as columns, specs as rows)
- **Key terminology:** Fluidix jets, SmartTub System, MicroClean Ultra filtration
- **Shared specs:** Control system, heater, filtration system shared across series
- **Model-specific:** Jet count, pump configuration, dimensions, seating capacity
- **Confidence:** MEDIUM -- based on prior manual versions; actual 2026 PDF not yet analyzed

### Hot Spring Highlife Collection
- **Expected layout:** Model-specific spec pages plus series-level shared features
- **Key terminology:** Moto-Massage DX jets, SilentFlo circulation, Tri-X filtration, IQ 2020 control, No-Fault heater, FreshWater system
- **Shared specs:** IQ 2020 control, SilentFlo pump, Tri-X filter, No-Fault heater
- **Model-specific:** Jet types and counts per zone, pump configuration, dimensions, water features
- **Confidence:** MEDIUM -- based on prior manual versions; actual 2026 PDF not yet analyzed

### Bullfrog M Series
- **Expected layout:** Likely different from others due to modular JetPak system
- **Key terminology:** JetPak, Simplicity filtration, EnduraFrame construction
- **Unique challenge:** JetPak system means jet specs are configurations, not fixed counts
- **Shared specs:** Control system, filtration, cover
- **Model-specific:** JetPak bay count, dimensions, pump count
- **Confidence:** MEDIUM -- based on prior manual versions; actual 2026 PDF not yet analyzed

## Claude API Cost Estimation

### Per-Model Extraction Cost

| Metric | Value |
|--------|-------|
| Pages per manual (estimated) | 50-80 |
| Tokens per page (text + image) | ~2,500 |
| Total tokens per manual | ~125,000-200,000 |
| Calls per model (10 categories) | 10 |
| Prompt caching benefit | ~90% discount on cached PDF tokens after first call |

### Total Extraction Cost Estimate (All 19 Models)

| Item | Calculation | Cost |
|------|-------------|------|
| First call per manufacturer (uncached) | 3 PDFs x 175K tokens x $3/MTok | ~$1.58 |
| Subsequent calls (cached, 90% off) | 16 models x 10 categories x 175K tokens x $0.30/MTok | ~$8.40 |
| Output tokens | 190 extractions x 2K tokens x $15/MTok | ~$5.70 |
| **Total estimated** | | **~$16** |
| With Batch API (50% off) | | **~$8** |

**Cost note:** Using Haiku instead of Sonnet would reduce costs by ~3x but may sacrifice accuracy on complex table layouts. Recommend starting with Sonnet and testing Haiku afterward.

## Open Questions

Things that could not be fully resolved:

1. **Actual PDF structure for 2026 manuals**
   - What we know: PDFs exist and are downloadable for Sundance and Hot Spring (2026). Bullfrog may only have 2025.
   - What's unclear: The internal structure -- where spec tables are, how they're formatted, whether text is selectable or scanned
   - Recommendation: **First task of Phase 2 should be downloading all 3 PDFs and performing manual structure analysis** before building any extraction code

2. **Spec data completeness in owner's manuals**
   - What we know: Owner's manuals contain general specifications (dimensions, jet counts, pump info)
   - What's unclear: Whether owner's manuals contain all 10 spec categories at sufficient detail (part numbers especially are often in separate service manuals, not owner's manuals)
   - Recommendation: Analyze PDFs first. If part numbers are missing from owner's manuals, those fields will be marked as null and filled from web scraping in Phase 3 or manual entry in Phase 4

3. **Bullfrog 2026 manual availability**
   - What we know: 2025 M Series manual is available. 2026 may not be published yet.
   - What's unclear: Whether Bullfrog has a 2026 manual or if the 2025 manual applies to 2026 models
   - Recommendation: Check bullfrogspas.com directly. If 2026 is unavailable, use 2025 manual and note the version mismatch in source references

4. **Extraction accuracy without human verification**
   - What we know: Phase 2 produces extraction output; Phase 4 adds human verification
   - What's unclear: What accuracy level the automated pipeline achieves before human review
   - Recommendation: Build automated sanity checks (range validation, format validation, cross-model consistency checks) into the pipeline. Track confidence scores. Flag low-confidence extractions.

5. **Claude PDF API performance on spa manuals specifically**
   - What we know: Claude PDF API handles documents up to 100 pages with text+vision analysis
   - What's unclear: How well it handles the specific formatting patterns in spa manufacturer manuals (multi-column comparison tables, specification charts with icons, etc.)
   - Recommendation: Build a quick prototype extraction on one page of one manual before committing to the full pipeline architecture

## Sources

### Primary (HIGH confidence)
- [Anthropic PDF Support Docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support) -- PDF API capabilities, limits, code examples
- [Anthropic Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- GA status, Pydantic integration, JSON schema constraints
- [pdfplumber GitHub](https://github.com/jsvine/pdfplumber) -- table extraction API, settings, visual debugging
- [Sundance Spas Manuals Page](https://www.sundancespas.com/en-us/manuals-and-user-guides.html) -- 2026 880 Series PDF confirmed
- [Hot Spring Highlife Manuals Page](https://www.hotspring.com/owners/manuals-and-resources/highlife) -- 2026 Highlife PDF confirmed
- [Instructor Library Anthropic Integration](https://python.useinstructor.com/integrations/anthropic/) -- Pydantic extraction with retries

### Secondary (MEDIUM confidence)
- [Unstract: LLMs for PDF Data Extraction](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/) -- extraction approach comparison
- [Best Python Libraries to Extract Tables From PDF in 2026](https://unstract.com/blog/extract-tables-from-pdf-python/) -- pdfplumber position in ecosystem
- [Bullfrog Spas Manuals Page](https://www.bullfrogspas.com/manuals/) -- 2025 M Series manual confirmed, 2026 availability unclear

### Tertiary (LOW confidence)
- [pdfplumber merged cells discussion](https://github.com/jsvine/pdfplumber/issues/79) -- community discussion on handling complex tables
- [pdfplumber table settings discussion](https://github.com/jsvine/pdfplumber/discussions/1071) -- parameter tuning examples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Claude PDF API and structured outputs are well-documented and GA. pdfplumber is mature.
- Architecture: HIGH -- Per-manufacturer templates with Claude PDF API is the clear best approach.
- Manufacturer PDF sources: HIGH (Sundance, Hot Spring) / MEDIUM (Bullfrog) -- actual download links found for 2 of 3.
- Extraction accuracy: MEDIUM -- approach is sound but untested against actual spa manufacturer PDFs.
- Cost estimation: MEDIUM -- based on typical PDF sizes and token counts; actual costs depend on manual page counts.
- Pitfalls: HIGH -- well-documented in prior research and confirmed by PDF extraction literature.

**Research date:** 2026-02-15
**Valid until:** 60 days for core patterns (Claude API, pdfplumber are stable); 14 days for manufacturer PDF URLs (may change)
