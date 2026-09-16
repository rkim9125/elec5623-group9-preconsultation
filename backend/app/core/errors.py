"""Application errors and the JSON error envelope.

Envelope shape (docs/api-contract.md section 4):

    {"error": {"code", "message", "details", "request_id"}}
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL"

    def __init__(self, message: str, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class SessionNotFound(AppError):
    status_code = 404
    code = "SESSION_NOT_FOUND"


class SlotNotFound(AppError):
    status_code = 404
    code = "SLOT_NOT_FOUND"


class SessionAlreadyCompleted(AppError):
    status_code = 409
    code = "SESSION_ALREADY_COMPLETED"


class SlotValidationFailed(AppError):
    status_code = 422
    code = "SLOT_VALIDATION_FAILED"


class SummaryNotReady(AppError):
    status_code = 409
    code = "SUMMARY_NOT_READY"


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or f"req_{uuid4().hex[:8]}"


def _envelope(status_code: int, code: str, message: str, details: list, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": _request_id(request),
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    """Make every non-2xx response use the section-4 envelope, including
    FastAPI's own request-parsing/validation errors and truly unhandled ones —
    not just the AppError cases raised explicitly by route code."""

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.details, request)

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _envelope(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "REQUEST_VALIDATION_FAILED",
            "The request body did not match the expected shape.",
            jsonable_encoder(exc.errors()),
            request,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return _envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL", "Internal server error.", [], request
        )
