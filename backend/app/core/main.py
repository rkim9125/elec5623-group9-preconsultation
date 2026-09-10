"""FastAPI application entrypoint.

Run in development:

    cd backend
    uvicorn app.core.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ELEC5623 Group 9 — Pre-consultation API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers. C3 session APIs are added in feat/c3-session-api.
    app.include_router(health.router, prefix="/api")

    return app


app = create_app()
