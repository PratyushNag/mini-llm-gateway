from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

import orjson

from app.domain.entities import GatewayChatRequest, ProviderUsage, RouteCandidate


def build_provider_payload(request: GatewayChatRequest, candidate_model: str) -> dict[str, Any]:
    payload = {
        "model": candidate_model,
        "messages": list(request.messages),
        "stream": request.stream,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def estimate_usage(messages: list[dict[str, Any]], *, max_tokens: int | None) -> ProviderUsage:
    prompt_chars = sum(len(str(message.get("content", ""))) for message in messages)
    prompt_tokens = max(1, prompt_chars // 4)
    completion_tokens = max_tokens or 256
    return ProviderUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def calculate_cost(usage: ProviderUsage, candidate: RouteCandidate) -> Decimal:
    input_cost = Decimal(usage.prompt_tokens) / Decimal(1000) * candidate.input_cost_per_1k
    output_cost = Decimal(usage.completion_tokens) / Decimal(1000) * candidate.output_cost_per_1k
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


def build_cache_key(request: GatewayChatRequest, route_policy: str, model: str) -> str:
    key_payload = {
        "model": model,
        "messages": list(request.messages),
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "route_policy": route_policy,
    }
    digest = hashlib.sha256(orjson.dumps(key_payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
    return f"gateway:{digest}"


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    if "messages" in redacted:
        redacted["messages"] = [
            {
                "role": message.get("role"),
                "content": str(message.get("content", ""))[:160],
            }
            for message in redacted["messages"]
        ]
    return redacted


def flatten_response_text(response_body: dict[str, Any]) -> str:
    choices = response_body.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", ""))
