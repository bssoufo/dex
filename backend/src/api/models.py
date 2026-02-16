"""Request and response models for the Dex API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Incoming question from the user."""

    question: str = Field(..., min_length=1, description="Natural language question about spa specs")
    conversation_id: str | None = Field(
        default=None,
        description="Session ID for multi-turn conversation. Omit to start new conversation.",
    )


class QueryResponse(BaseModel):
    """Agent answer returned to the user."""

    answer: str = Field(..., description="Agent's response to the question")
    conversation_id: str = Field(
        ...,
        description="Session ID -- return this in follow-up requests to continue the conversation",
    )
    tool_calls: list[dict] | None = Field(
        default=None, description="Tool calls made during processing (for debugging)"
    )
    validation_warnings: list[str] | None = Field(
        default=None, description="Validator warnings about response quality"
    )
