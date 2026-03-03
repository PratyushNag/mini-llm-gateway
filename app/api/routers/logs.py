from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_container, get_project_context
from app.api.schemas import AttemptLogResponse, RequestDetailResponse, RequestSummaryResponse
from app.domain.entities import ProjectContext

router = APIRouter(prefix="/v1/logs", tags=["logs"])

ProjectDependency = Annotated[ProjectContext, Depends(get_project_context)]


@router.get("", response_model=list[RequestSummaryResponse])
async def list_logs(
    request: Request,
    project: ProjectDependency,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RequestSummaryResponse]:
    container = get_container(request)
    records = await container.chat_service.list_logs(project=project, limit=limit)
    return [
        RequestSummaryResponse(
            request_id=record.request_id,
            route_policy=record.route_policy,
            requested_model=record.requested_model,
            resolved_model=record.resolved_model,
            status=record.status.value,
            stream=record.stream,
            cache_status=record.cache_status.value,
            attempt_count=record.attempt_count,
            latency_ms=record.latency_ms,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            cost_usd=record.cost_usd,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )
        for record in records
    ]


@router.get("/{request_id}", response_model=RequestDetailResponse)
async def get_log_detail(
    request_id: str,
    request: Request,
    project: ProjectDependency,
) -> RequestDetailResponse:
    container = get_container(request)
    record, attempts = await container.chat_service.get_log_detail(
        project=project, request_id=request_id
    )
    return RequestDetailResponse(
        request_id=record.request_id,
        route_policy=record.route_policy,
        requested_model=record.requested_model,
        resolved_model=record.resolved_model,
        status=record.status.value,
        stream=record.stream,
        cache_status=record.cache_status.value,
        attempt_count=record.attempt_count,
        latency_ms=record.latency_ms,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        total_tokens=record.total_tokens,
        cost_usd=record.cost_usd,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error_code=record.error_code,
        error_message=record.error_message,
        budget_reason=record.budget_reason,
        request_body_redacted=record.request_body_redacted,
        response_body_redacted=record.response_body_redacted,
        attempts=[
            AttemptLogResponse(
                attempt_id=attempt.attempt_id,
                attempt_index=attempt.attempt_index,
                candidate_model=attempt.candidate_model,
                actual_model=attempt.actual_model,
                provider_name=attempt.provider_name,
                status=attempt.status.value,
                failure_kind=attempt.failure_kind.value,
                latency_ms=attempt.latency_ms,
                http_status=attempt.http_status,
                prompt_tokens=attempt.prompt_tokens,
                completion_tokens=attempt.completion_tokens,
                total_tokens=attempt.total_tokens,
                cost_usd=attempt.cost_usd,
                error_code=attempt.error_code,
                error_message=attempt.error_message,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
            )
            for attempt in attempts
        ],
    )
