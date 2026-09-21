"""Stable errors shared by file validation, parsing, rendering and storage."""

from app.core.errors import AppError


class DocumentError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
