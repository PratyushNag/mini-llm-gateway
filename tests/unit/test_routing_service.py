from decimal import Decimal

from app.core.config import Settings
from app.domain.entities import ProjectContext
from app.services.routing_service import RoutingService


def test_routing_service_resolves_auto_policy() -> None:
    settings = Settings(routes_config_path="config/routes.yml")
    service = RoutingService(settings)
    project = ProjectContext(
        project_id="prj_1",
        project_name="demo",
        default_route_policy="balanced",
        monthly_budget_usd=Decimal("100"),
        per_request_cap_usd=Decimal("10"),
        allow_body_capture=False,
        api_key_id="key_1",
    )

    route_plan = service.resolve(
        requested_model="auto", route_policy_override=None, project=project
    )

    assert route_plan.policy_name == "balanced"
    assert [candidate.model for candidate in route_plan.candidates] == [
        "openai/gpt-4.1",
        "openai/gpt-4o-mini",
    ]
