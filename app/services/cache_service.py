from __future__ import annotations

from typing import Any

import orjson
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.domain.entities import GatewayChatRequest
from app.domain.enums import CacheStatus
from app.observability.metrics import observe_cache_hit
from app.providers.translators import build_cache_key


class CacheService:
    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self._redis = redis_client
        self._settings = settings

    async def fetch(
        self,
        *,
        request: GatewayChatRequest,
        route_policy: str,
        model: str,
    ) -> tuple[CacheStatus, dict[str, Any] | None]:
        if not self._is_cache_eligible(request):
            return CacheStatus.BYPASS, None
        key = build_cache_key(request, route_policy, model)
        try:
            raw = await self._redis.get(key)
        except RedisError:
            return CacheStatus.BYPASS, None
        if raw is None:
            return CacheStatus.MISS, None
        observe_cache_hit()
        return CacheStatus.HIT, orjson.loads(raw)

    async def store(
        self,
        *,
        request: GatewayChatRequest,
        route_policy: str,
        model: str,
        response_body: dict[str, Any],
    ) -> None:
        if not self._is_cache_eligible(request):
            return
        key = build_cache_key(request, route_policy, model)
        try:
            await self._redis.set(
                key,
                orjson.dumps(response_body),
                ex=self._settings.default_cache_ttl_seconds,
            )
        except RedisError:
            return

    @staticmethod
    def _is_cache_eligible(request: GatewayChatRequest) -> bool:
        return request.cache_enabled and not request.stream and request.demo_scenario != "fallback"
