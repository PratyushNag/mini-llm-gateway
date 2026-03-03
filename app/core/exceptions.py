from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GatewayError(Exception):
    code: str
    message: str
    status_code: int
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AuthenticationError(GatewayError):
    def __init__(self, message: str = "Invalid API key.") -> None:
        super().__init__(
            code="unauthorized",
            message=message,
            status_code=401,
            retryable=False,
        )


class BudgetExceededError(GatewayError):
    def __init__(self, message: str, *, status_code: int = 402) -> None:
        super().__init__(
            code="budget_exhausted",
            message=message,
            status_code=status_code,
            retryable=False,
        )


class NotFoundError(GatewayError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(
            code="not_found",
            message=message,
            status_code=404,
            retryable=False,
        )


class ValidationGatewayError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="invalid_request",
            message=message,
            status_code=422,
            retryable=False,
        )


class UpstreamGatewayError(GatewayError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        retryable: bool,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            retryable=retryable,
        )
