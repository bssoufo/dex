"""Dex single agent package.

Exports the agent factory function for use by the API layer and tests.
"""

from backend.src.agent.graph import create_dex_agent

__all__ = ["create_dex_agent"]
