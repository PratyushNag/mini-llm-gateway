from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from fastapi import Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ValidationGatewayError
from app.domain.entities import GatewayChatRequest, ProjectContext
from app.services.chat_service import ChatService


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    chat_service: ChatService


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


async def get_project_context(
    request: Request,
    authorization: str = Header(alias="Authorization"),
) -> ProjectContext:
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Authorization header must use Bearer token.")
    api_key = authorization.removeprefix("Bearer ").strip()
    return await get_container(request).chat_service.authenticate(api_key)


def build_gateway_request(
    *,
    request_id: str,
    payload: dict,
    route_policy_override: str | None,
    request_cap_header: str | None,
    cache_mode_header: str | None,
    capture_body_header: str | None,
    demo_scenario_header: str | None,
    project: ProjectContext,
    default_capture_body: bool,
) -> GatewayChatRequest:
    request_cap_usd = None
    if request_cap_header:
        try:
            request_cap_usd = Decimal(request_cap_header)
        except InvalidOperation as exc:
            raise ValidationGatewayError(
                "X-Gateway-Max-Cost-USD must be a decimal number."
            ) from exc
    capture_body = default_capture_body
    if capture_body_header is not None:
        capture_body = capture_body_header.lower() == "true"
    capture_body = capture_body and project.allow_body_capture
    return GatewayChatRequest(
        request_id=request_id,
        requested_model=str(payload["model"]),
        messages=payload["messages"],
        stream=bool(payload.get("stream", False)),
        temperature=payload.get("temperature"),
        max_tokens=payload.get("max_tokens"),
        route_policy_override=route_policy_override,
        request_cap_usd=request_cap_usd,
        cache_enabled=cache_mode_header == "read_write",
        capture_body=capture_body,
        demo_scenario=demo_scenario_header,
        raw_payload=payload,
    )
