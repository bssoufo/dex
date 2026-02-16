"""In-memory data store for spa model specifications.

Loads all 19 JSON model files at first access, validates each through
Pydantic SpaModel, and provides O(1) lookup by (manufacturer, model_name).

IMPORTANT: Logging is configured to stderr only. STDIO transport uses
stdout for JSON-RPC protocol messages -- any print/log to stdout corrupts
the protocol.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from backend.src.schema.models import SpaModel

# Configure logging to stderr to avoid corrupting STDIO transport
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the data directory containing manufacturer/series/model.json files
DATA_DIR = Path(__file__).parent.parent / "data"

# Type alias for the store key: (manufacturer_lower, model_name_lower)
ModelKey = tuple[str, str]

# Module-level singleton store
_store: dict[ModelKey, SpaModel] = {}


def load_all_models() -> dict[ModelKey, SpaModel]:
    """Load and validate all JSON model files into memory.

    Globs for *.json under DATA_DIR, parses each with json.loads(),
    validates with SpaModel.model_validate(), and keys by
    (manufacturer.value, model_name.lower()).

    Raises:
        RuntimeError: If the number of loaded models is not exactly 19.
    """
    store: dict[ModelKey, SpaModel] = {}
    json_files = list(DATA_DIR.rglob("*.json"))

    for json_file in json_files:
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        model = SpaModel.model_validate(raw)
        key: ModelKey = (model.manufacturer.value, model.model_name.lower())
        store[key] = model
        logger.debug("Loaded model: %s %s", model.manufacturer.value, model.model_name)

    if len(store) != 19:
        raise RuntimeError(
            f"Expected 19 models but loaded {len(store)}. "
            f"Found {len(json_files)} JSON files in {DATA_DIR}"
        )

    logger.info("Data store initialized: %d models loaded", len(store))
    return store


def get_store() -> dict[ModelKey, SpaModel]:
    """Get or lazily initialize the data store singleton."""
    global _store
    if not _store:
        _store = load_all_models()
    return _store


def get_model(manufacturer: str, model_name: str) -> SpaModel | None:
    """Look up a specific model by manufacturer and model name.

    Case-insensitive on both parameters.

    Args:
        manufacturer: Manufacturer identifier (e.g., "sundance", "hotspring").
        model_name: Model name (e.g., "Aspen", "M9").

    Returns:
        The SpaModel if found, None otherwise.
    """
    return get_store().get((manufacturer.lower(), model_name.lower()))
