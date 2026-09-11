"""Application errors and the JSON error envelope.

Envelope shape (docs/api-contract.md section 4):

    {"error": {"code", "message", "details", "request_id"}}
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
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


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": _request_id(request),
                }
            },
        )
