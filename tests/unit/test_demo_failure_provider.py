import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamGatewayError
from app.domain.entities import GatewayChatRequest, ProviderChatResult, ProviderUsage
from app.providers.demo_failure import DemoFailureProvider


class _StubProvider:
    async def chat_completion(
        self, *, candidate_model: str, request: GatewayChatRequest, attempt_index: int
    ) -> ProviderChatResult:
        return ProviderChatResult(
            response_body={},
            usage=ProviderUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            actual_model=candidate_model,
            provider_name="stub",
            upstream_request_id="up_1",
            content_text="ok",
        )

    async def stream_chat_completion(
        self, *, candidate_model: str, request: GatewayChatRequest, attempt_index: int
    ):
        raise AssertionError("stream not used in this test")


@pytest.mark.asyncio
async def test_demo_failure_provider_forces_first_fallback_failure() -> None:
    provider = DemoFailureProvider(_StubProvider(), Settings(enable_demo_mode=True))
    request = GatewayChatRequest(
        request_id="req_1",
        requested_model="auto",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
        temperature=0.2,
        max_tokens=50,
        route_policy_override=None,
        request_cap_usd=None,
        cache_enabled=False,
        capture_body=False,
        demo_scenario="fallback",
        raw_payload={"messages": [{"role": "user", "content": "hello"}]},
    )

    with pytest.raises(UpstreamGatewayError) as exc_info:
        await provider.chat_completion(
            candidate_model="openai/gpt-4.1",
            request=request,
            attempt_index=1,
        )

    assert exc_info.value.code == "demo_forced_timeout"
