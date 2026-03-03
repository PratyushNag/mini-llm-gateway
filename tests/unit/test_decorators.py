from __future__ import annotations

import pytest

from app.core.decorators import timed_async


@pytest.mark.asyncio
async def test_timed_async_preserves_async_execution() -> None:
    calls: list[int] = []

    @timed_async("decorator-test")
    async def sample(value: int) -> int:
        calls.append(value)
        return value + 1

    result = await sample(3)

    assert result == 4
    assert calls == [3]
