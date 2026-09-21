"""Shared integration-token boundary; C3 still owns per-user authorization.

Tokenless development must bind the server to loopback (as scripts/start.sh
does). This dependency does not restrict client IPs and is not a substitute
for patient authentication or tenant authorization.
"""

import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.utils.document_errors import DocumentError

_bearer = HTTPBearer(auto_error=False)


def require_document_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.document_api_token.get_secret_value()
    if expected and (credentials is None or not secrets.compare_digest(credentials.credentials.encode("utf-8"), expected.encode("utf-8"))):
        raise DocumentError("DOCUMENT_ACCESS_DENIED", "A valid document API bearer token is required.", 401)
