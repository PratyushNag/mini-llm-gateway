from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import UpstreamGatewayError
from app.domain.entities import GatewayChatRequest, ProviderChatResult, ProviderStreamHandle
from app.domain.protocols import LLMProvider


class DemoFailureProvider:
    def __init__(self, provider: LLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    async def chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderChatResult:
        self._maybe_fail(
            candidate_model=candidate_model, request=request, attempt_index=attempt_index
        )
        return await self._provider.chat_completion(
            candidate_model=candidate_model,
            request=request,
            attempt_index=attempt_index,
        )

    async def stream_chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderStreamHandle:
        self._maybe_fail(
            candidate_model=candidate_model, request=request, attempt_index=attempt_index
        )
        return await self._provider.stream_chat_completion(
            candidate_model=candidate_model,
            request=request,
            attempt_index=attempt_index,
        )

    def _maybe_fail(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> None:
        if not self._settings.demo_enabled:
            return
        if request.demo_scenario != "fallback":
            return
        if attempt_index != 1:
            return
        if "gpt-4.1" not in candidate_model:
            return
        raise UpstreamGatewayError(
            code="demo_forced_timeout",
            message="Demo mode forced the first attempt to timeout.",
            status_code=504,
            retryable=True,
        )
