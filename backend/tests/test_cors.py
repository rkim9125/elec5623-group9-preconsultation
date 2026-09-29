"""CORS behaviour the frontend depends on.

A browser treats localhost and 127.0.0.1 as different origins, and Vite moves
to 5174+ when 5173 is taken — both produce failures that don't look like CORS
problems from the frontend side, so they're pinned here.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.main import app

client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/api/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",  # a different origin to the browser
        "http://localhost:5174",  # Vite's fallback when 5173 is taken
        "http://127.0.0.1:3000",
    ],
)
def test_local_dev_origins_are_allowed_by_default(origin):
    resp = _preflight(origin)
    assert resp.headers.get("access-control-allow-origin") == origin


def test_non_local_origin_is_still_blocked():
    assert _preflight("https://evil.example.com").headers.get(
        "access-control-allow-origin"
    ) is None


def test_explicit_frontend_origin_disables_the_dev_fallback():
    configured = Settings(frontend_origin="https://prod.example.com")
    assert configured.cors_origins == ["https://prod.example.com"]
    assert configured.cors_origin_regex is None


def test_empty_frontend_origin_falls_back_to_local_regex():
    # docs/frontend-integration.md tells the frontend to leave this unset;
    # an empty value must not mean "block everything".
    assert Settings(frontend_origin="").cors_origin_regex is not None


def test_multiple_explicit_origins_are_split():
    configured = Settings(frontend_origin="https://a.example.com, https://b.example.com")
    assert configured.cors_origins == ["https://a.example.com", "https://b.example.com"]
