"""Spa specification category models and top-level SpaModel.

Contains the 10 spec category models (some with container/item pairs)
and the SpaModel that composes them all. This is the canonical data
structure that ETL writes to and MCP tools read from.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import JetSystemType, Manufacturer, PumpSpeed
from .parts import DimensionsSpec, PartReference, SourceReference


# === CATEGORY 1: JET PUMPS ===


class JetPumpSpec(BaseModel):
    """Specification for a single jet pump position."""

    position: int = Field(
        ge=1,
        description="Pump position number (1, 2, 3, etc.)",
    )
    model_name: str | None = None
    horsepower_continuous: float = Field(
        description="Continuous-duty horsepower rating",
    )
    horsepower_breakdown: float | None = None
    speed: PumpSpeed
    amperage_max: float | None = None
    frame: str | None = None
    voltage: int = 240
    part_number: PartReference | None = None


class JetPumpSpecs(BaseModel):
    """All jet pump specs for a spa model. Models have 1-4 jet pumps."""

    pumps: list[JetPumpSpec] = Field(min_length=1, max_length=4)
    diverter_valves: int | None = None
    total_brake_horsepower: float | None = None
    shared_with_series: bool = False


# === CATEGORY 2: CIRCULATION PUMP ===


class CirculationPumpSpec(BaseModel):
    """Dedicated circulation pump specification."""

    model_name: str | None = None
    description: str | None = None
    is_dedicated: bool = True
    wattage: float | None = None
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 3: SPA PAK (CONTROL BOX) ===


class SpaPakSpec(BaseModel):
    """Spa pak / control box specification."""

    model_name: str
    display_type: str | None = None
    voltage: int = 240
    amperage: int | None = None
    frequency_hz: int = 60
    features: list[str] = Field(default_factory=list)
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 4: TOPSIDE CONTROL PANEL ===


class TopsideControlSpec(BaseModel):
    """Topside control panel specification."""

    model_name: str | None = None
    type: str | None = None
    features: list[str] = Field(default_factory=list)
    smart_connectivity: str | None = None
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 5: JETS (PART NUMBERS AND QUANTITIES) ===


class JetTypeEntry(BaseModel):
    """A specific jet type and its quantity within the spa."""

    jet_type: str
    quantity: int = Field(ge=0)
    zone: str | None = None
    part_number: PartReference | None = None
    description: str | None = None


class JetSpecs(BaseModel):
    """Complete jet specification for a model.

    Accommodates both fixed-jet systems (Sundance, Hot Spring) via
    jets_by_type, and Bullfrog's modular JetPak system via
    jetpak_count and jetpak_options fields.
    """

    total_jet_count: int = Field(
        description="Total number of jets in the spa",
    )
    jet_system_type: JetSystemType = JetSystemType.FIXED
    jets_by_type: list[JetTypeEntry] = Field(default_factory=list)
    jetpak_count: int | None = None
    jetpak_options: int | None = None
    therapy_jet_count: int | None = None
    max_jet_count: int | None = None
    shared_with_series: bool = False


# === CATEGORY 6: HEADRESTS ===


class HeadrestSpec(BaseModel):
    """Specification for a single headrest/pillow type."""

    type: str | None = None
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

    system_name: str | None = None
    filter_type: str | None = None
    filtration_area_sqft: float | None = None
    quantity: int | None = None
    description: str | None = None
    no_bypass: bool | None = None
    part_number: PartReference | None = None


class FilterSpecs(BaseModel):
    """All filter specifications for a model."""

    filters: list[FilterSpec] = Field(min_length=1)
    shared_with_series: bool = False


# === CATEGORY 8: HEATER ELEMENT ===


class HeaterSpec(BaseModel):
    """Heater element specification."""

    model_name: str | None = None
    wattage: int | None = None
    voltage: int = 240
    material: str | None = None
    part_number: PartReference | None = None
    shared_with_series: bool = False


# === CATEGORY 9: LIGHTING ===


class LightSpec(BaseModel):
    """Specification for a single light/LED."""

    location: str
    type: str
    description: str | None = None
    part_number: PartReference | None = None


class LightingSpecs(BaseModel):
    """All lighting specifications for a model."""

    lights: list[LightSpec] = Field(default_factory=list)
    water_feature: str | None = None
    shared_with_series: bool = False


# === CATEGORY 10: COVER ===


class CoverSpec(BaseModel):
    """Spa cover specification."""

    model_name: str | None = None
    thickness: str | None = None
    material: str | None = None
    features: list[str] = Field(default_factory=list)
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

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Canonical spa model specification for Dex knowledge system"
        }
    )

    # Identity
    manufacturer: Manufacturer = Field(
        description="Spa manufacturer (sundance, hotspring, bullfrog)",
    )
    series: str
    model_name: str = Field(
        description="Model name within the series (e.g. 'Aspen', 'Grandee', 'M9')",
    )
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
