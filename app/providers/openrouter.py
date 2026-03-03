from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.core.exceptions import UpstreamGatewayError
from app.domain.entities import (
    GatewayChatRequest,
    ProviderChatResult,
    ProviderStreamHandle,
    ProviderUsage,
)
from app.providers.translators import build_provider_payload, estimate_usage, flatten_response_text


def _build_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_http_referer,
        "X-Title": settings.openrouter_app_title,
    }
    if settings.openrouter_api_key:
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
    return headers


def _classify_error(status_code: int) -> tuple[str, bool]:
    if status_code == 429:
        return "upstream_rate_limited", True
    if status_code >= 500:
        return "upstream_unavailable", True
    return "upstream_bad_request", False


class OpenRouterProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._headers = _build_headers(settings)
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderChatResult:
        if self._settings.demo_enabled and self._settings.demo_upstream_mode == "mock":
            return self._mock_completion(candidate_model=candidate_model, request=request)

        payload = build_provider_payload(request, candidate_model)
        response = await self._client.post("/chat/completions", headers=self._headers, json=payload)
        if response.status_code >= 400:
            code, retryable = _classify_error(response.status_code)
            raise UpstreamGatewayError(
                code=code,
                message=response.text,
                status_code=response.status_code,
                retryable=retryable,
            )
        body = response.json()
        usage_payload = body.get("usage", {})
        usage = ProviderUsage(
            prompt_tokens=int(usage_payload.get("prompt_tokens", 0)),
            completion_tokens=int(usage_payload.get("completion_tokens", 0)),
            total_tokens=int(usage_payload.get("total_tokens", 0)),
        )
        return ProviderChatResult(
            response_body=body,
            usage=usage,
            actual_model=str(body.get("model", candidate_model)),
            provider_name="openrouter",
            upstream_request_id=body.get("id"),
            content_text=flatten_response_text(body),
        )

    async def stream_chat_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
        attempt_index: int,
    ) -> ProviderStreamHandle:
        if self._settings.demo_enabled and self._settings.demo_upstream_mode == "mock":
            return self._mock_stream(candidate_model=candidate_model, request=request)

        payload = build_provider_payload(request, candidate_model)
        response = await self._client.send(
            self._client.build_request(
                "POST",
                "/chat/completions",
                headers=self._headers,
                json=payload,
            ),
            stream=True,
        )
        if response.status_code >= 400:
            message = await response.aread()
            await response.aclose()
            code, retryable = _classify_error(response.status_code)
            raise UpstreamGatewayError(
                code=code,
                message=message.decode("utf-8", errors="replace"),
                status_code=response.status_code,
                retryable=retryable,
            )

        done = asyncio.Event()
        result_box: dict[str, ProviderChatResult] = {}
        content_parts: list[str] = []
        usage = ProviderUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        upstream_request_id: str | None = None

        async def event_iterator() -> AsyncIterator[bytes]:
            nonlocal usage, upstream_request_id
            try:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        raw_payload = line[6:]
                        if raw_payload == "[DONE]":
                            yield b"data: [DONE]\n\n"
                            continue
                        payload_item = json.loads(raw_payload)
                        upstream_request_id = payload_item.get("id", upstream_request_id)
                        if payload_item.get("usage"):
                            usage = ProviderUsage(
                                prompt_tokens=int(payload_item["usage"].get("prompt_tokens", 0)),
                                completion_tokens=int(
                                    payload_item["usage"].get("completion_tokens", 0)
                                ),
                                total_tokens=int(payload_item["usage"].get("total_tokens", 0)),
                            )
                        delta = (
                            payload_item.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        )
                        if delta:
                            content_parts.append(str(delta))
                    yield f"{line}\n\n".encode()
            finally:
                await response.aclose()
                if usage.total_tokens == 0:
                    usage = estimate_usage(list(request.messages), max_tokens=request.max_tokens)
                result_box["result"] = ProviderChatResult(
                    response_body={
                        "id": upstream_request_id or f"stream-{request.request_id}",
                        "object": "chat.completion",
                        "model": candidate_model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "".join(content_parts)},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens,
                        },
                    },
                    usage=usage,
                    actual_model=candidate_model,
                    provider_name="openrouter",
                    upstream_request_id=upstream_request_id,
                    content_text="".join(content_parts),
                )
                done.set()

        async def result_factory() -> ProviderChatResult:
            await done.wait()
            return result_box["result"]

        return ProviderStreamHandle(event_iterator=event_iterator(), result_factory=result_factory)

    def _mock_completion(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
    ) -> ProviderChatResult:
        last_user_message = next(
            (
                str(message["content"])
                for message in reversed(request.messages)
                if message["role"] == "user"
            ),
            "No prompt supplied.",
        )
        content = (
            f"[mock:{candidate_model}] "
            f"The gateway processed your request. "
            f"Prompt summary: {last_user_message[:180]}"
        )
        usage = estimate_usage(list(request.messages), max_tokens=request.max_tokens)
        body = {
            "id": f"mock-{request.request_id}",
            "object": "chat.completion",
            "created": 0,
            "model": candidate_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
        }
        return ProviderChatResult(
            response_body=body,
            usage=usage,
            actual_model=candidate_model,
            provider_name="mock-openrouter",
            upstream_request_id=body["id"],
            content_text=content,
        )

    def _mock_stream(
        self,
        *,
        candidate_model: str,
        request: GatewayChatRequest,
    ) -> ProviderStreamHandle:
        content = self._mock_completion(
            candidate_model=candidate_model, request=request
        ).content_text
        usage = estimate_usage(list(request.messages), max_tokens=request.max_tokens)
        done = asyncio.Event()
        result_box: dict[str, ProviderChatResult] = {}

        async def event_iterator() -> AsyncIterator[bytes]:
            for part in content.split():
                chunk = {
                    "id": f"mock-stream-{request.request_id}",
                    "object": "chat.completion.chunk",
                    "model": candidate_model,
                    "choices": [{"index": 0, "delta": {"content": f"{part} "}}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
                await asyncio.sleep(0.02)

            usage_chunk = {
                "id": f"mock-stream-{request.request_id}",
                "object": "chat.completion.chunk",
                "model": candidate_model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
            }
            yield f"data: {json.dumps(usage_chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"
            result_box["result"] = ProviderChatResult(
                response_body={
                    "id": f"mock-stream-{request.request_id}",
                    "object": "chat.completion",
                    "model": candidate_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                },
                usage=usage,
                actual_model=candidate_model,
                provider_name="mock-openrouter",
                upstream_request_id=f"mock-stream-{request.request_id}",
                content_text=content,
            )
            done.set()

        async def result_factory() -> ProviderChatResult:
            await done.wait()
            return result_box["result"]

        return ProviderStreamHandle(event_iterator=event_iterator(), result_factory=result_factory)
