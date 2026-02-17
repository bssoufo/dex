"""Run the Dex MCP data server.

Usage:
    python -m backend.src.mcp

Starts the MCP server using STDIO transport for JSON-RPC communication.
STDIO uses stdout for JSON-RPC, so all application logging goes to stderr.
"""

import logging
import sys

# Configure backend.* loggers for the MCP subprocess.
# STDIO transport reserves stdout for JSON-RPC -- logs MUST go to stderr.
_pkg = logging.getLogger("backend")
_pkg.setLevel(logging.INFO)
_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
_pkg.addHandler(_h)
_pkg.propagate = False

from backend.src.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
