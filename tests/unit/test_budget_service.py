from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from app.domain.entities import GatewayChatRequest, ProjectContext, RouteCandidate, RoutePlan
from app.services.budget_service import BudgetService


class _FakeRequestRepository:
    async def current_month_cost(self, *, project_id: str) -> float:
        return 0.0


class _FakeBundle:
    def __init__(self) -> None:
        self.requests = _FakeRequestRepository()


class _FakeLoggingService:
    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[_FakeBundle]:
        yield _FakeBundle()


@pytest.mark.asyncio
async def test_budget_service_downgrades_to_cheaper_model() -> None:
    service = BudgetService(_FakeLoggingService())  # type: ignore[arg-type]
    project = ProjectContext(
        project_id="prj_1",
        project_name="demo",
        default_route_policy="balanced",
        monthly_budget_usd=Decimal("10"),
        per_request_cap_usd=Decimal("0.02"),
        allow_body_capture=False,
        api_key_id="key_1",
    )
    request = GatewayChatRequest(
        request_id="req_1",
        requested_model="auto",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
        temperature=0.2,
        max_tokens=500,
        route_policy_override=None,
        request_cap_usd=Decimal("0.001"),
        cache_enabled=False,
        capture_body=False,
        demo_scenario=None,
        raw_payload={"messages": [{"role": "user", "content": "hello"}]},
    )
    route_plan = RoutePlan(
        policy_name="balanced",
        requested_model="auto",
        candidates=(
            RouteCandidate(
                model="openai/gpt-4.1",
                input_cost_per_1k=Decimal("0.010"),
                output_cost_per_1k=Decimal("0.030"),
            ),
            RouteCandidate(
                model="openai/gpt-4o-mini",
                input_cost_per_1k=Decimal("0.00015"),
                output_cost_per_1k=Decimal("0.0006"),
            ),
        ),
        retry_on=frozenset(),
    )

    decision = await service.evaluate(project=project, request=request, route_plan=route_plan)

    assert decision.allowed is True
    assert decision.downgraded_to_model == "openai/gpt-4o-mini"
