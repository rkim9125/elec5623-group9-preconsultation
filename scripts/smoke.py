#!/usr/bin/env python3
"""Exercise the synthetic intake/document/export flow without external services.

Default: in-process FastAPI client, temporary local storage, OCR off, FakeLLM.
Optional --base-url: contact an already running loopback server; its configured
storage is used, and created documents are deleted before exit. The synthetic
session remains until that server restarts (there is no session-delete API).
"""

from __future__ import annotations

import argparse
from io import BytesIO
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def checked(response, status: int):
    if response.status_code != status:
        raise AssertionError(f"{response.request.method} {response.request.url.path}: expected {status}, got {response.status_code}: {response.text[:500]}")
    return response


def exercise(client) -> None:
    from docx import Document

    checked(client.get("/api/health"), 200)
    checked(client.get("/api/documents/health"), 200)
    session = checked(client.post("/api/sessions", json={"patient_ref": "synthetic-c7-smoke", "locale": "en-AU"}), 201).json()
    base = f"/api/sessions/{session['session_id']}"
    doc_ids: list[str] = []
    try:
        doc = Document()
        doc.add_paragraph("Synthetic preparation note: sore throat for three days.")
        data = BytesIO()
        doc.save(data)
        raw = data.getvalue()
        uploaded = checked(client.post(f"{base}/documents", files={"file": ("synthetic-note.docx", raw, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}), 201).json()
        doc_id = uploaded["document_id"]
        doc_ids.append(doc_id)
        assert uploaded["session_id"] == session["session_id"]
        document_url = f"{base}/documents/{doc_id}"
        assert checked(client.get(document_url), 200).json()["document_id"] == doc_id
        assert doc_id in {row["document_id"] for row in checked(client.get(f"{base}/documents"), 200).json()}
        extracted = checked(client.post(f"{document_url}/extract"), 200).json()["extraction"]
        assert extracted["status"] == "processed"
        assert "Synthetic preparation note" in " ".join(chunk["text"] for chunk in extracted["chunks"])
        assert checked(client.get(f"{document_url}/download"), 200).content == raw

        for slot_id, value in [
            ("chief_complaint", "Synthetic example: sore throat"),
            ("symptom_duration_days", 3),
            ("symptom_severity", "mild"),
            ("current_medications", []),
            ("allergies", []),
        ]:
            checked(client.post(f"{base}/slots/{slot_id}", json={"action": "edit", "value": value}), 200)
        checked(client.post(f"{base}/complete"), 200)
        checked(client.post(f"{base}/exports", json={"format": "pdf"}), 409)
        summary = checked(client.get(f"{base}/summary"), 200).json()
        assert summary["approved"] is False
        checked(client.post(f"{base}/summary/approve", json={"content_sha256": "0" * 64}), 409)
        approved = checked(client.post(f"{base}/summary/approve", json={"content_sha256": summary["content_sha256"]}), 200).json()
        assert approved["approved"] is True
        for export_format, signature in [("pdf", b"%PDF-"), ("docx", b"PK")]:
            exported = checked(client.post(f"{base}/exports", json={"format": export_format}), 201).json()
            doc_ids.append(exported["document_id"])
            download = checked(client.get(f"{base}/documents/{exported['document_id']}/download"), 200)
            assert download.content.startswith(signature)
    finally:
        errors = []
        for document_id in doc_ids:
            response = client.delete(f"{base}/documents/{document_id}")
            if response.status_code != 204:
                errors.append(f"{document_id}: HTTP {response.status_code}")
        if errors:
            raise AssertionError("Smoke cleanup failed: " + ", ".join(errors))
    assert checked(client.get(f"{base}/documents"), 200).json() == []
    print("PASS: health, synthetic intake, DOCX upload/extract/list/get/download, approval gate, PDF/DOCX exports, deletion")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="optional running server, e.g. http://127.0.0.1:8000 (loopback only)")
    args = parser.parse_args()
    if args.base_url:
        url = urlsplit(args.base_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            parser.error("--base-url must be an HTTP loopback origin without credentials, path, query, or fragment")
        import httpx
        from dotenv import load_dotenv

        load_dotenv(ROOT / "backend" / ".env", override=False)
        token = os.environ.get("DOCUMENT_API_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=30, trust_env=False) as client:
            exercise(client)
        print("Created synthetic session remains on the running server until restart.")
        return

    with TemporaryDirectory(prefix="elec5623-smoke-") as tmp:
        # Override .env and inherited settings before importing the application.
        # No cloud SDK, credentials, OCR binary, or live model is used here.
        os.environ.update({
            "STORAGE_BACKEND": "local",
            "STORAGE_LOCAL_ROOT": tmp,
            "STORAGE_BUCKET": "",
            "STORAGE_REGION": "",
            "STORAGE_ENDPOINT": "",
            "STORAGE_PREFIX": "smoke",
            "STORAGE_ACCESS_KEY_ID": "",
            "STORAGE_ACCESS_KEY_SECRET": "",
            "STORAGE_SESSION_TOKEN": "",
            "STORAGE_TIMEOUT_SECONDS": "10",
            "STORAGE_OSS_IS_CNAME": "false",
            "DOCUMENT_API_TOKEN": "",
            "DOCUMENT_MAX_BYTES": "10485760",
            "DOCUMENT_MAX_PDF_PAGES": "50",
            "DOCUMENT_MAX_TEXT_CHARS": "200000",
            "DOCUMENT_MAX_IMAGE_PIXELS": "20000000",
            "DOCUMENT_OCR_ENABLED": "false",
            "DOCUMENT_OCR_LANGUAGE": "eng",
            "DOCUMENT_OCR_TIMEOUT_SECONDS": "20",
        })
        from fastapi.testclient import TestClient
        from app.core.main import app

        with TestClient(app) as client:
            exercise(client)
    print("Temporary smoke files and in-process metadata discarded.")


if __name__ == "__main__":
    main()
