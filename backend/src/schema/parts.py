"""Shared models for part references, source provenance, and physical dimensions.

These models are used across multiple spec category models and the
top-level SpaModel. They capture the relational complexity of part
numbers (supersession chains, cross-model compatibility) and the
provenance of every data point.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PartReference(BaseModel):
    """A part number with its supersession and compatibility context.

    Part numbers are not simple strings -- they carry information about
    which parts they replace, which parts replace them, and which models
    and years they fit. This context is critical for cross-reference
    queries ("what other models use this part?").
    """

    part_number: str = Field(
        description="Primary part number identifier (e.g. '6500-310', '73250')"
    )
    description: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    fits_models: list[str] = Field(default_factory=list)
    fits_years: str | None = None
    notes: str | None = None


class SourceReference(BaseModel):
    """Provenance tracking for a data point.

    Every spec value in the system must be traceable back to a source
    document (PDF page, website URL, or manual entry). This enables
    verification and trust -- when a technician questions a value,
    we can point to exactly where it came from.
    """

    source_type: Literal["pdf", "website", "manual_entry"]
    url: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    accessed_date: str | None = None
    verified_by: str | None = None
    verified_date: str | None = None


class DataQuality(BaseModel):
    """Verification and quality metadata for a spa model's data.

    Added in Phase 4 as an optional field on SpaModel. Existing JSON files
    without this field still validate because SpaModel.data_quality defaults
    to None.
    """

    verification_date: str | None = None
    verified_by: str | None = None
    not_available_fields: list[str] = Field(default_factory=list)
    anomalies_reviewed: list[dict] = Field(default_factory=list)
    completeness_pct: float | None = None


class DimensionsSpec(BaseModel):
    """Physical dimensions of the spa."""

    length_inches: float
    width_inches: float
    height_inches: float
    dry_weight_lbs: float | None = None
    filled_weight_lbs: float | None = None
    water_capacity_gallons: float | None = None
