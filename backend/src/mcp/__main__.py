"""Run the Dex MCP data server.

Usage:
    python -m backend.src.mcp

Starts the MCP server using STDIO transport for JSON-RPC communication.
"""

from backend.src.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
