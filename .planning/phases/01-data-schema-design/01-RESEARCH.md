# Phase 1: Data Schema Design - Research

**Researched:** 2026-02-15
**Domain:** Pydantic schema design for hot tub/spa technical specifications with cross-references
**Confidence:** HIGH

## Summary

This research investigates what data fields exist across all 10 spec categories for the three POC manufacturers (Sundance, Hot Spring, Bullfrog), how those fields vary between models, which specs are shared at series level vs model-specific, and how Pydantic v2 should be used to model this domain. The research was conducted by fetching actual manufacturer product pages and parts supplier data to understand real-world data shapes.

The spa parts domain has a deceptive amount of relational complexity hiding behind what appears to be simple key-value specifications. Each of the 10 spec categories has its own data shape -- pumps need HP ratings and frame sizes with per-position data, jets need type/quantity breakdowns with part numbers per type, filters need area and cartridge details, and covers need tapered dimensional data. The three manufacturers structure their specs differently: Sundance uses the 6500/6541 part number series with year-range compatibility, Hot Spring uses named proprietary systems (Wavemaster, SilentFlo, Tri-X, IQ 2020) with part numbers in the 71xxx-77xxx range, and Bullfrog uses a modular JetPak system that fundamentally differs from fixed-jet architectures. Additionally, some specs are genuinely shared at series level (all Sundance 880 models use the same spa pak, same filter system, same heater), while others vary per model (jet count, dimensions, pump count on smaller models).

**Primary recommendation:** Design the Pydantic schema with a top-level `SpaModel` that contains 10 nested category models (one per spec category), each with their own field structure. Use enums for known finite values (manufacturers, jet types), `list[T]` for multi-position data (pumps, jets), explicit `None | T` for optional fields, and a separate `PartReference` model for part numbers that includes supersession and compatibility metadata. Validate the schema against three pilot models (Aspen, Grandee, M9) before defining all 19 models.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.12.5 | Schema definition, validation, JSON Schema export | Rust-powered validation, native JSON Schema generation via `model_json_schema()`, strict type enforcement. Already selected in stack research. |
| Python | 3.12 | Runtime | Required by project stack decisions |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic `StrEnum` / `Literal` | built-in | Finite value constraints | For manufacturer names, jet types, spec categories -- anywhere a field has a known finite set of valid values |
| `json` (stdlib) | built-in | JSON file I/O | Reading/writing model data files |
| `pathlib` (stdlib) | built-in | File path handling | Organizing data directory structure |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic models | Python dataclasses + jsonschema | Loses automatic JSON Schema export, loses validation, loses `model_json_schema()`. No benefit. |
| StrEnum for known values | Plain strings | Loses compile-time and validation-time checking of valid values. Part number categories like "jet_pump" would be free-text strings. |
| Nested Pydantic models | Flat dict structures | Flat dicts lose type safety, lose per-category validation, and make the schema harder to understand and extend. |

**Installation:**
```bash
# Pydantic is already in the project dependencies from stack research
uv add pydantic
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
  src/
    schema/
      __init__.py           # Public exports
      models.py             # Top-level SpaModel and category models
      enums.py              # Manufacturer, JetType, SpecCategory enums
      parts.py              # PartReference, Supersession models
      cross_ref.py          # CrossReference, Compatibility models
      validators.py         # Custom validators (part number format, etc.)
      export.py             # JSON Schema export utilities
    data/
      sundance/
        880-series/
          aspen-2026.json
          optima-2026.json
          cameo-2026.json
          altamar-2026.json
          vistamar-2026.json
          marin-2026.json
          capris-2026.json
      hotspring/
        highlife/
          grandee-2026.json
          envoy-2026.json
          aria-2026.json
          vanguard-2026.json
          sovereign-2026.json
          prodigy-2026.json
          jetsetter-lx-2026.json
          jetsetter-2026.json
      bullfrog/
        m-series/
          m9-2026.json
          m8-2026.json
          m7-2026.json
          m6-2026.json
    schemas/
      spa-model.schema.json  # Exported JSON Schema
  tests/
    test_schema/
      test_models.py         # Schema instantiation tests
      test_validation.py     # Validation rule tests
      test_export.py         # JSON Schema export tests
      test_pilot_data.py     # Pilot model data validation
      conftest.py            # Shared fixtures (sample data)
```

### Pattern 1: Nested Category Models

**What:** The top-level `SpaModel` contains exactly 10 nested models, one per spec category. Each category model has its own field structure tailored to that category's data shape.

**When to use:** Always. This is the core pattern for the entire schema.

**Why:** Different spec categories have fundamentally different shapes. A pump spec has HP, speed, frame size. A jet spec has type, quantity, zone. A cover spec has dimensions. Flattening these into a single model would create a monster with 50+ fields where half are always null for any given category.

**Example:**
```python
from pydantic import BaseModel, Field
from enum import StrEnum

class Manufacturer(StrEnum):
    SUNDANCE = "sundance"
    HOT_SPRING = "hotspring"
    BULLFROG = "bullfrog"

class SpaModel(BaseModel):
    """Top-level model representing a complete spa specification."""
    manufacturer: Manufacturer
    series: str                          # e.g., "880 Series", "Highlife", "M Series"
    model_name: str                      # e.g., "Aspen", "Grandee", "M9"
    year: int                            # e.g., 2026
    seating_capacity: int

    jet_pumps: JetPumpSpecs
    circulation_pump: CirculationPumpSpec | None = None
    spa_pak: SpaPakSpec
    topside_control: TopsideControlSpec
    jets: JetSpecs
    headrests: HeadrestSpecs
    filters: FilterSpecs
    heater: HeaterSpec
    lighting: LightingSpecs
    cover: CoverSpec

    # Physical dimensions
    dimensions: DimensionsSpec

    # Cross-references
    compatibility_notes: list[str] = Field(default_factory=list)
    source_documents: list[SourceReference] = Field(default_factory=list)
```

### Pattern 2: Multi-Position / Multi-Item Lists

**What:** For spec categories where a model has multiple instances (e.g., pump position 1 and pump position 2, or multiple jet types), use `list[T]` with each item carrying a position/type identifier.

**When to use:** Jet pumps (models have 1-3 pumps), jets (models have 5-7 distinct jet types), headrests (multiple positions), filters (1-2 cartridges).

**Why:** The Sundance Aspen has 2 jet pumps with identical specs. The Hot Spring Grandee has 2 jet pumps with different models (Wavemaster 9000 vs 9200). The Bullfrog M9 has 3 therapy pumps. The schema must handle all these cases without hardcoding "pump_1" and "pump_2" fields, because the M9 needs "pump_3."

**Example:**
```python
class JetPumpSpec(BaseModel):
    """Specification for a single jet pump."""
    position: int = Field(ge=1, description="Pump position number (1, 2, 3)")
    model_name: str | None = None        # e.g., "Wavemaster 9000"
    horsepower_continuous: float          # e.g., 2.5
    horsepower_breakdown: float | None = None  # e.g., 5.2 (breakdown torque)
    speed: str                           # e.g., "1-speed", "2-speed"
    amperage_max: float | None = None    # e.g., 11.3
    frame: str | None = None             # e.g., "56 Frame"
    voltage: int = 240                   # e.g., 240
    part_number: PartReference | None = None

class JetPumpSpecs(BaseModel):
    """All jet pump specifications for a model."""
    pumps: list[JetPumpSpec] = Field(min_length=1)
    diverter_valves: int | None = None
```

### Pattern 3: Series-Level Shared Specs with Model Override

**What:** Some specs are identical across all models in a series (e.g., all Sundance 880 models share the same spa pak, filter system, and heater). Rather than duplicating this data in every model file, document which specs are series-level vs model-specific. However, for POC simplicity, each model JSON file contains the complete spec even if shared -- the "shared" annotation is metadata, not a data deduplication mechanism.

**When to use:** When the same spec values repeat across models in a series.

**Why:** For the POC with 19 models and JSON files, full duplication is acceptable and simpler to query. But the schema should include a `shared_with_series` flag so the MCP tools can report "this spec is shared across all 880 Series models" and future ETL can validate consistency.

**Example:**
```python
class SpaPakSpec(BaseModel):
    """Spa pak (control box) specification."""
    model_name: str                      # e.g., "IQ 2020"
    features: list[str] = Field(default_factory=list)
    voltage: int                         # e.g., 230
    amperage: int                        # e.g., 50
    frequency_hz: int = 60
    part_number: PartReference | None = None
    shared_with_series: bool = False     # True = same across all models in series
```

### Pattern 4: Part Reference with Supersession

**What:** Part numbers are not simple strings. They have a manufacturer-specific format, can be superseded by newer part numbers, and have year-range compatibility. A `PartReference` model captures this complexity.

**When to use:** Every field that contains a part number.

**Why:** From research: Sundance heater 6500-301 was replaced by 6500-310. Hot Spring pillow 77228 fits 2014-current. Jet 6541-102 replaces 6000-315. These relationships are critical for the "which parts fit which models" cross-reference requirement (DATA-02).

**Example:**
```python
class PartReference(BaseModel):
    """A part number with its compatibility and supersession context."""
    part_number: str                     # e.g., "6500-310"
    manufacturer_sku: str | None = None  # Manufacturer's own SKU if different
    description: str | None = None       # Brief description
    supersedes: str | None = None        # Part number this replaces
    superseded_by: str | None = None     # Part number that replaces this
    fits_models: list[str] = Field(default_factory=list)  # Which models this part fits
    fits_years: str | None = None        # e.g., "2019-2026" or "2014+"
    notes: str | None = None             # Compatibility notes
```

### Anti-Patterns to Avoid

- **Flat top-level model with 50+ fields:** Do not put all specs at the root level. Use nested category models.
- **Hardcoded pump_1/pump_2 fields:** Use `list[JetPumpSpec]` to handle variable numbers of pumps.
- **String-only part numbers:** Part numbers need context (supersession, compatibility). Use `PartReference`.
- **Omitting nullable annotations:** If a field might not have data, use `T | None = None`. Never leave it as a required field that gets filled with placeholder values like "N/A" or "unknown".
- **Generic dict for category data:** Do not use `dict[str, Any]` for spec categories. Each category has a defined shape; model it explicitly.
- **Trying to normalize/deduplicate at JSON level:** For POC, each model file should be self-contained. Normalization is a database concern for the PostgreSQL migration.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema generation | Custom schema generator | `SpaModel.model_json_schema()` | Pydantic generates valid JSON Schema automatically from model definitions. Custom generators are fragile and miss edge cases (unions, nested refs, enums). |
| Data validation | Custom validation functions | Pydantic model instantiation + validators | Pydantic's Rust core validates at 5-50x the speed of hand-written Python validation. Field validators, model validators, and type annotations handle all validation needs. |
| Enum value checking | if/elif chains | `StrEnum` subclasses | Pydantic automatically validates enum membership. No manual checking needed. |
| Part number format validation | Regex in application code | `field_validator` on PartReference | Keep validation logic co-located with the data model, not scattered in application code. |
| JSON file reading/writing | Custom serialization | `model.model_dump_json()` / `SpaModel.model_validate_json()` | Pydantic handles serialization/deserialization with type coercion, validation, and proper None handling built in. |
| Schema documentation | Separate documentation files | `Field(description=...)` + JSON Schema export | Descriptions in Field() propagate to the exported JSON Schema, keeping docs and schema in sync automatically. |

**Key insight:** Pydantic v2 is not just a validation library -- it is a complete schema definition, validation, serialization, and documentation system. The entire Phase 1 deliverable (schema + validation + JSON Schema export) can be built using Pydantic alone with no additional libraries.

## Common Pitfalls

### Pitfall 1: Designing the Schema Without Looking at Real Data First

**What goes wrong:** Schema is designed based on assumptions about what specs exist, then real manufacturer data does not fit. Fields are missing, types are wrong, or the structure does not accommodate the actual complexity.
**Why it happens:** It is tempting to design the schema abstractly from the 10 category names. But "jet part numbers and quantities" is not a simple field -- the Grandee has 7 distinct jet types with different quantities, each with its own part number.
**How to avoid:** This research documents the actual field structures from real manufacturer pages. The schema design should be driven by this data, not by abstract category names. The three pilot models (Aspen, Grandee, M9) must be fully populated and validated before the schema is considered complete.
**Warning signs:** A spec category modeled as a single string or a simple key-value pair. Jet specs without type breakdown. Pump specs without position numbers.

### Pitfall 2: Confusing "Not Listed on Website" with "Does Not Exist"

**What goes wrong:** Manufacturer product pages do not show all specs. For example, Sundance does not list heater wattage or spa pak model on the Aspen product page. Hot Spring does not list individual headrest part numbers. The schema designer assumes these fields do not exist and omits them.
**Why it happens:** Manufacturer marketing pages emphasize features, not technical specs. The full specs are in owner's manuals, dealer documentation, and parts supplier websites.
**How to avoid:** Use `T | None = None` for every field that might not be available from the primary source. The schema must accommodate the most complete data set (parts supplier data) even if the initial ETL source (manufacturer website) provides less. Flag fields as nullable, never omit them.
**Warning signs:** Schema has no optional fields. Required fields that have to be filled with "N/A" strings instead of None.

### Pitfall 3: Different Manufacturers Needing Different Schema Structures

**What goes wrong:** Bullfrog's JetPak system is fundamentally different from Sundance and Hot Spring's fixed-jet systems. Trying to force both into one jet schema either loses information about JetPaks (how many, which types, interchangeability) or creates fields that are meaningless for fixed-jet spas.
**Why it happens:** The three manufacturers use genuinely different engineering approaches. Bullfrog's modularity (swappable JetPaks with 16 massage options) has no equivalent in the other brands.
**How to avoid:** Use a unified jet schema that can represent both approaches. JetPaks are modeled as jet groups with a `type` field. Fixed jets are modeled as individual jet entries with a `type` field. The schema accommodates both without manufacturer-specific branching. Include a `jet_system_type` field to indicate the approach ("fixed" vs "modular_jetpak").
**Warning signs:** if/else branching based on manufacturer name in the schema definition. Separate schema classes per manufacturer.

### Pitfall 4: Not Modeling the Source/Provenance of Each Data Point

**What goes wrong:** Data is populated but nobody can verify where a specific value came from. When Adam questions "is the Cameo really 53 jets?", there is no way to trace that value back to the source PDF page or website URL.
**Why it happens:** Provenance tracking feels like overhead during initial data entry. But it is a requirement (ETL-05) and critical for the trust model.
**How to avoid:** Include a `SourceReference` in the schema from day one. Every data file should have a top-level `source_documents` field, and individual specs can optionally reference specific sources.
**Warning signs:** No source_documents field in the model. Source attribution added as an afterthought in a separate file.

### Pitfall 5: Part Numbers as Simple Strings Losing Cross-Reference Power

**What goes wrong:** Part numbers are stored as plain strings ("6500-310"). When the MCP tool needs to answer "which other models use this part?", it has to scan every model file for string matches. Supersession chains ("6500-301 replaced by 6500-310") are not captured.
**Why it happens:** Part numbers look like simple strings. The relational context (fits which models, replaces which parts) is not visible when looking at a single model's data.
**How to avoid:** Use the `PartReference` model. Even for POC, capturing `supersedes` and `fits_models` enables the cross-reference requirement (DATA-02) without a separate lookup table.
**Warning signs:** Part numbers stored as `str` fields. No way to answer "what else does this part fit?" without scanning all files.

## Code Examples

### Complete Spec Category Models (Based on Real Manufacturer Data)

```python
# Source: Manufacturer product pages (Sundance, Hot Spring, Bullfrog)
# Verified against: sundancespas.com, hotspring.com, bullfrogspas.com, patiosplash.com

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from enum import StrEnum
from typing import Literal


# === ENUMS ===

class Manufacturer(StrEnum):
    SUNDANCE = "sundance"
    HOT_SPRING = "hotspring"
    BULLFROG = "bullfrog"

class PumpSpeed(StrEnum):
    ONE_SPEED = "1-speed"
    TWO_SPEED = "2-speed"
    VARIABLE = "variable"

class JetSystemType(StrEnum):
    FIXED = "fixed"                    # Sundance, Hot Spring
    MODULAR_JETPAK = "modular_jetpak"  # Bullfrog JetPak system

class VoltageSpec(StrEnum):
    V120 = "120"
    V240 = "240"


# === SHARED MODELS ===

class PartReference(BaseModel):
    """A part number with supersession and compatibility context."""
    part_number: str
    description: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    fits_models: list[str] = Field(default_factory=list)
    fits_years: str | None = None
    notes: str | None = None

class SourceReference(BaseModel):
    """Provenance tracking for a data point."""
    source_type: Literal["pdf", "website", "manual_entry"]
    url: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    accessed_date: str | None = None
    verified_by: str | None = None
    verified_date: str | None = None

class DimensionsSpec(BaseModel):
    """Physical dimensions of the spa."""
    length_inches: float
    width_inches: float
    height_inches: float
    dry_weight_lbs: float | None = None
    filled_weight_lbs: float | None = None
    water_capacity_gallons: float | None = None


# === CATEGORY 1: JET PUMPS ===

class JetPumpSpec(BaseModel):
    """Specification for a single jet pump position."""
    position: int = Field(ge=1, description="Pump position (1, 2, 3)")
    model_name: str | None = None            # e.g., "Wavemaster 9000", "Wavemaster 9200"
    horsepower_continuous: float             # e.g., 2.5
    horsepower_breakdown: float | None = None  # e.g., 5.2 (breakdown torque HP)
    speed: PumpSpeed
    amperage_max: float | None = None
    frame: str | None = None                 # e.g., "56 Frame"
    voltage: int = 240
    part_number: PartReference | None = None

class JetPumpSpecs(BaseModel):
    """All jet pump specs for a spa model. Models have 1-3 jet pumps."""
    pumps: list[JetPumpSpec] = Field(min_length=1, max_length=4)
    diverter_valves: int | None = None
    total_brake_horsepower: float | None = None  # Bullfrog lists total BHP
    shared_with_series: bool = False


# === CATEGORY 2: CIRCULATION PUMP ===

class CirculationPumpSpec(BaseModel):
    """Dedicated circulation pump specification."""
    model_name: str | None = None            # e.g., "SilentFlo 5000"
    description: str | None = None           # e.g., "Dedicated low-energy circulation"
    is_dedicated: bool = True                # True = separate from jet pumps
    wattage: float | None = None
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 3: SPA PAK (CONTROL BOX) ===

class SpaPakSpec(BaseModel):
    """Spa pak / control box specification."""
    model_name: str                          # e.g., "IQ 2020"
    display_type: str | None = None          # e.g., "Color LCD Touchscreen"
    voltage: int = 240
    amperage: int | None = None              # e.g., 50
    frequency_hz: int = 60
    features: list[str] = Field(default_factory=list)
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 4: TOPSIDE CONTROL PANEL ===

class TopsideControlSpec(BaseModel):
    """Topside control panel specification."""
    model_name: str | None = None            # e.g., "IQ 2020 Color LCD"
    type: str | None = None                  # e.g., "Color touchscreen", "Capacitive touch"
    features: list[str] = Field(default_factory=list)
    smart_connectivity: str | None = None    # e.g., "SmartTub compatible", "WiFi"
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 5: JETS (PART NUMBERS AND QUANTITIES) ===

class JetTypeEntry(BaseModel):
    """A specific jet type and its quantity within the spa."""
    jet_type: str                            # e.g., "Moto-Massage DX", "Fluidix Intelli"
    quantity: int = Field(ge=0)
    zone: str | None = None                  # e.g., "back", "shoulder", "foot", "calf"
    part_number: PartReference | None = None
    description: str | None = None

class JetSpecs(BaseModel):
    """Complete jet specification for a model."""
    total_jet_count: int
    jet_system_type: JetSystemType = JetSystemType.FIXED
    jets_by_type: list[JetTypeEntry] = Field(default_factory=list)
    # Bullfrog-specific: JetPak configuration
    jetpak_count: int | None = None          # Number of JetPak slots (Bullfrog only)
    jetpak_options: int | None = None         # Number of available JetPak types
    therapy_jet_count: int | None = None      # Additional non-JetPak therapy jets
    max_jet_count: int | None = None          # Maximum possible with all JetPak options
    shared_with_series: bool = False


# === CATEGORY 6: HEADRESTS ===

class HeadrestSpec(BaseModel):
    """Specification for headrests/pillows."""
    type: str | None = None                  # e.g., "Adjustable", "Fixed"
    quantity: int | None = None
    part_number: PartReference | None = None
    description: str | None = None

class HeadrestSpecs(BaseModel):
    """All headrest specifications for a model."""
    headrests: list[HeadrestSpec] = Field(default_factory=list)
    shared_with_series: bool = False


# === CATEGORY 7: FILTER CARTRIDGE ===

class FilterSpec(BaseModel):
    """Specification for a filter cartridge."""
    system_name: str | None = None           # e.g., "MicroClean Ultra II", "Tri-X", "Simplicity"
    filter_type: str | None = None           # e.g., "Cartridge", "Tri-X Ceramic", "Flat filter"
    filtration_area_sqft: float | None = None # e.g., 130.0, 325.0
    quantity: int | None = None              # Number of filter cartridges
    description: str | None = None           # e.g., "dual interlocking cartridge filters"
    no_bypass: bool | None = None            # Hot Spring "100% No-Bypass" feature
    part_number: PartReference | None = None

class FilterSpecs(BaseModel):
    """All filter specifications for a model."""
    filters: list[FilterSpec] = Field(min_length=1)
    shared_with_series: bool = False


# === CATEGORY 8: HEATER ELEMENT ===

class HeaterSpec(BaseModel):
    """Heater element specification."""
    model_name: str | None = None            # e.g., "Smart Heater", "No-Fault"
    wattage: int | None = None               # e.g., 5500, 4000
    voltage: int = 240
    material: str | None = None              # e.g., "Titanium" (Hot Spring No-Fault)
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 9: LIGHTING ===

class LightSpec(BaseModel):
    """Specification for a single light/LED."""
    location: str                            # e.g., "interior", "exterior", "waterfall", "footwell"
    type: str                                # e.g., "LED", "Multicolor LED", "SunGlow LED"
    description: str | None = None
    part_number: PartReference | None = None

class LightingSpecs(BaseModel):
    """All lighting specifications for a model."""
    lights: list[LightSpec] = Field(default_factory=list)
    water_feature: str | None = None         # e.g., "BellaFontana 3 arcs", "Premium waterfall"
    shared_with_series: bool = False


# === CATEGORY 10: COVER ===

class CoverSpec(BaseModel):
    """Spa cover specification."""
    model_name: str | None = None            # e.g., "WeatherPro", "Patio Performance"
    thickness: str | None = None             # e.g., '4" Tapered Core'
    material: str | None = None
    features: list[str] = Field(default_factory=list)  # e.g., "Hinge Seal", "Smart Sensor"
    # Cover dimensions (may differ from spa dimensions due to overhang)
    length_inches: float | None = None
    width_inches: float | None = None
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === TOP-LEVEL MODEL ===

class SpaModel(BaseModel):
    """Complete specification for a single spa model.

    This is the canonical data structure that both ETL (writes to)
    and MCP tools (reads from) use. Each JSON data file contains
    one SpaModel instance.
    """
    # Identity
    manufacturer: Manufacturer
    series: str
    model_name: str
    year: int
    seating_capacity: int

    # 10 Spec Categories
    jet_pumps: JetPumpSpecs
    circulation_pump: CirculationPumpSpec | None = None
    spa_pak: SpaPakSpec
    topside_control: TopsideControlSpec
    jets: JetSpecs
    headrests: HeadrestSpecs
    filters: FilterSpecs
    heater: HeaterSpec
    lighting: LightingSpecs
    cover: CoverSpec

    # Physical dimensions
    dimensions: DimensionsSpec

    # Electrical
    voltage: int = 240
    amperage: int | None = None
    requires_gfci: bool = True

    # Metadata
    compatibility_notes: list[str] = Field(default_factory=list)
    source_documents: list[SourceReference] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Canonical spa model specification for Dex knowledge system"
        }
    )
```

### JSON Schema Export

```python
# Source: Pydantic docs - https://docs.pydantic.dev/latest/concepts/json_schema/
import json
from pathlib import Path

def export_json_schema(output_path: Path) -> None:
    """Export Pydantic schema as JSON Schema file."""
    schema = SpaModel.model_json_schema(mode="serialization")
    output_path.write_text(json.dumps(schema, indent=2))

def export_multi_model_schema(output_path: Path) -> None:
    """Export schema for all models with shared $defs."""
    from pydantic import TypeAdapter
    from pydantic.json_schema import models_json_schema

    _, schema = models_json_schema(
        [(SpaModel, "validation")],
        title="Dex Spa Model Schema",
    )
    output_path.write_text(json.dumps(schema, indent=2))
```

### Pilot Model Data (Sundance Aspen - Based on Real Data)

```python
# Source: sundancespas.com/en-us/aspen-880-series/Aspen.html
# Verified fields from actual product page

aspen_data = {
    "manufacturer": "sundance",
    "series": "880 Series",
    "model_name": "Aspen",
    "year": 2026,
    "seating_capacity": 7,
    "jet_pumps": {
        "pumps": [
            {
                "position": 1,
                "horsepower_continuous": 2.5,
                "speed": "1-speed",
                "amperage_max": 11.3,
                "frame": "56 Frame",
                "voltage": 240
            },
            {
                "position": 2,
                "horsepower_continuous": 2.5,
                "speed": "1-speed",
                "amperage_max": 11.3,
                "frame": "56 Frame",
                "voltage": 240
            }
        ],
        "diverter_valves": 2,
        "shared_with_series": False  # Smaller 880 models may have 1 pump
    },
    "circulation_pump": {
        "is_dedicated": True,
        "description": "Dedicated circulation pump",
        "shared_with_series": True
    },
    "spa_pak": {
        "model_name": "Advanced Touch Control",
        "display_type": "Color touchscreen",
        "voltage": 240,
        "frequency_hz": 60,
        "features": ["SmartTub compatible"],
        "shared_with_series": True
    },
    "topside_control": {
        "type": "Color touchscreen",
        "features": ["Icon-driven menus", "Glowing color display"],
        "smart_connectivity": "SmartTub System (optional)",
        "shared_with_series": True
    },
    "jets": {
        "total_jet_count": 66,
        "jet_system_type": "fixed",
        "jets_by_type": [
            {"jet_type": "Fluidix", "quantity": 66, "zone": "full-body"}
        ],
        "shared_with_series": False  # Jet count varies by model
    },
    "headrests": {
        "headrests": [],
        "shared_with_series": False
    },
    "filters": {
        "filters": [
            {
                "system_name": "MicroClean Ultra II",
                "filter_type": "Cartridge",
                "filtration_area_sqft": 130.0,
                "quantity": 2,
                "description": "Dual interlocking cartridge filters"
            }
        ],
        "shared_with_series": True  # All 880 models use same filter system
    },
    "heater": {
        "model_name": "Smart Heater",
        "wattage": 5500,
        "voltage": 240,
        "part_number": {
            "part_number": "6500-310",
            "supersedes": "6500-301",
            "fits_years": "2000+"
        },
        "shared_with_series": True  # Same heater across 880 Series
    },
    "lighting": {
        "lights": [
            {"location": "interior", "type": "Multicolor SunGlow LED"},
            {"location": "waterfall", "type": "SunGlow LED"},
            {"location": "footwell", "type": "SunGlow LED"},
            {"location": "grab_bar", "type": "Backlit LED"},
            {"location": "exterior", "type": "LED accent"}
        ],
        "shared_with_series": True
    },
    "cover": {
        "features": ["Energy Efficiency package available"],
        "shared_with_series": False  # Cover dimensions are model-specific
    },
    "dimensions": {
        "length_inches": 110.0,
        "width_inches": 89.0,
        "height_inches": 40.0,
        "dry_weight_lbs": 1240.0,
        "water_capacity_gallons": 505.0
    },
    "voltage": 240,
    "amperage": 50,
    "source_documents": [
        {
            "source_type": "website",
            "url": "https://www.sundancespas.com/en-us/aspen-880-series/Aspen.html",
            "accessed_date": "2026-02-15"
        }
    ]
}
```

## Real-World Data Field Mapping

### Category-by-Category Field Analysis (from Manufacturer Data)

The following tables document the actual fields found on manufacturer product pages and parts supplier sites. This is the evidence base for schema design.

#### Category 1: Jet Pump Model/HP

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Pump count | 2 (Aspen, Optima, Cameo) | 2 (Grandee: 9000+9200) | 2-3 (M6/M7: 2, M8/M9: 3) |
| Model name | Not branded | Wavemaster 9000/9200 | Not branded |
| HP continuous | 2.5 | 2.5 | Not listed (total BHP only) |
| HP breakdown | Not listed | 5.2 | Not listed |
| Speed | 1-speed | 1-speed / 2-speed (varies) | 2-speed |
| Amperage | 11.3A | Not listed on page | Not listed |
| Frame | 56 Frame | Not listed | Not listed |
| Voltage | 240 | 230 | 240 |
| Total BHP | Not used | Not used | 14.40 (M9) |

**Schema implication:** Pump spec model needs both per-pump fields AND a total_brake_horsepower field for Bullfrog.

#### Category 2: Circulation Pump

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Has dedicated circ pump | Yes | Yes | Yes |
| Model name | Not listed | SilentFlo 5000 | Not branded |
| Wattage | Not listed | "Less than 40W light bulb" | Not listed |

**Schema implication:** Simple model with model_name and optional wattage. All three have dedicated circulation pumps.

#### Category 3: Spa Pak (Control Box)

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Model name | "Advanced Touch Control" | "IQ 2020" | "M Series Touch Screen" |
| Display type | Color touchscreen | Color LCD Touchscreen | Capacitive touch |
| Voltage | 240V | 230V | 240V |
| Amperage | 40/50/60A options | 50A | 60A |
| Shared across series | Yes (all 880) | Yes (all Highlife) | Yes (all M Series) |

**Schema implication:** Series-level shared spec. Include `shared_with_series: true`.

#### Category 4: Topside Control Panel

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Type | Color touchscreen | Color LCD | Capacitive touch |
| Smart connectivity | SmartTub (optional) | FreshWater IQ Ready | Not listed |
| Part number | Not listed | 77433 | Not listed |

**Schema implication:** Often merged with spa pak in manufacturer listings. Keep as separate category per requirements but allow overlap.

#### Category 5: Jets (Part Numbers and Quantities)

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Total count | Varies: 66 (Aspen), 49 (Optima), 53 (Cameo) | 49 (Grandee), 39 (Envoy/Aria), 42 (Vanguard) | 29 standard + up to 323 max (M9) |
| Jet types listed | Fluidix (generic) | 7 types: Moto-Massage DX, SoothingStream, JetStream, Rotary Hydromassage, Directional Hydromassage, HydroStream, Directional Precision | JetPak types (16 options) + therapy jets |
| Per-type breakdown | Not on product page | Yes (Grandee: 2+2+2+3+2+10+26) | JetPak count + therapy jet count |
| Part numbers | 6541-102, 6541-560, 6541-172, 6541-010 (from parts suppliers) | 73307 (Moto-Massage assembly) | Not found |
| Zones | "Full-body Fluidix Seats" | Back, neck, shoulders, calves, feet | Per JetPak position |

**Schema implication:** This is the most complex category. Needs `jets_by_type` list for Hot Spring, `jet_system_type` enum for Bullfrog distinction, and per-type part numbers. Sundance requires ETL from parts suppliers for detailed breakdown.

#### Category 6: Headrests

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Type | Not listed on product page | Not detailed | Adjustable (standard on premium seats) |
| Part number | Not found | 77228 / 1411501 (2014-current) | Not found |
| Quantity | Not listed | Not listed | Not listed |

**Schema implication:** Sparse data category. Schema must handle mostly-null state. Use optional fields throughout.

#### Category 7: Filter Cartridge

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| System name | MicroClean Ultra II | Tri-X | Simplicity |
| Filter type | Cartridge | Ceramic (Tri-X) | Flat filter |
| Area | 130 sq ft | 325 sq ft | Not listed |
| Quantity | 2 (interlocking) | Model-dependent | Not listed |
| No-bypass | Not stated | Yes (100% No-Bypass) | Not stated |
| Part number | Not found | 73250 (Tri-X) | Not found |
| Shared | Yes (all 880) | Yes (all Highlife) | Yes (all M Series) |

**Schema implication:** Simple model but with manufacturer-specific features (no_bypass boolean for Hot Spring).

#### Category 8: Heater Element

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Model name | Smart Heater | No-Fault | Not listed |
| Wattage | 5500W | 4000W | Not listed |
| Voltage | 240V | 230V | Not listed |
| Material | Not listed | Titanium | Not listed |
| Part number | 6500-310 (supersedes 6500-301) | Not found | Not found |
| Shared | Yes (all 880) | Yes (all Highlife) | Likely yes |

**Schema implication:** Include material field for Hot Spring titanium. Supersession data critical for Sundance.

#### Category 9: Lighting

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Interior | Multicolor SunGlow LED | Customizable LED Zone Lighting | Premium LED surround |
| Exterior | LED accent | Multi-Color LED with Timer | Rim lighting |
| Waterfall | SunGlow LED | BellaFontana (3 illuminated arcs) | Premium waterfall |
| Footwell | SunGlow LED | Not listed | Not listed |

**Schema implication:** List of light specs by location. Water feature as separate field.

#### Category 10: Cover

| Field | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|-------|-------------|--------------------|--------------------|
| Model name | Not listed | WeatherPro | Patio Performance |
| Thickness | Not listed | 4" Tapered Core | Not listed |
| Features | Energy Efficiency package | Hinge Seal | Smart sensor technology |
| Dimensions | Model-specific (matches spa dims) | Model-specific | Model-specific |

**Schema implication:** Cover dimensions differ from spa dimensions (overhang). Separate length/width fields needed.

## Series-Level Shared Specs Summary

Understanding which specs are shared at series level is critical for data consistency and query response enrichment ("this spec is the same across all 880 Series models").

| Spec Category | Sundance 880 | Hot Spring Highlife | Bullfrog M Series |
|--------------|-------------|--------------------|--------------------|
| Jet pumps | Model-specific (count varies) | Model-specific (models/HP vary) | Model-specific (2 vs 3 pumps) |
| Circulation pump | Shared (all have dedicated) | Shared (SilentFlo 5000) | Shared (all have dedicated) |
| Spa pak | Shared | Shared (IQ 2020) | Shared (M Series touch) |
| Topside control | Shared | Shared | Shared |
| Jets | Model-specific (count varies) | Model-specific (count/types vary) | Model-specific (JetPak count varies) |
| Headrests | Unknown | Shared part number (77228) | Model-specific |
| Filters | Shared (MicroClean Ultra II, 130sqft) | Shared (Tri-X) | Shared (Simplicity) |
| Heater | Shared (Smart Heater 5500W) | Shared (No-Fault 4000W) | Likely shared |
| Lighting | Shared (SunGlow LED system) | Model-specific (zone count) | Shared |
| Cover | Model-specific (dimensions differ) | Model-specific (dimensions differ) | Model-specific (dimensions differ) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `Optional[T]` implicit None default | Pydantic v2 requires explicit `T \| None = None` | v2 (2023) | All optional fields must have explicit None default. No implicit defaults. |
| Pydantic v1 `schema()` method | Pydantic v2 `model_json_schema()` method | v2 (2023) | Different method name and return format. Use v2 API exclusively. |
| `use_enum_values = True` in Config | Default behavior in v2 | v2 (2023) | No configuration needed for enum value serialization. |
| `json()` method for serialization | `model_dump_json()` method | v2 (2023) | Use v2 method names throughout. |
| `parse_obj()` / `parse_raw()` | `model_validate()` / `model_validate_json()` | v2 (2023) | Use v2 method names throughout. |

**Deprecated/outdated:**
- Pydantic v1 API: All v1 methods (`.schema()`, `.json()`, `.parse_obj()`) are removed in v2. Do not use.
- `Optional[T]` without `= None`: In v2, `Optional[T]` does NOT set a default of None. Must write `T | None = None` explicitly.

## Open Questions

1. **Exact jet type breakdown for Sundance models**
   - What we know: Sundance lists "Fluidix" jets generically. Parts suppliers show specific types (Fluidix Intelli, Fluidix ST, Fluidix Reflex) with part numbers.
   - What's unclear: Which specific Fluidix jet types are in which positions for each 880 model. Product pages do not break this down.
   - Recommendation: Schema should support per-type breakdown. ETL in Phase 2/3 should extract from parts supplier sites and owner's manuals, not just manufacturer marketing pages.

2. **Bullfrog individual pump HP ratings**
   - What we know: Bullfrog lists total BHP (14.40 for M9 with 3 pumps) but not individual pump HP.
   - What's unclear: Whether all 3 pumps are identical or if there are different sizes.
   - Recommendation: Schema has per-pump HP as optional field, plus total_brake_horsepower as a separate field. ETL can populate whichever is available.

3. **Cover dimensions vs spa dimensions**
   - What we know: Cover dimensions are not listed on any manufacturer product page. Covers have overhang beyond spa shell dimensions.
   - What's unclear: Whether cover dimensions can be derived from spa dimensions or need separate data.
   - Recommendation: Include both spa dimensions (in `DimensionsSpec`) and cover dimensions (in `CoverSpec`) as separate fields. Populate cover dimensions from aftermarket cover supplier data if manufacturer data is not available.

4. **Headrest details for most models**
   - What we know: Hot Spring headrest part number 77228 fits 2014-current Highlife models. Bullfrog lists "adjustable" headrests. Sundance headrest data not found.
   - What's unclear: Exact headrest quantities, positions, and part numbers per model.
   - Recommendation: Schema supports list of headrest specs. Accept that this category may be sparse initially. ETL should target parts supplier sites for this data.

5. **Vistamar and Capris models**
   - What we know: These are listed in the POC scope but were not found on the current Sundance website.
   - What's unclear: Whether these models are current 2026 models or have been renamed/discontinued.
   - Recommendation: Flag for verification with Spaparts team. Schema is flexible enough to handle them if they exist. If discontinued, reduce POC scope from 19 to 17 models.

## Sources

### Primary (HIGH confidence)
- [Sundance Aspen Product Page](https://www.sundancespas.com/en-us/aspen-880-series/Aspen.html) -- Pump, jet, filter, dimension specs extracted
- [Sundance Optima Product Page](https://www.sundancespas.com/en-us/optima-880-series/Optima.html) -- Pump, jet, filter, dimension specs extracted
- [Sundance Cameo Product Page](https://www.sundancespas.com/en-us/cameo-880-series/Cameo.html) -- Pump, jet, filter, dimension specs extracted
- [Hot Spring Grandee Product Page](https://www.hotspring.com/shop/highlife/grandee) -- Full spec sheet with pump models, jet breakdown, heater, filter
- [Bullfrog M9 Specs (Patio Splash)](https://patiosplash.com/bullfrog-spas/m-series/m9/) -- Pump count, JetPak details, dimensions, electrical
- [Bullfrog M7 Specs (Patio Splash)](https://patiosplash.com/bullfrog-spas/m-series/m7/) -- Pump count, JetPak details, dimensions
- [Pydantic JSON Schema Docs](https://docs.pydantic.dev/latest/concepts/json_schema/) -- model_json_schema(), models_json_schema(), customization
- [Pydantic Unions Docs](https://docs.pydantic.dev/latest/concepts/unions/) -- Discriminated unions, Literal types, best practices
- [Pydantic Models Docs](https://docs.pydantic.dev/latest/concepts/models/) -- Optional fields, validators, ConfigDict

### Secondary (MEDIUM confidence)
- [SpaStore Sundance Parts](https://www.spastore.com/sundance-spa-parts/) -- Part number format, compatibility patterns, year ranges
- [Hot Spring Supply Moto-Massage 73307](https://hotspringsupply.com/products/moto-massage-jet-assy-warm-grey) -- Jet assembly part number
- [Amazon Hot Spring Pillow 77228](https://www.amazon.com/77228-1411501-Replacement-Compatible-Collection/dp/B0FPF95RZT) -- Headrest part number, compatibility 2014-current
- [Sundance Smart Heater 6500-310](https://www.spaandpoolsource.com/6500-310-Sundance-spas-Smart-Heater.aspx) -- Heater part number, supersession from 6500-301
- [Sundance Fluidix Intelli-Jet 6541-102](https://spaandpoolstore.com/6541-102-sundance-spas-fluidix-intelli-jet-880-series-mid-2009/) -- Jet part number, supersession from 6000-315
- [Hot Spring Tri-X Filter 73250](https://shop.spaandsauna.com/products/hot-spring-tri-x-filter) -- Filter part number
- [Arnold Pool Highlife Specs](https://www.arnoldpoolcompany.com/spas/hot-spring-spas-highlife-collection/) -- Model comparison dimensions
- [Bullfrog M Series Overview](https://wetpoolsandspas.net/spas/bullfrog-m-series/) -- M6/M7/M8 pump count comparison

### Tertiary (LOW confidence)
- Bullfrog heater and filter part numbers: Not found in any source. Likely available only through dealer documentation.
- Sundance headrest part numbers: Not found. May need direct extraction from owner's manual PDFs.
- Cover dimensions: Not found for any manufacturer. May require aftermarket cover supplier data or direct measurement.

## Metadata

**Confidence breakdown:**
- Standard stack (Pydantic v2): HIGH -- Official documentation reviewed, API methods verified
- Architecture (schema patterns): HIGH -- Driven by real manufacturer data from product pages, cross-validated across 3 manufacturers
- Field definitions per category: MEDIUM to HIGH -- Based on actual product page data, but some fields (headrests, covers, Bullfrog heater) have sparse data
- Pitfalls: HIGH -- Driven by observed data complexity and domain-specific issues (supersession, series sharing, manufacturer differences)
- Cross-reference patterns: MEDIUM -- Part number relationships observed but full supersession chains not yet mapped

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days -- schema patterns are stable, manufacturer specs update annually)
