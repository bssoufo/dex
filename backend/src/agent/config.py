"""Shared configuration for the Dex agent package.

Provides factory functions for the LLM model and MCP client,
extracted from graph.py to avoid duplication across multi-agent
components.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient

# Project root: resolve from this file's location (backend/src/agent/config.py -> root)
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])

load_dotenv(dotenv_path=Path(_PROJECT_ROOT) / "backend" / ".env")


def create_model() -> ChatGoogleGenerativeAI:
    """Create the Gemini Flash model for tool-calling.

    Returns:
        ChatGoogleGenerativeAI configured with gemini-2.5-flash,
        temperature=0, and max 2048 output tokens.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,
        max_output_tokens=2048,
    )


def create_mcp_client() -> MultiServerMCPClient:
    """Create MCP client with stdio transport to Dex data server.

    Sets cwd and PYTHONPATH to the project root so the subprocess
    can always resolve ``backend.src.mcp`` regardless of the caller's
    working directory.

    Returns:
        MultiServerMCPClient configured with the dex_data server.
    """
    # Build env from current process env + explicit PYTHONPATH to project root
    env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT}

    return MultiServerMCPClient(
        {
            "dex_data": {
                "command": sys.executable,
                "args": ["-m", "backend.src.mcp"],
                "transport": "stdio",
                "cwd": _PROJECT_ROOT,
                "env": env,
            }
        }
    )
