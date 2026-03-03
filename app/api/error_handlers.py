from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import GatewayError
from app.core.ids import new_request_id


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def handle_gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        request_id = getattr(request.state, "gateway_request_id", None) or request.headers.get(
            "X-Gateway-Request-Id",
            new_request_id(),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request_id,
                    "retryable": exc.retryable,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        request_id = getattr(request.state, "gateway_request_id", None) or request.headers.get(
            "X-Gateway-Request-Id",
            new_request_id(),
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": str(exc),
                    "request_id": request_id,
                    "retryable": False,
                }
            },
        )
