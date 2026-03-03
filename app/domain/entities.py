from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain.enums import AttemptStatus, CacheStatus, FailureKind, RequestStatus


@dataclass(frozen=True, slots=True)
class ProjectContext:
    project_id: str
    project_name: str
    default_route_policy: str
    monthly_budget_usd: Decimal
    per_request_cap_usd: Decimal | None
    allow_body_capture: bool
    api_key_id: str


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    model: str
    input_cost_per_1k: Decimal
    output_cost_per_1k: Decimal


@dataclass(frozen=True, slots=True)
class RoutePlan:
    policy_name: str
    requested_model: str
    candidates: tuple[RouteCandidate, ...]
    retry_on: frozenset[str]


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    reason: str
    project_remaining_budget_usd: Decimal
    effective_cap_usd: Decimal | None
    downgraded_to_model: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class ProviderChatResult:
    response_body: dict[str, Any]
    usage: ProviderUsage
    actual_model: str
    provider_name: str
    upstream_request_id: str | None
    content_text: str


@dataclass(frozen=True, slots=True)
class ProviderStreamHandle:
    event_iterator: AsyncIterator[bytes]
    result_factory: Callable[[], Awaitable[ProviderChatResult]]


@dataclass(frozen=True, slots=True)
class GatewayChatRequest:
    request_id: str
    requested_model: str
    messages: Sequence[Mapping[str, Any]]
    stream: bool
    temperature: float | None
    max_tokens: int | None
    route_policy_override: str | None
    request_cap_usd: Decimal | None
    cache_enabled: bool
    capture_body: bool
    demo_scenario: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_id: str
    request_id: str
    attempt_index: int
    candidate_model: str
    actual_model: str | None
    provider_name: str
    status: AttemptStatus
    failure_kind: FailureKind
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    http_status: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    error_code: str | None
    error_message: str | None
    upstream_request_id: str | None


@dataclass(frozen=True, slots=True)
class RequestRecord:
    request_id: str
    project_id: str
    route_policy: str
    requested_model: str
    resolved_model: str | None
    status: RequestStatus
    stream: bool
    cache_status: CacheStatus
    capture_body: bool
    attempt_count: int
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    currency: str = "USD"
    error_code: str | None = None
    error_message: str | None = None
    request_body_redacted: dict[str, Any] | None = None
    response_body_redacted: dict[str, Any] | None = None
    budget_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    request_id: str
    response_body: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class StreamState:
    chunks: list[str] = field(default_factory=list)
    usage: ProviderUsage | None = None
    upstream_request_id: str | None = None
