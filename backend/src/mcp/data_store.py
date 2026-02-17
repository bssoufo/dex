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
from pathlib import Path

from backend.src.schema.models import SpaModel

# Logger inherits config from the "backend" package logger set up in app.py.
# When running under MCP STDIO transport (not via app.py), the fallback is
# the root logger -- still safe because we never write to stdout here.
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

        # Log each model with quality info so we can verify data freshness
        dq = model.data_quality
        verified = dq.verification_date if dq else "N/A"
        completeness = f"{dq.completeness_pct}%" if dq else "N/A"
        logger.info(
            "  Loaded %-12s %-14s verified=%s completeness=%s",
            model.manufacturer.value,
            model.model_name,
            verified,
            completeness,
        )

    if len(store) != 19:
        raise RuntimeError(
            f"Expected 19 models but loaded {len(store)}. "
            f"Found {len(json_files)} JSON files in {DATA_DIR}"
        )

    logger.info("Data store ready: %d models loaded from %s", len(store), DATA_DIR)
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


def find_cross_references(
    manufacturer: str,
    model_name: str,
    category: str,
    exclude_keys: tuple[str, ...] = ("part_number", "shared_with_series", "model_name"),
) -> list[str]:
    """Find other models from the same manufacturer that share identical specs for a category.

    Compares the target model's category data (minus exclude_keys) against
    all other models from the same manufacturer using dict equality on
    Pydantic model_dump() output.

    Args:
        manufacturer: Manufacturer identifier (e.g., "sundance", "hotspring").
        model_name: Model name (e.g., "Aspen", "M9").
        category: Spec category field name (e.g., "heater", "circulation_pump").
        exclude_keys: Top-level keys to remove before comparison. Defaults to
            part_number (mostly null), shared_with_series (metadata), and
            model_name (always differs).

    Returns:
        Sorted list of model names that share identical specs, empty if
        target not found or category data is None.
    """
    target = get_model(manufacturer, model_name)
    if target is None:
        return []

    target_data = getattr(target, category, None)
    if target_data is None:
        return []

    # Build comparison signature for the target
    target_sig = target_data.model_dump()
    for key in exclude_keys:
        target_sig.pop(key, None)

    # Compare against all other models from the same manufacturer
    store = get_store()
    mfr_lower = manufacturer.lower()
    target_name_lower = model_name.lower()
    matches: list[str] = []

    for (store_mfr, store_model_lower), spa_model in store.items():
        if store_mfr != mfr_lower:
            continue
        if store_model_lower == target_name_lower:
            continue

        other_data = getattr(spa_model, category, None)
        if other_data is None:
            continue

        other_sig = other_data.model_dump()
        for key in exclude_keys:
            other_sig.pop(key, None)

        if other_sig == target_sig:
            matches.append(spa_model.model_name)

    return sorted(matches)
