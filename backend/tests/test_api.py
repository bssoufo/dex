"""Tests for the Dex FastAPI application.

Validates API route registration, request/response models, the
health endpoint, and the SSE streaming endpoint structure. Does NOT
test real agent invocation (that requires MCP subprocess + Gemini API
and belongs in integration tests).
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.src.api.app import _format_sse, _normalize_content, app
from backend.src.api.models import QueryRequest, QueryResponse


# ---------------------------------------------------------------------------
# CORS middleware tests
# ---------------------------------------------------------------------------


class TestCORSMiddleware:
    """Verify CORS middleware is configured for dev and preview servers."""

    def _get_cors_middleware_config(self):
        """Find CORS middleware config from FastAPI's user_middleware list."""
        from starlette.middleware.cors import CORSMiddleware

        for mw in app.user_middleware:
            if mw.cls is CORSMiddleware:
                return mw.kwargs
        return None

    def test_cors_middleware_registered(self):
        config = self._get_cors_middleware_config()
        assert config is not None, "CORSMiddleware not found in app user_middleware"

    def test_cors_allows_vite_dev_server(self):
        config = self._get_cors_middleware_config()
        assert config is not None
        assert "http://localhost:5173" in config["allow_origins"]

    def test_cors_allows_vite_preview_server(self):
        config = self._get_cors_middleware_config()
        assert config is not None
        assert "http://localhost:4173" in config["allow_origins"]

    @pytest.mark.asyncio
    async def test_cors_preflight_returns_headers(self):
        """OPTIONS preflight request should return CORS headers."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.options(
                "/query/stream",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


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

    def test_stream_endpoint_exists(self):
        route_map = self._get_route_map()
        assert "/query/stream" in route_map, "/query/stream route not registered"
        assert "POST" in route_map["/query/stream"], "/query/stream should accept POST"


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

    def test_request_with_conversation_id(self):
        req = QueryRequest(question="test", conversation_id="session-123")
        assert req.conversation_id == "session-123"

    def test_request_without_conversation_id(self):
        req = QueryRequest(question="test")
        assert req.conversation_id is None


class TestQueryResponseModel:
    """Validate QueryResponse Pydantic model."""

    def test_basic_response(self):
        resp = QueryResponse(answer="The Cameo has 3 pumps.", conversation_id="abc")
        assert resp.answer == "The Cameo has 3 pumps."
        assert resp.conversation_id == "abc"
        assert resp.tool_calls is None
        assert resp.validation_warnings is None

    def test_response_with_tool_calls(self):
        calls = [{"tool": "get_spec_category", "content": "..."}]
        resp = QueryResponse(answer="Answer", conversation_id="xyz", tool_calls=calls)
        assert resp.tool_calls == calls

    def test_serialization(self):
        resp = QueryResponse(answer="test", conversation_id="conv-1")
        data = resp.model_dump()
        assert data == {
            "answer": "test",
            "conversation_id": "conv-1",
            "tool_calls": None,
            "validation_warnings": None,
        }

    def test_response_with_validation_warnings(self):
        resp = QueryResponse(
            answer="Some answer",
            conversation_id="conv-2",
            validation_warnings=["No tool calls detected"],
        )
        assert resp.validation_warnings == ["No tool calls detected"]
        data = resp.model_dump()
        assert data["validation_warnings"] == ["No tool calls detected"]

    def test_response_requires_conversation_id(self):
        with pytest.raises(ValidationError):
            QueryResponse(answer="test")


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


# ---------------------------------------------------------------------------
# Data quality endpoint tests
# ---------------------------------------------------------------------------


class TestDataQualityEndpoint:
    """Verify /data-quality endpoint."""

    @pytest.mark.anyio
    async def test_data_quality_returns_200(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/data-quality")
        assert response.status_code == 200
        body = response.json()
        assert "total_models" in body
        assert body["total_models"] == 19
        assert "average_completeness_pct" in body
        assert body["average_completeness_pct"] > 0
        assert "models" in body
        assert len(body["models"]) == 19

    @pytest.mark.anyio
    async def test_data_quality_model_structure(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/data-quality")
        body = response.json()
        model = body["models"][0]
        assert "manufacturer" in model
        assert "model_name" in model
        assert "completeness_pct" in model
        assert "gaps" in model
        assert "gap_count" in model


# ---------------------------------------------------------------------------
# SSE streaming endpoint tests
# ---------------------------------------------------------------------------


class TestStreamEndpoint:
    """Verify SSE streaming endpoint registration and request model."""

    def test_stream_request_model_compatible(self):
        """The /query/stream endpoint uses the same QueryRequest as /query."""
        # Verify QueryRequest works for stream endpoint (same model, same validation)
        req = QueryRequest(question="What pumps does the Cameo have?")
        assert req.question == "What pumps does the Cameo have?"
        assert req.conversation_id is None

        # With conversation_id
        req2 = QueryRequest(
            question="Tell me more", conversation_id="session-abc"
        )
        assert req2.conversation_id == "session-abc"

        # Empty question still rejected (same min_length=1 validation)
        with pytest.raises(ValidationError):
            QueryRequest(question="")

    @pytest.mark.asyncio
    async def test_stream_returns_503_when_agent_not_initialized(self):
        """Without lifespan, agent is None so /query/stream returns 503."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/query/stream",
                json={"question": "test question"},
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "Agent not initialized"


class TestSSEEventFormat:
    """Verify SSE event formatting helpers used by the stream endpoint."""

    def test_format_sse_metadata_event(self):
        result = _format_sse("metadata", {"conversation_id": "abc-123"})
        assert result == 'event: metadata\ndata: {"conversation_id": "abc-123"}\n\n'

    def test_format_sse_token_event(self):
        result = _format_sse("token", {"content": "Hello world", "node": "specialist"})
        parsed_data = json.loads(result.split("data: ", 1)[1].split("\n")[0])
        assert parsed_data["content"] == "Hello world"
        assert parsed_data["node"] == "specialist"
        assert result.startswith("event: token\n")
        assert result.endswith("\n\n")

    def test_format_sse_done_event(self):
        result = _format_sse("done", {"status": "complete"})
        assert result == 'event: done\ndata: {"status": "complete"}\n\n'

    def test_format_sse_validation_event(self):
        warnings = ["No tool calls detected"]
        result = _format_sse("validation", {"warnings": warnings})
        parsed_data = json.loads(result.split("data: ", 1)[1].split("\n")[0])
        assert parsed_data["warnings"] == ["No tool calls detected"]

    def test_format_sse_validation_event_empty_warnings(self):
        result = _format_sse("validation", {"warnings": []})
        parsed_data = json.loads(result.split("data: ", 1)[1].split("\n")[0])
        assert parsed_data["warnings"] == []

    def test_format_sse_data_is_valid_json(self):
        """All SSE data payloads must be valid JSON."""
        events = [
            _format_sse("metadata", {"conversation_id": "x"}),
            _format_sse("token", {"content": "text", "node": "n"}),
            _format_sse("done", {"status": "complete"}),
            _format_sse("validation", {"warnings": []}),
        ]
        for event_str in events:
            lines = event_str.strip().split("\n")
            data_line = [l for l in lines if l.startswith("data: ")][0]
            json_str = data_line[len("data: "):]
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)

    def test_format_sse_special_characters_in_content(self):
        """SSE with special chars (quotes, newlines) in content is valid JSON."""
        result = _format_sse("token", {"content": 'He said "hello"\nnew line', "node": "s"})
        data_line = [l for l in result.strip().split("\n") if l.startswith("data: ")][0]
        parsed = json.loads(data_line[len("data: "):])
        assert parsed["content"] == 'He said "hello"\nnew line'


class TestNormalizeContent:
    """Verify content normalization for Gemini list-of-blocks format."""

    def test_normalize_string_content(self):
        assert _normalize_content("Hello world") == "Hello world"

    def test_normalize_list_of_text_blocks(self):
        blocks = [{"text": "Part 1"}, {"text": "Part 2"}]
        assert _normalize_content(blocks) == "Part 1\nPart 2"

    def test_normalize_list_of_strings(self):
        blocks = ["Part 1", "Part 2"]
        assert _normalize_content(blocks) == "Part 1\nPart 2"

    def test_normalize_mixed_list(self):
        blocks = [{"text": "From dict"}, "Plain string"]
        assert _normalize_content(blocks) == "From dict\nPlain string"

    def test_normalize_empty_list(self):
        assert _normalize_content([]) == ""

    def test_normalize_non_string_fallback(self):
        assert _normalize_content(42) == "42"
