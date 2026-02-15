"""Writes validated SpaModel instances to JSON files.

Handles both production output (validated SpaModel -> JSON) and debug
output (raw extraction dict -> RAW.json) for failed validations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import DATA_OUTPUT_DIR

if TYPE_CHECKING:
    from ...schema.models import SpaModel


def _slugify(name: str) -> str:
    """Convert a series/model name to a filesystem-safe slug.

    Examples:
        ``"880 Series"``      -> ``"880-series"``
        ``"Highlife Collection"`` -> ``"highlife-collection"``
        ``"Jetsetter LX"``    -> ``"jetsetter-lx"``
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def write_model_json(
    spa_model: SpaModel,
    output_dir: Path | None = None,
) -> Path:
    """Serialize a validated SpaModel to a JSON file.

    Args:
        spa_model: A fully validated ``SpaModel`` instance.
        output_dir: Override directory.  Defaults to
            ``DATA_OUTPUT_DIR / {manufacturer} / {series_slug}``.

    Returns:
        Path to the written JSON file.
    """
    if output_dir is None:
        series_slug = _slugify(spa_model.series)
        output_dir = (
            DATA_OUTPUT_DIR
            / str(spa_model.manufacturer)
            / series_slug
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_slugify(spa_model.model_name)}-{spa_model.year}.json"
    file_path = output_dir / filename

    data = spa_model.model_dump()
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    size = file_path.stat().st_size
    print(f"Wrote {file_path} ({size} bytes)")
    return file_path


def write_raw_json(
    model_name: str,
    year: int,
    raw_data: dict,
    output_dir: Path,
) -> Path:
    """Write a raw extraction dict for debugging failed validations.

    Saves the pre-schema-mapping data so developers can inspect what
    Claude returned before Pydantic rejected it.

    Args:
        model_name: Spa model name (e.g. ``"Aspen"``).
        year: Model year.
        raw_data: The raw dict that failed validation.
        output_dir: Directory to write into.

    Returns:
        Path to the written RAW JSON file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_slugify(model_name)}-{year}-RAW.json"
    file_path = output_dir / filename

    file_path.write_text(
        json.dumps(raw_data, indent=2, default=str),
        encoding="utf-8",
    )

    size = file_path.stat().st_size
    print(f"Wrote {file_path} ({size} bytes) [RAW debug]")
    return file_path
