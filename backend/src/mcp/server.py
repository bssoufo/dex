"""Dex MCP data server -- tool definitions.

Placeholder: full implementation in Task 2.
"""

from fastmcp import FastMCP

mcp = FastMCP(
    name="DexDataServer",
    instructions=(
        "Dex data server provides deterministic lookup of spa technical "
        "specifications. Use get_spec_category for specific data, "
        "get_model_overview for model summaries, and list_models for discovery."
    ),
)
