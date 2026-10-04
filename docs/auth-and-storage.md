# Authentication, sharing and local storage

The product API uses email verification codes only. There is no password route,
seeded account, development code, or authentication bypass. The email adapter
sends through Resend; missing sender configuration and provider delivery failures
return explicit errors and never claim a code was sent successfully.

## Configuration

- `RESEND_API_KEY` and `RESEND_FROM_EMAIL`: a send-capable Resend key and a sender
  verified for the account. Sender/domain setup must be completed in Resend.
- `DOCTOR_EMAILS`: comma-separated clinician email allowlist. An authenticated
  patient cannot grant themselves clinician access by changing request JSON.
- `APP_BASE_URL`: the exact browser origin, for example `http://localhost:8000`.
  Production must use an HTTPS deployment. `APP_ENV=production` enables Secure
  host-only session cookies. Add intentional extra origins with `ALLOWED_ORIGINS`.
- `PRODUCT_DB_PATH`: SQLite file (defaults to `backend/data/product.sqlite3`).
- `UPLOAD_DIR`: private local attachment directory (defaults to
  `backend/data/uploads`). Do not serve this directory with a static file server.

OTP codes expire after 10 minutes, permit at most five wrong attempts, and are
salted with scrypt in the database. A successful verification atomically consumes
the code and creates a 12-hour session. Session tokens are opaque random values;
only their SHA-256 digests are persisted. Cookies are HttpOnly and SameSite=Lax.
All mutations require a matching Origin or Referer. Logout revokes the server-side
session. Email and IP rate limits protect code send/verify routes.

The clinician role is checked against the current allowlist on each authenticated
request, so removing an address revokes clinician access even for existing sessions.

## Approval boundary

Patients can read, edit, and delete only their own intakes. A draft must be reviewed
and its current summary version explicitly approved for an allowlisted clinician.
Only that clinician can retrieve the shared record. Clinicians receive the approved
summary, structured information, and attachments, without private chat history or
internal planner/provider metadata. Changing a shared record requires withdrawing
sharing first. Withdrawal and deletion immediately remove server-side clinician
visibility; they cannot retract information already downloaded by the clinician.

Explicit withdrawal of processing consent stops further editing. A new intake
requires new consent. Sharing withdrawal alone retains processing consent and
allows further editing followed by a new review and approval.

## Persistence and concurrency

SQLite uses WAL, foreign keys, private database file permissions and per-request
connections. The `get_connection()` context manager commits on success, rolls back
on error, and always closes. `save_intake()` compares the stored `revision` with the
loaded revision and rejects stale writes. A conflicting HTTP update returns 409.
Provider calls execute outside database write transactions. `mutate_intake()` is
reserved for brief local mutations, such as attachment metadata.

The local database and attachments persist across server restarts. File permissions
protect them from other ordinary OS accounts; this is not application-level
encryption. Protect the Mac account, enable disk encryption, and keep any backups
private. Deleting an intake removes its database row and its upload directory.
There is no OSS dependency for this single-Mac deployment.

## Regression checks

Run from `backend` using the repository virtual environment:

```sh
../.venv/bin/python -m pytest tests/test_product_auth.py tests/test_product_api.py -q
```

Tests use disposable databases and mocked email/model calls. They exercise code
expiry, one-time use, brute-force lockout, cookie revocation, CSRF, clinician role
restrictions, patient isolation, assignment, approval versions, withdrawal,
deletion and concurrent edits. Passing these tests does not certify a public
healthcare deployment or establish external provider availability.
