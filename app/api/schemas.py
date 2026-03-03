from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=512, ge=1, le=4096)

    @model_validator(mode="after")
    def validate_messages(self) -> ChatCompletionRequest:
        if not self.messages:
            raise ValueError("messages must not be empty")
        return self


class AttemptLogResponse(BaseModel):
    attempt_id: str
    attempt_index: int
    candidate_model: str
    actual_model: str | None
    provider_name: str
    status: str
    failure_kind: str
    latency_ms: int
    http_status: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime


class RequestSummaryResponse(BaseModel):
    request_id: str
    route_policy: str
    requested_model: str
    resolved_model: str | None
    status: str
    stream: bool
    cache_status: str
    attempt_count: int
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    started_at: datetime
    completed_at: datetime


class RequestDetailResponse(RequestSummaryResponse):
    error_code: str | None
    error_message: str | None
    budget_reason: str | None
    request_body_redacted: dict[str, Any] | None
    response_body_redacted: dict[str, Any] | None
    attempts: list[AttemptLogResponse]
