# Integration validation — 5 October 2026

## Delivered source and runtime

Complete upstream repository cloned from `rkim9125/elec5623-group9-preconsultation`, based on `36a10c4`. Local integration branch: `codex/integration`. The original teaching modules and tests remain in the checkout. Product UI is built from `frontend/src/product/`; the authenticated server extends FastAPI in `backend/app/product/`.

The final production bundle and backend were started on `127.0.0.1:8000` with `scripts/start-local.sh`. The database and uploads are persistent local files. The test-only server on port 8001 was stopped after browser verification. No public server was deployed, and no GitHub push or PR was created.

## Automated checks

- Backend: **434 tests passed**, including original engine/database tests, all 30 baseline forms and their optional guided inputs, exact selection evidence, adaptive planning, cited synthesis, corrections, authentication, ownership, media and deployment boundaries.
- Frontend: **74 tests passed** (55 preserved regressions, four navigation/save-boundary tests and 15 guided-answer/body-region tests); ESLint and production Vite build passed.
- Browser acceptance: **52 checks passed**: 38 for the full patient/doctor flow and 14 for illustrated questions. These cover real API sessions, multiple/custom topics, no-category preparation, form autosave, navigation, provider outages, versioned approval, genuine synthetic AI summaries, sharing/revocation, keyboard body-map selection, patient left/right, exact selection/custom-text reload, unknown/declined/reset and single-choice replacement. Twenty-four screenshots and both machine-readable reports are in `docs/screenshots/v3/`; the previous evidence remains in `docs/screenshots/v2/`.
- Accessibility: eighteen scanned desktop/390px mobile states had zero serious or critical axe violations. This is a bounded automated check, not a complete accessibility certification.
- No browser JavaScript errors or tested horizontal-overflow failures remained.
- Git whitespace check and supplied-credential scan passed. Credentials exist only in ignored, private `backend/.env`, never in the browser bundle or committed source.

The browser suite uses temporary synthetic users and real server-side cookie sessions in an isolated test database. It does not insert a production login bypass. A genuine model-generated synthetic summary from the separate live test is seeded for presentation checks; browser tests themselves disable external providers. Email OTP hashing, expiry, single-use, rate limiting and delivery-error handling are tested with a mocked mail adapter.

## V2 product behavior

The revised journey is topic selection, a grouped baseline form, optional adaptive follow-up, then summary review and explicit sharing. The interface uses warm ivory surfaces, teal controls, readable text, 30 topic-specific icons, responsive stages and distinct patient/clinician summary views. Fixed workflow questions offer optional single/multiple-choice cards and seven anatomical diagram families, including front-only shins and rear-only calves. Equivalent labelled buttons support keyboard/mobile use. Selections never create default facts, and custom text remains available; exact medication, allergy, reading and date details remain text. Shared context is collected once. Unknown, declined and deferred answers retain their own states and are not repeated as baseline questions in chat.

The agent organizes form evidence, activates explicitly supported detail, chooses one eligible extra question at a time, and synthesizes concise English patient and clinician accounts. Its visible activity records measured model operations. Current facts have source references; omitted, superseded and private historical values are excluded from synthesis context. Corrections invalidate old summaries and approvals. Replacing a form value invalidates dependent extracted details. Removing a medicine preserves independently authored, unrelated form concerns while still withholding stale same-concern narratives.

## Live provider checks

The v2 live check (`scripts/smoke-product-v2.py`) uses synthetic input only and verified:

- GPT-6 Sol reads a bilingual form containing leg pain, sleep difficulties and a custom work-certificate concern.
- Two optional follow-up answers are processed without repeating baseline fields.
- Real patient-overview, clinician-brief, per-concern, agenda and uncertainty sections are generated with registered current-source references.
- A medicine-removal correction produces a new live summary version, removes the medicine and its dose/frequency from the clinician projection, and preserves the unrelated custom concern.

Earlier integration checks additionally verified these unchanged provider/media paths:

- Account access to `gpt-6-sol`, `gpt-5.6-sol`, and `gpt-4o-mini-transcribe`.
- GPT-6 Sol extracts separate leg and sleep concerns and activates the multiple-concern agenda without merging their onset descriptions.
- Review correction removes a synthetic medicine and its dose/frequency from the clinician handoff; the corrected version is reconciled and no deleted phrase remains in the projected handoff.
- OpenAI speech transcription returns the expected sentence from a computer-generated sample.
- PNG upload, private download, and GPT-6 Sol document reading.
- PDF upload and GPT-5.6 Sol document reading.

These checks establish the integration paths, not clinical accuracy across all cases. The 30-workflow catalogue and safety rules require clinical review before use as a real clinical service. A preparation completion indicator never establishes that waiting for an appointment is safe.

## Configuration still needed from the owner

`RESEND_FROM_EMAIL` is now configured as the owner-supplied `uni-proj@bittool.ai`; the server reports mail configuration present. `DOCTOR_EMAILS` still requires the intended clinician login address. The provided Resend key is restricted to sending email; its response to a domain-list query explicitly reported `restricted_api_key`. That query cannot verify the domain's sending status.

Live email delivery has not been tested by the agent; no real verification email was sent during automated checks. The owner can verify delivery through normal email-code sign-in. Add the clinician address through `scripts/configure-email.py` or `backend/.env`, then restart to enable that clinician account.

For ongoing operation, see [the local product guide](local-product.md).
