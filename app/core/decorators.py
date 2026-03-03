from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from app.observability.metrics import observe_internal_operation

P = ParamSpec("P")
R = TypeVar("R")


def timed_async(
    operation_name: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            started_at = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                observe_internal_operation(operation_name, time.perf_counter() - started_at)

        return wrapper

    return decorator
