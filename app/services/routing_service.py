from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from app.core.config import Settings
from app.core.exceptions import ValidationGatewayError
from app.domain.entities import ProjectContext, RouteCandidate, RoutePlan


class RoutingService:
    def __init__(self, settings: Settings) -> None:
        self._config = self._load_config(settings.routes_config_path)

    def resolve(
        self,
        *,
        requested_model: str,
        route_policy_override: str | None,
        project: ProjectContext,
    ) -> RoutePlan:
        policy_name = (
            route_policy_override or project.default_route_policy or self._config["default_policy"]
        )
        policy = self._config["policies"].get(policy_name)
        if policy is None:
            raise ValidationGatewayError(f"Unknown route policy '{policy_name}'.")

        if requested_model != "auto":
            candidates = (self._find_candidate(requested_model),)
        else:
            alias = policy["aliases"].get("auto")
            if alias is None:
                raise ValidationGatewayError(
                    f"Route policy '{policy_name}' does not define auto routing."
                )
            candidates = tuple(self._build_candidate(item) for item in alias["candidates"])

        return RoutePlan(
            policy_name=policy_name,
            requested_model=requested_model,
            candidates=candidates,
            retry_on=frozenset(policy.get("retry_on", [])),
        )

    def _find_candidate(self, model_name: str) -> RouteCandidate:
        for policy in self._config["policies"].values():
            for alias in policy.get("aliases", {}).values():
                for raw_candidate in alias.get("candidates", []):
                    if raw_candidate["model"] == model_name:
                        return self._build_candidate(raw_candidate)
        return RouteCandidate(
            model=model_name,
            input_cost_per_1k=Decimal("0.010000"),
            output_cost_per_1k=Decimal("0.030000"),
        )

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file_pointer:
            return yaml.safe_load(file_pointer)

    @staticmethod
    def _build_candidate(payload: dict[str, Any]) -> RouteCandidate:
        return RouteCandidate(
            model=str(payload["model"]),
            input_cost_per_1k=Decimal(str(payload["input_cost_per_1k"])),
            output_cost_per_1k=Decimal(str(payload["output_cost_per_1k"])),
        )
