"""Dex MCP data server package.

Exports the FastMCP server instance for use by the entry point
and test harness.
"""

from backend.src.mcp.server import mcp

__all__ = ["mcp"]
