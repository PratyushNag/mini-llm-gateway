from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmAttemptModel
from app.domain.entities import AttemptRecord
from app.domain.enums import AttemptStatus, FailureKind


def _to_domain(model: LlmAttemptModel) -> AttemptRecord:
    return AttemptRecord(
        attempt_id=model.id,
        request_id=model.request_id,
        attempt_index=model.attempt_index,
        candidate_model=model.candidate_model,
        actual_model=model.actual_model,
        provider_name=model.provider_name,
        status=AttemptStatus(model.status),
        failure_kind=FailureKind(model.failure_kind),
        started_at=model.started_at,
        completed_at=model.completed_at,
        latency_ms=model.latency_ms,
        http_status=model.http_status,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        total_tokens=model.total_tokens,
        cost_usd=Decimal(model.cost_usd),
        error_code=model.error_code,
        error_message=model.error_message,
        upstream_request_id=model.upstream_request_id,
    )


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, records: list[AttemptRecord]) -> None:
        for record in records:
            self._session.add(
                LlmAttemptModel(
                    id=record.attempt_id,
                    request_id=record.request_id,
                    attempt_index=record.attempt_index,
                    candidate_model=record.candidate_model,
                    actual_model=record.actual_model,
                    provider_name=record.provider_name,
                    status=record.status.value,
                    failure_kind=record.failure_kind.value,
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    latency_ms=record.latency_ms,
                    http_status=record.http_status,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                    total_tokens=record.total_tokens,
                    cost_usd=record.cost_usd,
                    error_code=record.error_code,
                    error_message=record.error_message,
                    upstream_request_id=record.upstream_request_id,
                )
            )
        await self._session.commit()

    async def list_for_request(self, *, request_id: str) -> list[AttemptRecord]:
        query = (
            select(LlmAttemptModel)
            .where(LlmAttemptModel.request_id == request_id)
            .order_by(LlmAttemptModel.attempt_index.asc())
        )
        rows = (await self._session.scalars(query)).all()
        return [_to_domain(row) for row in rows]
