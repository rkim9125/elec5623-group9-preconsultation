"""FastAPI application entrypoint.

Run in development:

    cd backend
    uvicorn app.core.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents, health, sessions
from app.api.document_limits import DocumentUploadLimitMiddleware
from app.core.config import get_settings
from app.core.errors import install_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ELEC5623 Group 9 — Pre-consultation API",
        version="0.1.0",
    )

    app.add_middleware(DocumentUploadLimitMiddleware, max_bytes=settings.document_max_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")

    install_error_handlers(app)

    return app


app = create_app()
