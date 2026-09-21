"""Bound multipart bodies before Starlette spools uploads to disk."""

from starlette.requests import Request

from app.core.errors import _envelope


class DocumentUploadLimitMiddleware:
    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        # Allow multipart headers in addition to the validated file bytes.
        self.limit = max_bytes + 64 * 1024

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if not (scope["type"] == "http" and scope.get("method") == "POST"
                and path.startswith("/api/sessions/") and path.endswith("/documents")):
            return await self.app(scope, receive, send)
        request = Request(scope)

        async def reject():
            response = _envelope(413, "FILE_TOO_LARGE", "Upload request exceeds the configured size limit.", [], request)
            await response(scope, receive, send)

        try:
            declared = int(request.headers.get("content-length", "0"))
        except ValueError:
            declared = 0
        if declared > self.limit:
            return await reject()
        chunks = []
        length = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            length += len(chunk)
            if length > self.limit:
                return await reject()
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
