# Integration validation — 5 October 2026

## Delivered source and runtime

Complete upstream repository cloned from `rkim9125/elec5623-group9-preconsultation`, based on `36a10c4`. Local integration branch: `codex/integration`. The original teaching modules and tests remain in the checkout. Product UI is built from `frontend/src/product/`; the authenticated server extends FastAPI in `backend/app/product/`.

The final production bundle and backend were started on `127.0.0.1:8000` with `scripts/start-local.sh`. The database and uploads are persistent local files. The test-only server on port 8001 was stopped after browser verification. No public server was deployed, and no GitHub push or PR was created.

## Automated checks

- Backend: **257 tests passed**, including original state-engine/database tests and new catalogue, agent, provider, authentication, authorization, media and deployment tests.
- Frontend: **55 preserved regression tests passed**; ESLint and production Vite build passed.
- Browser acceptance: **25 checks passed**, including the real patient/doctor API flow and desktop/390px mobile layouts. Ten screenshots and a machine-readable report are in `docs/screenshots/integration/`.
- Accessibility: seven scanned states had zero serious or critical axe violations. This is a bounded automated check, not a complete accessibility certification.
- No browser JavaScript errors or tested horizontal-overflow failures remained.
- Git whitespace check and supplied-credential scan passed. Credentials exist only in ignored, private `backend/.env`, never in the browser bundle or committed source.

The browser suite uses temporary synthetic users and real server-side cookie sessions in an isolated test database. It does not insert a production login bypass. Email OTP hashing, expiry, single-use, rate limiting and delivery-error handling are tested with a mocked mail adapter.

## Live provider checks

Real calls using synthetic input verified:

- Account access to `gpt-6-sol`, `gpt-5.6-sol`, and `gpt-4o-mini-transcribe`.
- GPT-6 Sol extracts separate leg and sleep concerns and activates the multiple-concern agenda without merging their onset descriptions.
- Review correction removes a synthetic medicine and its dose/frequency from the clinician handoff; the corrected version is reconciled and no deleted phrase remains in the projected handoff.
- OpenAI speech transcription returns the expected sentence from a computer-generated sample.
- PNG upload, private download, and GPT-6 Sol document reading.
- PDF upload and GPT-5.6 Sol document reading.

These checks establish the integration paths, not clinical accuracy across all cases. The 30-workflow catalogue and safety rules require clinical review before use as a real clinical service. A preparation completion indicator never establishes that waiting for an appointment is safe.

## Configuration still needed from the owner

`RESEND_FROM_EMAIL` and `DOCTOR_EMAILS` remain empty because the owner has not supplied a verified sending address/domain or clinician account address. The provided Resend key is restricted to sending email; its response to a domain-list query explicitly reported `restricted_api_key`. The key cannot be used to discover the verified sender.

Therefore, live email delivery and a genuine email-code login have **not** been verified. The running login screen accurately reports that email setup is incomplete. No real verification email has been sent. Supply those addresses, run `scripts/configure-email.py` or edit `backend/.env`, restart, and complete a real OTP login to finish owner configuration.

For ongoing operation, see [the local product guide](local-product.md).
