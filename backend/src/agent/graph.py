"""Dex single agent -- LangGraph ReAct agent with MCP tools.

Creates a ReAct agent graph that connects to the MCP data server
via stdio transport for tool calling. Uses Gemini 2.5 Flash for
deterministic spec lookups with temperature=0.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from backend.src.agent.prompts import SYSTEM_PROMPT

load_dotenv(dotenv_path="backend/.env")


def _create_model() -> ChatGoogleGenerativeAI:
    """Create the Gemini Flash model for tool-calling.

    Returns:
        ChatGoogleGenerativeAI configured with gemini-2.5-flash,
        temperature=0, and max 1024 output tokens.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0,
        max_output_tokens=1024,
    )


def _create_mcp_client() -> MultiServerMCPClient:
    """Create MCP client with stdio transport to Dex data server.

    The command must be run from the project root where PYTHONPATH=.
    is set. On Windows, use "python" (not "python3").

    Returns:
        MultiServerMCPClient configured with the dex_data server.
    """
    return MultiServerMCPClient(
        {
            "dex_data": {
                "command": sys.executable,
                "args": ["-m", "backend.src.mcp"],
                "transport": "stdio",
            }
        }
    )


async def create_dex_agent():
    """Create the Dex ReAct agent connected to MCP tools.

    Instantiates an MCP client, loads tools from the Dex data server,
    and creates a LangGraph ReAct agent with the system prompt.

    The MultiServerMCPClient creates a new stdio session per tool call,
    so no persistent connection management is needed by the caller.

    Returns:
        Tuple of (agent_graph, mcp_client).
    """
    client = _create_mcp_client()
    tools = await client.get_tools()
    model = _create_model()

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent, client
