from __future__ import annotations

from decimal import Decimal

from app.core.exceptions import BudgetExceededError
from app.domain.entities import BudgetDecision, GatewayChatRequest, ProjectContext, RoutePlan
from app.observability.metrics import observe_budget_rejection
from app.providers.translators import calculate_cost, estimate_usage
from app.services.logging_service import LoggingService


class BudgetService:
    def __init__(self, logging_service: LoggingService) -> None:
        self._logging_service = logging_service

    async def evaluate(
        self,
        *,
        project: ProjectContext,
        request: GatewayChatRequest,
        route_plan: RoutePlan,
    ) -> BudgetDecision:
        async with self._logging_service.session_scope() as bundle:
            current_spend = Decimal(
                str(await bundle.requests.current_month_cost(project_id=project.project_id))
            )

        remaining = project.monthly_budget_usd - current_spend
        if remaining <= Decimal("0"):
            observe_budget_rejection()
            raise BudgetExceededError("Project monthly budget has been exhausted.")

        effective_cap = project.per_request_cap_usd
        if request.request_cap_usd is not None:
            effective_cap = (
                request.request_cap_usd
                if effective_cap is None
                else min(request.request_cap_usd, effective_cap)
            )

        estimated_usage = estimate_usage(
            list(request.raw_payload["messages"]), max_tokens=request.max_tokens
        )
        for candidate in route_plan.candidates:
            estimated_cost = calculate_cost(estimated_usage, candidate)
            if estimated_cost > remaining:
                continue
            if effective_cap is not None and estimated_cost > effective_cap:
                continue
            downgraded_to_model = None
            if candidate.model != route_plan.candidates[0].model:
                downgraded_to_model = candidate.model
            return BudgetDecision(
                allowed=True,
                reason="allowed",
                project_remaining_budget_usd=remaining,
                effective_cap_usd=effective_cap,
                downgraded_to_model=downgraded_to_model,
            )

        observe_budget_rejection()
        if effective_cap is not None:
            raise BudgetExceededError(
                "No route candidate satisfies the effective per-request budget cap.",
                status_code=422,
            )
        raise BudgetExceededError("No route candidate fits the remaining project budget.")
