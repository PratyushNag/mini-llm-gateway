from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.responses import StreamingResponse

from app.core.context import set_request_context
from app.core.decorators import timed_async
from app.core.exceptions import (
    BudgetExceededError,
    GatewayError,
    NotFoundError,
    UpstreamGatewayError,
)
from app.core.ids import new_attempt_id
from app.domain.entities import (
    AttemptRecord,
    GatewayChatRequest,
    GatewayResponse,
    ProjectContext,
    RequestRecord,
)
from app.domain.enums import AttemptStatus, CacheStatus, FailureKind, RequestStatus
from app.domain.protocols import LLMProvider
from app.observability.metrics import observe_attempt, observe_request
from app.providers.translators import calculate_cost, redact_payload
from app.services.budget_service import BudgetService
from app.services.cache_service import CacheService
from app.services.logging_service import LoggingService
from app.services.routing_service import RoutingService

LOGGER = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        routing_service: RoutingService,
        budget_service: BudgetService,
        cache_service: CacheService,
        logging_service: LoggingService,
    ) -> None:
        self._provider = provider
        self._routing_service = routing_service
        self._budget_service = budget_service
        self._cache_service = cache_service
        self._logging_service = logging_service

    async def authenticate(self, api_key: str) -> ProjectContext:
        async with self._logging_service.session_scope() as bundle:
            return await bundle.projects.resolve_project_by_api_key(api_key)

    @timed_async("chat_service_handle_non_stream")
    async def handle_chat(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
    ) -> GatewayResponse:
        set_request_context(request_id=request.request_id, project_id=project.project_id)
        route_plan = self._routing_service.resolve(
            requested_model=request.requested_model,
            route_policy_override=request.route_policy_override,
            project=project,
        )
        try:
            budget_decision = await self._budget_service.evaluate(
                project=project,
                request=request,
                route_plan=route_plan,
            )
        except BudgetExceededError as exc:
            await self._persist_rejected_request(
                project=project,
                request=request,
                route_policy=route_plan.policy_name,
                error=exc,
            )
            raise
        if budget_decision.downgraded_to_model is not None:
            route_plan = replace(
                route_plan,
                candidates=tuple(
                    candidate
                    for candidate in route_plan.candidates
                    if candidate.model == budget_decision.downgraded_to_model
                )
                + tuple(
                    candidate
                    for candidate in route_plan.candidates
                    if candidate.model != budget_decision.downgraded_to_model
                ),
            )

        cache_status, cached_response = await self._cache_service.fetch(
            request=request,
            route_policy=route_plan.policy_name,
            model=route_plan.candidates[0].model,
        )
        if cached_response is not None:
            return await self._build_cached_response(
                project=project,
                request=request,
                route_policy=route_plan.policy_name,
                cache_status=cache_status,
                response_body=cached_response,
                budget_reason=budget_decision.reason,
            )

        started_at = datetime.now(UTC)
        attempts: list[AttemptRecord] = []
        final_error: GatewayError | None = None
        for attempt_index, candidate in enumerate(route_plan.candidates, start=1):
            attempt_started_at = datetime.now(UTC)
            perf_started = time.perf_counter()
            try:
                provider_result = await self._provider.chat_completion(
                    candidate_model=candidate.model,
                    request=request,
                    attempt_index=attempt_index,
                )
                completed_at = datetime.now(UTC)
                latency_ms = int((time.perf_counter() - perf_started) * 1000)
                cost_usd = calculate_cost(provider_result.usage, candidate)
                attempts.append(
                    AttemptRecord(
                        attempt_id=new_attempt_id(),
                        request_id=request.request_id,
                        attempt_index=attempt_index,
                        candidate_model=candidate.model,
                        actual_model=provider_result.actual_model,
                        provider_name=provider_result.provider_name,
                        status=AttemptStatus.SUCCEEDED,
                        failure_kind=FailureKind.NONE,
                        started_at=attempt_started_at,
                        completed_at=completed_at,
                        latency_ms=latency_ms,
                        http_status=200,
                        prompt_tokens=provider_result.usage.prompt_tokens,
                        completion_tokens=provider_result.usage.completion_tokens,
                        total_tokens=provider_result.usage.total_tokens,
                        cost_usd=cost_usd,
                        error_code=None,
                        error_message=None,
                        upstream_request_id=provider_result.upstream_request_id,
                    )
                )
                observe_attempt(AttemptStatus.SUCCEEDED.value, latency_ms / 1000)
                request_record = RequestRecord(
                    request_id=request.request_id,
                    project_id=project.project_id,
                    route_policy=route_plan.policy_name,
                    requested_model=request.requested_model,
                    resolved_model=provider_result.actual_model,
                    status=RequestStatus.SUCCEEDED,
                    stream=False,
                    cache_status=cache_status,
                    capture_body=request.capture_body,
                    attempt_count=len(attempts),
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=int((completed_at - started_at).total_seconds() * 1000),
                    prompt_tokens=provider_result.usage.prompt_tokens,
                    completion_tokens=provider_result.usage.completion_tokens,
                    total_tokens=provider_result.usage.total_tokens,
                    cost_usd=sum(
                        (attempt.cost_usd for attempt in attempts), start=Decimal("0.000000")
                    ),
                    error_code=None,
                    error_message=None,
                    request_body_redacted=redact_payload(request.raw_payload)
                    if request.capture_body
                    else None,
                    response_body_redacted=(
                        redact_payload(provider_result.response_body)
                        if request.capture_body
                        else None
                    ),
                    budget_reason=budget_decision.reason,
                )
                async with self._logging_service.session_scope() as bundle:
                    await bundle.requests.create(request_record)
                    await bundle.attempts.create_many(attempts)
                await self._cache_service.store(
                    request=request,
                    route_policy=route_plan.policy_name,
                    model=candidate.model,
                    response_body=provider_result.response_body,
                )
                headers = self._build_headers(
                    request_id=request.request_id,
                    project_id=project.project_id,
                    route_policy=route_plan.policy_name,
                    resolved_model=provider_result.actual_model,
                    cache_status=cache_status.value,
                )
                observe_request(
                    RequestStatus.SUCCEEDED.value,
                    request_record.latency_ms / 1000,
                    float(request_record.cost_usd),
                )
                LOGGER.info(
                    "Request succeeded",
                    extra={
                        "extra_payload": {
                            "status": request_record.status.value,
                            "resolved_model": request_record.resolved_model,
                            "cache_status": request_record.cache_status.value,
                            "attempt_count": request_record.attempt_count,
                            "latency_ms": request_record.latency_ms,
                            "cost_usd": str(request_record.cost_usd),
                        }
                    },
                )
                return GatewayResponse(
                    request_id=request.request_id,
                    response_body=provider_result.response_body,
                    headers=headers,
                )
            except GatewayError as exc:
                completed_at = datetime.now(UTC)
                latency_ms = int((time.perf_counter() - perf_started) * 1000)
                attempts.append(
                    AttemptRecord(
                        attempt_id=new_attempt_id(),
                        request_id=request.request_id,
                        attempt_index=attempt_index,
                        candidate_model=candidate.model,
                        actual_model=None,
                        provider_name="openrouter",
                        status=AttemptStatus.FAILED,
                        failure_kind=self._classify_failure_kind(exc),
                        started_at=attempt_started_at,
                        completed_at=completed_at,
                        latency_ms=latency_ms,
                        http_status=exc.status_code,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_usd=Decimal("0.000000"),
                        error_code=exc.code,
                        error_message=exc.message,
                        upstream_request_id=None,
                    )
                )
                observe_attempt(AttemptStatus.FAILED.value, latency_ms / 1000)
                final_error = exc
                failure_kind = self._classify_failure_kind(exc)
                if failure_kind.value not in route_plan.retry_on and not exc.retryable:
                    break

        assert final_error is not None
        await self._persist_failure(
            project=project,
            request=request,
            route_policy=route_plan.policy_name,
            cache_status=cache_status,
            attempts=attempts,
            started_at=started_at,
            error=final_error,
            budget_reason=budget_decision.reason,
        )
        raise final_error

    async def handle_streaming_chat(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
    ) -> StreamingResponse:
        set_request_context(request_id=request.request_id, project_id=project.project_id)
        route_plan = self._routing_service.resolve(
            requested_model=request.requested_model,
            route_policy_override=request.route_policy_override,
            project=project,
        )
        try:
            budget_decision = await self._budget_service.evaluate(
                project=project,
                request=request,
                route_plan=route_plan,
            )
        except BudgetExceededError as exc:
            await self._persist_rejected_request(
                project=project,
                request=request,
                route_policy=route_plan.policy_name,
                error=exc,
            )
            raise
        candidate = route_plan.candidates[0]
        started_at = datetime.now(UTC)
        attempt_started_at = datetime.now(UTC)
        perf_started = time.perf_counter()
        handle = await self._provider.stream_chat_completion(
            candidate_model=candidate.model,
            request=request,
            attempt_index=1,
        )

        async def stream_iterator():
            attempts: list[AttemptRecord] = []
            try:
                async for chunk in handle.event_iterator:
                    yield chunk
                provider_result = await handle.result_factory()
                completed_at = datetime.now(UTC)
                latency_ms = int((time.perf_counter() - perf_started) * 1000)
                cost_usd = calculate_cost(provider_result.usage, candidate)
                attempts.append(
                    AttemptRecord(
                        attempt_id=new_attempt_id(),
                        request_id=request.request_id,
                        attempt_index=1,
                        candidate_model=candidate.model,
                        actual_model=provider_result.actual_model,
                        provider_name=provider_result.provider_name,
                        status=AttemptStatus.SUCCEEDED,
                        failure_kind=FailureKind.NONE,
                        started_at=attempt_started_at,
                        completed_at=completed_at,
                        latency_ms=latency_ms,
                        http_status=200,
                        prompt_tokens=provider_result.usage.prompt_tokens,
                        completion_tokens=provider_result.usage.completion_tokens,
                        total_tokens=provider_result.usage.total_tokens,
                        cost_usd=cost_usd,
                        error_code=None,
                        error_message=None,
                        upstream_request_id=provider_result.upstream_request_id,
                    )
                )
                request_record = RequestRecord(
                    request_id=request.request_id,
                    project_id=project.project_id,
                    route_policy=route_plan.policy_name,
                    requested_model=request.requested_model,
                    resolved_model=provider_result.actual_model,
                    status=RequestStatus.SUCCEEDED,
                    stream=True,
                    cache_status=CacheStatus.BYPASS,
                    capture_body=request.capture_body,
                    attempt_count=1,
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=int((completed_at - started_at).total_seconds() * 1000),
                    prompt_tokens=provider_result.usage.prompt_tokens,
                    completion_tokens=provider_result.usage.completion_tokens,
                    total_tokens=provider_result.usage.total_tokens,
                    cost_usd=cost_usd,
                    request_body_redacted=redact_payload(request.raw_payload)
                    if request.capture_body
                    else None,
                    response_body_redacted=(
                        redact_payload(provider_result.response_body)
                        if request.capture_body
                        else None
                    ),
                    budget_reason=budget_decision.reason,
                )
                async with self._logging_service.session_scope() as bundle:
                    await bundle.requests.create(request_record)
                    await bundle.attempts.create_many(attempts)
                observe_request(
                    RequestStatus.SUCCEEDED.value,
                    request_record.latency_ms / 1000,
                    float(cost_usd),
                )
            except Exception as exc:
                gateway_exc = (
                    exc
                    if isinstance(exc, GatewayError)
                    else UpstreamGatewayError(
                        code="stream_interrupted",
                        message=str(exc),
                        status_code=502,
                        retryable=False,
                    )
                )
                await self._persist_failure(
                    project=project,
                    request=request,
                    route_policy=route_plan.policy_name,
                    cache_status=CacheStatus.BYPASS,
                    attempts=[
                        AttemptRecord(
                            attempt_id=new_attempt_id(),
                            request_id=request.request_id,
                            attempt_index=1,
                            candidate_model=candidate.model,
                            actual_model=None,
                            provider_name="openrouter",
                            status=AttemptStatus.FAILED,
                            failure_kind=self._classify_failure_kind(gateway_exc),
                            started_at=attempt_started_at,
                            completed_at=datetime.now(UTC),
                            latency_ms=int((time.perf_counter() - perf_started) * 1000),
                            http_status=gateway_exc.status_code,
                            prompt_tokens=0,
                            completion_tokens=0,
                            total_tokens=0,
                            cost_usd=Decimal("0.000000"),
                            error_code=gateway_exc.code,
                            error_message=gateway_exc.message,
                            upstream_request_id=None,
                        )
                    ],
                    started_at=started_at,
                    error=gateway_exc,
                    budget_reason=budget_decision.reason,
                )
                raise

        return StreamingResponse(
            stream_iterator(),
            media_type="text/event-stream",
            headers=self._build_headers(
                request_id=request.request_id,
                project_id=project.project_id,
                route_policy=route_plan.policy_name,
                resolved_model=candidate.model,
                cache_status=CacheStatus.BYPASS.value,
            ),
        )

    async def list_logs(self, *, project: ProjectContext, limit: int) -> list[RequestRecord]:
        async with self._logging_service.session_scope() as bundle:
            return await bundle.requests.list_for_project(
                project_id=project.project_id, limit=limit
            )

    async def get_log_detail(
        self, *, project: ProjectContext, request_id: str
    ) -> tuple[RequestRecord, list[AttemptRecord]]:
        async with self._logging_service.session_scope() as bundle:
            request_record = await bundle.requests.get_for_project(
                project_id=project.project_id,
                request_id=request_id,
            )
            if request_record is None:
                raise NotFoundError("Request log not found.")
            attempts = await bundle.attempts.list_for_request(request_id=request_id)
            return request_record, attempts

    async def _build_cached_response(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
        route_policy: str,
        cache_status: CacheStatus,
        response_body: dict[str, object],
        budget_reason: str,
    ) -> GatewayResponse:
        now = datetime.now(UTC)
        request_record = RequestRecord(
            request_id=request.request_id,
            project_id=project.project_id,
            route_policy=route_policy,
            requested_model=request.requested_model,
            resolved_model=str(response_body.get("model")),
            status=RequestStatus.SUCCEEDED,
            stream=False,
            cache_status=cache_status,
            capture_body=request.capture_body,
            attempt_count=0,
            started_at=now,
            completed_at=now,
            latency_ms=0,
            prompt_tokens=int(response_body.get("usage", {}).get("prompt_tokens", 0)),
            completion_tokens=int(response_body.get("usage", {}).get("completion_tokens", 0)),
            total_tokens=int(response_body.get("usage", {}).get("total_tokens", 0)),
            cost_usd=Decimal("0.000000"),
            request_body_redacted=redact_payload(request.raw_payload)
            if request.capture_body
            else None,
            response_body_redacted=redact_payload(response_body) if request.capture_body else None,
            budget_reason=budget_reason,
        )
        async with self._logging_service.session_scope() as bundle:
            await bundle.requests.create(request_record)
        observe_request(RequestStatus.SUCCEEDED.value, 0.0, 0.0)
        return GatewayResponse(
            request_id=request.request_id,
            response_body=response_body,
            headers=self._build_headers(
                request_id=request.request_id,
                project_id=project.project_id,
                route_policy=route_policy,
                resolved_model=request_record.resolved_model or "cached",
                cache_status=cache_status.value,
            ),
        )

    async def _persist_failure(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
        route_policy: str,
        cache_status: CacheStatus,
        attempts: list[AttemptRecord],
        started_at: datetime,
        error: GatewayError,
        budget_reason: str,
    ) -> None:
        completed_at = datetime.now(UTC)
        request_record = RequestRecord(
            request_id=request.request_id,
            project_id=project.project_id,
            route_policy=route_policy,
            requested_model=request.requested_model,
            resolved_model=None,
            status=RequestStatus.FAILED,
            stream=request.stream,
            cache_status=cache_status,
            capture_body=request.capture_body,
            attempt_count=len(attempts),
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=int((completed_at - started_at).total_seconds() * 1000),
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=Decimal("0.000000"),
            error_code=error.code,
            error_message=error.message,
            request_body_redacted=redact_payload(request.raw_payload)
            if request.capture_body
            else None,
            budget_reason=budget_reason,
        )
        async with self._logging_service.session_scope() as bundle:
            await bundle.requests.create(request_record)
            await bundle.attempts.create_many(attempts)
        observe_request(RequestStatus.FAILED.value, request_record.latency_ms / 1000, 0.0)

    async def _persist_rejected_request(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
        route_policy: str,
        error: GatewayError,
    ) -> None:
        now = datetime.now(UTC)
        request_record = RequestRecord(
            request_id=request.request_id,
            project_id=project.project_id,
            route_policy=route_policy,
            requested_model=request.requested_model,
            resolved_model=None,
            status=RequestStatus.REJECTED,
            stream=request.stream,
            cache_status=CacheStatus.BYPASS,
            capture_body=request.capture_body,
            attempt_count=0,
            started_at=now,
            completed_at=now,
            latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=Decimal("0.000000"),
            error_code=error.code,
            error_message=error.message,
            request_body_redacted=redact_payload(request.raw_payload)
            if request.capture_body
            else None,
            budget_reason=error.message,
        )
        async with self._logging_service.session_scope() as bundle:
            await bundle.requests.create(request_record)

    @staticmethod
    def _build_headers(
        *,
        request_id: str,
        project_id: str,
        route_policy: str,
        resolved_model: str,
        cache_status: str,
    ) -> dict[str, str]:
        return {
            "X-Gateway-Request-Id": request_id,
            "X-Gateway-Project-Id": project_id,
            "X-Gateway-Route-Policy": route_policy,
            "X-Gateway-Resolved-Model": resolved_model,
            "X-Gateway-Cache": cache_status,
        }

    @staticmethod
    def _classify_failure_kind(exc: GatewayError) -> FailureKind:
        if exc.code == "demo_forced_timeout":
            return FailureKind.DEMO_FORCED_TIMEOUT
        if exc.status_code == 429:
            return FailureKind.UPSTREAM_429
        if exc.status_code >= 500:
            return FailureKind.UPSTREAM_5XX
        if exc.status_code >= 400:
            return FailureKind.UPSTREAM_4XX
        return FailureKind.UNKNOWN
