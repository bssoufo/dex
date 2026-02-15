"""JSON Schema export utility for the Dex spa specification schema.

Generates a JSON Schema file from the Pydantic SpaModel definition.
This enables validation of spa model data files outside of Python/Pydantic,
for example in CI pipelines, documentation tools, or other language runtimes.

Usage:
    python -m src.schema.export
"""

from __future__ import annotations

import json
from pathlib import Path


def export_json_schema(output_path: Path) -> dict:
    """Export SpaModel as a JSON Schema file.

    Args:
        output_path: File path to write the JSON Schema to.

    Returns:
        The generated JSON Schema as a dictionary.
    """
    from .models import SpaModel

    schema = SpaModel.model_json_schema(mode="serialization")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    return schema


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "schemas" / "spa-model.schema.json"


if __name__ == "__main__":
    schema = export_json_schema(DEFAULT_OUTPUT_PATH)
    props = len(schema.get("properties", {}))
    defs = len(schema.get("$defs", {}))
    print(f"Exported JSON Schema to {DEFAULT_OUTPUT_PATH}")
    print(f"  {props} top-level properties, {defs} definitions")
