"""Request and response models for the Dex API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming question from the user."""

    question: str = Field(..., min_length=1, description="Natural language question about spa specs")


class QueryResponse(BaseModel):
    """Agent answer returned to the user."""

    answer: str = Field(..., description="Agent's response to the question")
    tool_calls: list[dict] | None = Field(
        default=None, description="Tool calls made during processing (for debugging)"
    )
