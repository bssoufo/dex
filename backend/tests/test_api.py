"""Tests for the Dex FastAPI application.

Validates API route registration, request/response models, and
the health endpoint. Does NOT test real agent invocation (that
requires MCP subprocess + Gemini API and belongs in integration tests).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.src.api.app import app
from backend.src.api.models import QueryRequest, QueryResponse


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    """Verify that expected routes are registered on the FastAPI app."""

    def _get_route_map(self) -> dict[str, set[str]]:
        """Build a {path: {methods}} mapping from app routes."""
        route_map: dict[str, set[str]] = {}
        for route in app.routes:
            if hasattr(route, "methods"):
                route_map[route.path] = route.methods
        return route_map

    def test_query_endpoint_exists(self):
        route_map = self._get_route_map()
        assert "/query" in route_map, "/query route not registered"
        assert "POST" in route_map["/query"], "/query should accept POST"

    def test_health_endpoint_exists(self):
        route_map = self._get_route_map()
        assert "/health" in route_map, "/health route not registered"
        assert "GET" in route_map["/health"], "/health should accept GET"


# ---------------------------------------------------------------------------
# Request / Response model tests
# ---------------------------------------------------------------------------


class TestQueryRequestModel:
    """Validate QueryRequest Pydantic model."""

    def test_valid_question(self):
        req = QueryRequest(question="What pumps does the Cameo have?")
        assert req.question == "What pumps does the Cameo have?"

    def test_missing_question_raises(self):
        with pytest.raises(ValidationError):
            QueryRequest()  # type: ignore[call-arg]

    def test_empty_question_raises(self):
        with pytest.raises(ValidationError):
            QueryRequest(question="")

    def test_whitespace_only_question(self):
        # A single space passes min_length=1; that is acceptable
        req = QueryRequest(question=" ")
        assert req.question == " "


class TestQueryResponseModel:
    """Validate QueryResponse Pydantic model."""

    def test_basic_response(self):
        resp = QueryResponse(answer="The Cameo has 3 pumps.")
        assert resp.answer == "The Cameo has 3 pumps."
        assert resp.tool_calls is None

    def test_response_with_tool_calls(self):
        calls = [{"tool": "get_spec_category", "content": "..."}]
        resp = QueryResponse(answer="Answer", tool_calls=calls)
        assert resp.tool_calls == calls

    def test_serialization(self):
        resp = QueryResponse(answer="test")
        data = resp.model_dump()
        assert data == {"answer": "test", "tool_calls": None}


# ---------------------------------------------------------------------------
# Health endpoint test (via httpx AsyncClient)
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test the /health endpoint without lifespan (agent not started)."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        # agent_ready is false because lifespan does not run with TestClient
        assert body["agent_ready"] is False
