"""Observe final HTTPX requests without changing prompts or the base URL.

Prepare mode raises before ANY transport is called. Live mode preserves response
bytes. Only the configured Responses endpoint is allowed; auth headers are never
serialized. This recorder is scoped to one sequential evaluation process.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import threading
import time
from unittest.mock import patch

import httpx

from common import append_jsonl, digest


class PreparedRequest(Exception):
    pass


class BudgetExceeded(Exception):
    pass


def body_record(body: bytes) -> dict:
    try:
        decoded = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        decoded = None
    return {"body_b64": base64.b64encode(body).decode("ascii"),
            "body_sha256": digest(body), "body_json": decoded}


class Recorder:
    def __init__(self, directory, *, base_url, live=False, max_calls=0, max_reserved_output_tokens=0):
        url = httpx.URL(base_url)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Use a base URL without credentials, query parameters, or fragments")
        self.directory = directory
        self.endpoint = base_url.rstrip("/") + "/responses"
        self.live = live
        self.max_calls = max_calls
        self.max_reserved_output_tokens = max_reserved_output_tokens
        self.calls = 0
        self.reserved_output_tokens = 0
        self.metadata = None
        self.attempt = 0
        self.lock = threading.Lock()

    @contextmanager
    def job(self, **metadata):
        previous = self.metadata
        self.metadata, self.attempt = metadata, 0
        try:
            yield
        finally:
            self.metadata = previous

    def before(self, request, body):
        if self.metadata is None or str(request.url) != self.endpoint or request.method != "POST":
            raise RuntimeError("Evaluation blocked an unexpected HTTP request.")
        payload = json.loads(body)
        output_cap = payload.get("max_output_tokens", 0)
        with self.lock:
            if self.live and (self.calls >= self.max_calls or
                             self.reserved_output_tokens + output_cap > self.max_reserved_output_tokens):
                raise BudgetExceeded("Configured call/output-token reservation cap reached.")
            self.calls += 1
            self.attempt += 1
            self.reserved_output_tokens += output_cap
            record = {**self.metadata, "call_id": f"call-{self.calls:04d}", "attempt": self.attempt,
                      "mode": "live" if self.live else "prepare", "method": request.method,
                      "url": str(request.url), "created_at": datetime.now(timezone.utc).isoformat(),
                      **body_record(body)}
            # No request headers, cookies, API keys, or transport exception text.
            append_jsonl(self.directory / "requests.jsonl", record)
        return record

    def after(self, record, response, body, started):
        parsed = body_record(body)
        data = parsed["body_json"]
        result = {key: record[key] for key in ("case_id", "job_id", "operation", "call_id", "attempt")}
        result.update(mode="live", status_code=response.status_code,
                      duration_ms=round((time.perf_counter() - started) * 1000, 3), **parsed)
        result["headers"] = {k: v for k, v in response.headers.items()
                             if k.lower() in {"x-request-id", "openai-processing-ms", "content-type"}}
        result["usage"] = data.get("usage") if isinstance(data, dict) else None
        result["provider_response_id"] = data.get("id") if isinstance(data, dict) else None
        append_jsonl(self.directory / "responses.jsonl", result)

    def failed(self, record, exc, started):
        append_jsonl(self.directory / "responses.jsonl", {
            **{k: record[k] for k in ("case_id", "job_id", "operation", "call_id", "attempt")},
            "mode": "live", "status_code": None, "error_type": type(exc).__name__,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3), "usage": None,
        })

    @contextmanager
    def installed(self):
        sync_send, async_send = httpx.Client.send, httpx.AsyncClient.send
        recorder = self

        def send(client, request, **kwargs):
            record = recorder.before(request, request.read())
            if not recorder.live:
                raise PreparedRequest("Request captured; no network operation performed.")
            started = time.perf_counter()
            try:
                response = sync_send(client, request, **kwargs)
                recorder.after(record, response, response.read(), started)
                return response
            except Exception as exc:
                recorder.failed(record, exc, started)
                raise

        async def asend(client, request, **kwargs):
            record = recorder.before(request, await request.aread())
            if not recorder.live:
                raise PreparedRequest("Request captured; no network operation performed.")
            started = time.perf_counter()
            try:
                response = await async_send(client, request, **kwargs)
                recorder.after(record, response, await response.aread(), started)
                return response
            except Exception as exc:
                recorder.failed(record, exc, started)
                raise

        with patch.object(httpx.Client, "send", send), patch.object(httpx.AsyncClient, "send", asend):
            yield self
