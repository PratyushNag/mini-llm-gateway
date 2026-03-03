from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.deps import ServiceContainer
from app.api.error_handlers import register_error_handlers
from app.api.routers.chat import router as chat_router
from app.api.routers.health import router as health_router
from app.api.routers.logs import router as logs_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.observability.structured_logging import configure_logging
from app.providers.demo_failure import DemoFailureProvider
from app.providers.openrouter import OpenRouterProvider
from app.services.bootstrap import ensure_demo_project
from app.services.budget_service import BudgetService
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService
from app.services.logging_service import LoggingService
from app.services.routing_service import RoutingService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    logging_service = LoggingService(session_factory)
    await ensure_demo_project(logging_service, settings)

    routing_service = RoutingService(settings)
    budget_service = BudgetService(logging_service)
    cache_service = CacheService(redis, settings)
    openrouter_provider = OpenRouterProvider(settings)
    provider = DemoFailureProvider(openrouter_provider, settings)
    chat_service = ChatService(
        provider=provider,
        routing_service=routing_service,
        budget_service=budget_service,
        cache_service=cache_service,
        logging_service=logging_service,
    )
    app.state.container = ServiceContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=redis,
        chat_service=chat_service,
    )
    try:
        yield
    finally:
        await openrouter_provider.close()
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="LLM Gateway",
    version="0.1.0",
    description="Demo-first LLM control plane for routing, retries, budgets, caching, and logs.",
    lifespan=lifespan,
)

app.include_router(chat_router)
app.include_router(logs_router)
app.include_router(health_router)
register_error_handlers(app)
