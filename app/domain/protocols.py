from __future__ import annotations

from typing import Protocol

from app.domain.entities import (
    AttemptRecord,
    BudgetDecision,
    GatewayChatRequest,
    ProjectContext,
    ProviderChatResult,
    ProviderStreamHandle,
    RequestRecord,
    RoutePlan,
)


class LLMProvider(Protocol):
    async def chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderChatResult: ...

    async def stream_chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderStreamHandle: ...


class RoutingPolicyEngine(Protocol):
    def resolve(
        self,
        *,
        requested_model: str,
        route_policy_override: str | None,
        project: ProjectContext,
    ) -> RoutePlan: ...


class BudgetGuard(Protocol):
    async def evaluate(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
        route_plan: RoutePlan,
    ) -> BudgetDecision: ...


class CacheBackend(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class ProjectRepository(Protocol):
    async def resolve_project_by_api_key(self, api_key: str) -> ProjectContext: ...


class RequestRepository(Protocol):
    async def create(self, record: RequestRecord) -> None: ...
    async def update(self, record: RequestRecord) -> None: ...
    async def list_for_project(self, *, project_id: str, limit: int) -> list[RequestRecord]: ...
    async def get_for_project(
        self, *, project_id: str, request_id: str
    ) -> RequestRecord | None: ...
    async def current_month_cost(self, *, project_id: str) -> float: ...


class AttemptRepository(Protocol):
    async def create_many(self, records: list[AttemptRecord]) -> None: ...
