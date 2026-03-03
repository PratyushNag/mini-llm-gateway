from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.deps import get_container
from app.observability.metrics import render_metrics

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    container = get_container(request)
    async with container.engine.begin() as connection:
        await connection.run_sync(lambda _: None)
    await container.redis.ping()  # type: ignore[misc]
    return {"status": "ready"}


@router.get("/metrics")
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
