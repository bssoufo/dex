"""Allow running the verify package as a module.

Usage:
    uv run python -m backend.src.etl.verify
"""

from .cli import main

main()
