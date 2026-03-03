from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response

from app.api.deps import build_gateway_request, get_container, get_project_context
from app.api.schemas import ChatCompletionRequest
from app.core.ids import new_request_id
from app.domain.entities import ProjectContext

router = APIRouter(prefix="/v1", tags=["chat"])

ProjectDependency = Annotated[ProjectContext, Depends(get_project_context)]


@router.post("/chat/completions")
async def create_chat_completion(
    payload: ChatCompletionRequest,
    request: Request,
    project: ProjectDependency,
    route_policy_override: str | None = Header(default=None, alias="X-Gateway-Route-Policy"),
    request_cap_header: str | None = Header(default=None, alias="X-Gateway-Max-Cost-USD"),
    cache_mode_header: str | None = Header(default=None, alias="X-Gateway-Cache-Mode"),
    capture_body_header: str | None = Header(default=None, alias="X-Gateway-Capture-Body"),
    demo_scenario_header: str | None = Header(default=None, alias="X-Demo-Scenario"),
) -> Response:
    container = get_container(request)
    request.state.gateway_request_id = new_request_id()
    gateway_request = build_gateway_request(
        request_id=request.state.gateway_request_id,
        payload=payload.model_dump(),
        route_policy_override=route_policy_override,
        request_cap_header=request_cap_header,
        cache_mode_header=cache_mode_header,
        capture_body_header=capture_body_header,
        demo_scenario_header=demo_scenario_header,
        project=project,
        default_capture_body=container.settings.log_body_capture_default,
    )
    if gateway_request.stream:
        return await container.chat_service.handle_streaming_chat(
            project=project, request=gateway_request
        )
    result = await container.chat_service.handle_chat(project=project, request=gateway_request)
    return JSONResponse(content=result.response_body, headers=result.headers)
