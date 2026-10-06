"""FastAPI application: authenticated product API and built React web app."""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import health, sessions
from app.core.config import get_settings
from app.core.errors import install_error_handlers


def create_app(*, enable_legacy: bool | None = None) -> FastAPI:
    settings = get_settings()
    from app.product.database import init_db
    from app.product.auth import router as auth_router
    from app.product.routes import router as product_router
    from app.product.media import router as media_router
    from app.product.assessment import router as assessment_router
    from app.product.report_pdf import router as report_pdf_router

    @asynccontextmanager
    async def lifespan(_app):
        init_db()
        yield

    app = FastAPI(title='ELEC5623 Group 9 — Pre-consultation', version='1.0.0', lifespan=lifespan,
                  docs_url=None if os.getenv('APP_ENV') == 'production' else '/api/docs', redoc_url=None)
    from app.product.config import get_settings as product_settings
    legacy_enabled = enable_legacy is True or (enable_legacy is None and os.getenv('ENABLE_LEGACY_API') == '1')
    origins = settings.cors_origins if legacy_enabled else sorted(product_settings().allowed_origins)
    origin_regex = settings.cors_origin_regex if legacy_enabled else None
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_origin_regex=origin_regex, allow_credentials=True,
                       allow_methods=['*'], allow_headers=['*'])

    @app.middleware('http')
    async def security_headers(request, call_next):
        # Bound multipart bodies before Starlette spools them to disk.
        length = request.headers.get('content-length')
        if request.url.path.startswith('/api/v1') and length:
            try:
                too_large = int(length) > 11 * 1024 * 1024
            except ValueError:
                too_large = True
            if too_large:
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': 'Request exceeds the 10 MB upload limit.'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        elif 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        return response

    app.include_router(health.router, prefix='/api')
    app.include_router(auth_router, prefix='/api/v1')
    app.include_router(product_router, prefix='/api/v1')
    app.include_router(media_router, prefix='/api/v1')
    app.include_router(assessment_router, prefix='/api/v1')
    app.include_router(report_pdf_router, prefix='/api/v1')
    # The original unowned teaching API is opt-in for historical tests only.
    if legacy_enabled:
        app.include_router(sessions.router, prefix='/api')
    install_error_handlers(app)

    frontend = Path(__file__).resolve().parents[3] / 'frontend' / 'dist'
    if (frontend / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=frontend / 'assets'), name='assets')
    @app.get('/', include_in_schema=False)
    @app.get('/patient', include_in_schema=False)
    @app.get('/doctor', include_in_schema=False)
    def index():
        if not (frontend / 'index.html').exists():
            from fastapi.responses import HTMLResponse
            return HTMLResponse('<h1>Pre-consultation</h1><p>Run scripts/start-local.sh to build the web interface.</p>', status_code=503)
        return FileResponse(frontend / 'index.html', headers={'Cache-Control': 'no-cache'})
    return app


app = create_app()
