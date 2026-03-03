from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.services.logging_service import LoggingService


async def ensure_demo_project(logging_service: LoggingService, settings: Settings) -> None:
    async with logging_service.session_scope() as bundle:
        await bundle.projects.create_demo_project(
            name=settings.demo_project_name,
            api_key=settings.demo_project_api_key,
            default_route_policy=settings.default_route_policy,
            monthly_budget_usd=Decimal("25.00"),
            per_request_cap_usd=Decimal("2.00"),
            allow_body_capture=False,
        )
