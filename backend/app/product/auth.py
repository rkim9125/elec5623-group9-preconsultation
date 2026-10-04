"""Email OTP authentication and same-origin protection for cookie sessions."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from typing import Literal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from .config import get_settings
from .database import get_connection, utc_now

router = APIRouter(prefix="/auth", tags=["Authentication"])


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        raise ValueError("Enter a valid email address.")
    return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["patient", "doctor"] = "patient"

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        return normalize_email(value)


class VerifyRequest(LoginRequest):
    code: str = Field(pattern=r"^\d{6}$")


class ProfileRequest(BaseModel):
    name: str = Field(max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if any(ord(char) < 32 for char in value):
            raise ValueError("Name contains invalid characters.")
        return value


def csrf_protect(request: Request) -> None:
    """Require browser-origin evidence on every state-changing request."""
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer", "")
        parsed = urlparse(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    if not origin or origin.rstrip("/") not in get_settings().allowed_origins:
        raise HTTPException(status_code=403, detail="Request origin is not allowed. Open this app from its configured address.")


def cookie_name() -> str:
    return "__Host-preconsult_session" if get_settings().production else "preconsult_session"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _otp_hash(code: str, salt: str) -> str:
    return hashlib.scrypt(code.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def _check_doctor(email: str, role: str) -> None:
    if role == "doctor" and email not in get_settings().doctor_emails:
        raise HTTPException(403, "This email is not registered as a clinician. Contact the service administrator.")


def _client_address(request: Request) -> str:
    # Do not trust client-supplied forwarded headers. A trusted proxy may populate
    # request.client when uvicorn is configured with explicit proxy trust.
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request, category: str, email: str | None = None) -> None:
    now = time.time()
    if category == "otp_request":
        windows = [(f"otp-send:ip:{_client_address(request)}", 3600, 30)]
        if email:
            windows.extend([(f"otp-send:email:{email}", 60, 1), (f"otp-send:email:{email}", 3600, 5)])
    elif category == "otp_verify":
        windows = [(f"otp-verify:ip:{_client_address(request)}", 3600, 60)]
        if email:
            windows.append((f"otp-verify:email:{email}", 3600, 20))
    else:
        windows = [(f"{category}:ip:{_client_address(request)}", 3600, 120)]
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM rate_limits WHERE happened_at < ?", (now - 86400,))
        for bucket, seconds, limit in windows:
            count = conn.execute("SELECT COUNT(*) FROM rate_limits WHERE bucket = ? AND happened_at > ?", (bucket, now - seconds)).fetchone()[0]
            if count >= limit:
                raise HTTPException(429, "Too many attempts. Please wait before trying again.", headers={"Retry-After": str(seconds)})
        for bucket in {entry[0] for entry in windows}:
            conn.execute("INSERT INTO rate_limits (bucket, happened_at) VALUES (?, ?)", (bucket, now))


def send_verification_email(email: str, code: str) -> None:
    """Server-side Resend call; never expose provider details or OTP to clients."""
    settings = get_settings()
    if not settings.mail_configured:
        raise HTTPException(503, "Email sign-in is not configured. Set RESEND_API_KEY and a verified RESEND_FROM_EMAIL on the server.")
    try:
        result = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_email,
                "to": [email],
                "subject": "Your Pre-Consultation sign-in code",
                "text": f"Your Pre-Consultation sign-in code is {code}.\n\nIt expires in 10 minutes and can be used once. Do not share it. If you did not request this, you can ignore this email.",
            },
            timeout=15,
        )
        result.raise_for_status()
        if not result.json().get("id"):
            raise ValueError("No delivery receipt")
    except (httpx.HTTPError, ValueError, AttributeError):
        raise HTTPException(502, "The email service could not send your code. Ask the administrator to check the verified sender and delivery configuration.") from None


def require_user(request: Request) -> dict:
    token = request.cookies.get(cookie_name(), "")
    if not token or len(token) > 256:
        raise HTTPException(401, "Please sign in to continue.")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, u.name, s.role FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
            (_token_hash(token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = dict(row)
    _check_doctor(user["email"], user["role"])
    return user


def require_patient(user: dict = Depends(require_user)) -> dict:
    if user["role"] != "patient":
        raise HTTPException(403, "Use the patient portal to manage your own intake.")
    return user


def require_doctor(user: dict = Depends(require_user)) -> dict:
    if user["role"] != "doctor":
        raise HTTPException(403, "Clinician access is required.")
    return user


@router.post("/request-code", dependencies=[Depends(csrf_protect)])
def request_code(body: LoginRequest, request: Request, response: Response) -> dict:
    settings = get_settings()
    if not settings.mail_configured:
        raise HTTPException(503, "Email sign-in is not configured. Set RESEND_API_KEY and a verified RESEND_FROM_EMAIL on the server.")
    _check_doctor(body.email, body.role)
    check_rate_limit(request, "otp_request", body.email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    challenge_id = uuid4().hex
    now = time.time()
    with get_connection() as conn:
        conn.execute("DELETE FROM otp_challenges WHERE expires_at <= ?", (now,))
        conn.execute(
            "INSERT INTO otp_challenges (id, email, role, salt, code_hash, expires_at, attempts, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?) ON CONFLICT(email, role) DO UPDATE SET id=excluded.id, salt=excluded.salt, code_hash=excluded.code_hash, expires_at=excluded.expires_at, attempts=0, created_at=excluded.created_at",
            (challenge_id, body.email, body.role, salt, _otp_hash(code, salt), now + settings.otp_ttl_seconds, now),
        )
    try:
        send_verification_email(body.email, code)
    except Exception:
        with get_connection() as conn:
            conn.execute("DELETE FROM otp_challenges WHERE id = ?", (challenge_id,))
        raise
    response.headers["Cache-Control"] = "no-store"
    return {"message": "A six-digit sign-in code has been sent to your email.", "expires_in": settings.otp_ttl_seconds}


@router.post("/verify", dependencies=[Depends(csrf_protect)])
def verify_code(body: VerifyRequest, request: Request, response: Response) -> dict:
    settings = get_settings()
    _check_doctor(body.email, body.role)
    check_rate_limit(request, "otp_verify", body.email)
    token = secrets.token_urlsafe(48)
    now = time.time()
    user = None
    # Invalid-attempt changes must COMMIT; raise only after leaving transaction.
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        challenge = conn.execute("SELECT * FROM otp_challenges WHERE email = ? AND role = ?", (body.email, body.role)).fetchone()
        valid = bool(challenge and challenge["expires_at"] > now and challenge["attempts"] < settings.otp_attempt_limit)
        if valid and not hmac.compare_digest(_otp_hash(body.code, challenge["salt"]), challenge["code_hash"]):
            conn.execute("UPDATE otp_challenges SET attempts = attempts + 1 WHERE id = ?", (challenge["id"],))
            valid = False
        if valid:
            conn.execute("DELETE FROM otp_challenges WHERE id = ?", (challenge["id"],))
            conn.execute("INSERT OR IGNORE INTO users (id, email, name, created_at) VALUES (?, ?, '', ?)", (uuid4().hex, body.email, utc_now()))
            row = conn.execute("SELECT id, email, name FROM users WHERE email = ?", (body.email,)).fetchone()
            user = {**dict(row), "role": body.role}
            old_token = request.cookies.get(cookie_name())
            if old_token:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(old_token),))
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            conn.execute("INSERT INTO sessions (token_hash, user_id, role, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                         (_token_hash(token), user["id"], body.role, now + settings.session_ttl_seconds, now))
    if user is None:
        raise HTTPException(400, "That code is invalid or expired. Request a new code if needed.")
    response.set_cookie(cookie_name(), token, max_age=settings.session_ttl_seconds, httponly=True, secure=settings.production, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"user": user}


@router.get("/me")
def current_user(response: Response, user: dict = Depends(require_user)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"user": user}


@router.patch("/me", dependencies=[Depends(csrf_protect)])
def update_profile(body: ProfileRequest, user: dict = Depends(require_user)) -> dict:
    with get_connection() as conn:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (body.name, user["id"]))
    return {"user": {**user, "name": body.name}}


@router.post("/logout", status_code=204, dependencies=[Depends(csrf_protect)])
def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(cookie_name())
    if token:
        with get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    response.delete_cookie(cookie_name(), path="/", secure=get_settings().production, httponly=True, samesite="lax")
