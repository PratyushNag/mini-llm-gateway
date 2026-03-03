from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmRequestModel
from app.domain.entities import RequestRecord
from app.domain.enums import CacheStatus, RequestStatus


def _to_domain(model: LlmRequestModel) -> RequestRecord:
    return RequestRecord(
        request_id=model.id,
        project_id=model.project_id,
        route_policy=model.route_policy,
        requested_model=model.requested_model,
        resolved_model=model.resolved_model,
        status=RequestStatus(model.status),
        stream=model.stream,
        cache_status=CacheStatus(model.cache_status),
        capture_body=model.capture_body,
        attempt_count=model.attempt_count,
        started_at=model.started_at,
        completed_at=model.completed_at,
        latency_ms=model.latency_ms,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        total_tokens=model.total_tokens,
        cost_usd=Decimal(model.cost_usd),
        currency=model.currency,
        error_code=model.error_code,
        error_message=model.error_message,
        request_body_redacted=model.request_body_redacted,
        response_body_redacted=model.response_body_redacted,
        budget_reason=model.budget_reason,
    )


class RequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: RequestRecord) -> None:
        self._session.add(
            LlmRequestModel(
                id=record.request_id,
                project_id=record.project_id,
                route_policy=record.route_policy,
                requested_model=record.requested_model,
                resolved_model=record.resolved_model,
                status=record.status.value,
                stream=record.stream,
                cache_status=record.cache_status.value,
                capture_body=record.capture_body,
                attempt_count=record.attempt_count,
                started_at=record.started_at,
                completed_at=record.completed_at,
                latency_ms=record.latency_ms,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                total_tokens=record.total_tokens,
                cost_usd=record.cost_usd,
                currency=record.currency,
                error_code=record.error_code,
                error_message=record.error_message,
                budget_reason=record.budget_reason,
                request_body_redacted=record.request_body_redacted,
                response_body_redacted=record.response_body_redacted,
            )
        )
        await self._session.commit()

    async def update(self, record: RequestRecord) -> None:
        model = await self._session.get(LlmRequestModel, record.request_id)
        if model is None:
            await self.create(record)
            return
        model.resolved_model = record.resolved_model
        model.status = record.status.value
        model.cache_status = record.cache_status.value
        model.attempt_count = record.attempt_count
        model.completed_at = record.completed_at
        model.latency_ms = record.latency_ms
        model.prompt_tokens = record.prompt_tokens
        model.completion_tokens = record.completion_tokens
        model.total_tokens = record.total_tokens
        model.cost_usd = record.cost_usd
        model.currency = record.currency
        model.error_code = record.error_code
        model.error_message = record.error_message
        model.budget_reason = record.budget_reason
        model.request_body_redacted = record.request_body_redacted
        model.response_body_redacted = record.response_body_redacted
        await self._session.commit()

    async def list_for_project(self, *, project_id: str, limit: int) -> list[RequestRecord]:
        query = (
            select(LlmRequestModel)
            .where(LlmRequestModel.project_id == project_id)
            .order_by(LlmRequestModel.started_at.desc())
            .limit(limit)
        )
        rows = (await self._session.scalars(query)).all()
        return [_to_domain(row) for row in rows]

    async def get_for_project(self, *, project_id: str, request_id: str) -> RequestRecord | None:
        query = (
            select(LlmRequestModel)
            .where(LlmRequestModel.project_id == project_id)
            .where(LlmRequestModel.id == request_id)
            .limit(1)
        )
        row = (await self._session.scalars(query)).first()
        return None if row is None else _to_domain(row)

    async def current_month_cost(self, *, project_id: str) -> float:
        now = datetime.now(UTC)
        month_start = datetime(year=now.year, month=now.month, day=1, tzinfo=UTC)
        query = select(func.coalesce(func.sum(LlmRequestModel.cost_usd), 0)).where(
            LlmRequestModel.project_id == project_id,
            LlmRequestModel.completed_at >= month_start,
            LlmRequestModel.status == RequestStatus.SUCCEEDED.value,
        )
        value = (await self._session.execute(query)).scalar_one()
        return float(value)
