# Local product guide

This integration builds on the complete upstream repository at `36a10c4` on local branch `codex/integration`. The original React components, FastAPI state engine, database migrations and tests are retained. The authenticated product extends the application under `backend/app/product` and `frontend/src/product`; the old unowned `/api/sessions` API is disabled by default.

## Open the product

- Patient: http://127.0.0.1:8000/#/patient
- Doctor: http://127.0.0.1:8000/#/doctor
- Start: double-click `Start Preconsultation.command`, or run `bash scripts/start-local.sh` from the repository.
- Stop: `bash scripts/stop-local.sh`.
- Status: `.venv/bin/python scripts/local-server.py status`.
- Logs: `.local/server.log` (HTTP access logs disabled to reduce sensitive metadata).

The startup script builds the React bundle and serves both web interfaces and the API on one localhost address. SQLite starts inside the application. Docker, a separate database service, and Aliyun OSS are not needed for this local deployment. The server binds only to the Mac's loopback interface. Keep the Mac awake while using it; restart after reboot. Use separate browser profiles or an incognito window to test patient and doctor sessions simultaneously. Microphone access requires browser permission. Localhost is a browser secure context; remote microphone use requires HTTPS.

Patient and doctor portals share one browser session. Opening the other portal keeps the requested URL and shows an explicit identity-switch screen; it never silently redirects to the current role or grants another role. Choose **Sign out and continue to doctor sign-in** (or the patient equivalent), then verify the appropriate email. The doctor email still requires administrator authorization. Returning to a tab rechecks the server identity and clears the old workspace when the server reports an identity change. Each portal's home logo stays within that portal.

## Finish email setup

The application has no password login, fixed verification code, or demo authentication bypass. It sends a single-use six-digit code through Resend, valid for ten minutes. Doctor emails must be explicitly configured; selecting the doctor portal does not grant doctor access.

1. Set `RESEND_FROM_EMAIL` to a sender on a domain verified in your Resend account.
2. Set `DOCTOR_EMAILS` to the clinician login address(es), comma separated.
3. Restart the server.

Run `.venv/bin/python scripts/configure-email.py` for an interactive setup. Resend's test sender `onboarding@resend.dev` is suitable only where the account's testing restrictions permit the recipient; use a verified domain for general patient sign-in. A sending-only API key cannot query sending domains, so a rejected domain-list request does not prove sending is broken.

`backend/.env` contains local service credentials, has mode 600, and is ignored by Git. The browser bundle receives no API credentials. Because the credentials were pasted into a conversation, rotate them before any public deployment.

## Patient and clinician workflow

1. Sign in to the patient portal using an email code. Enter your preferred name if desired.
2. Select any combination of the 30 preparation topics, add custom concerns, or continue without a predefined category. Consent to AI processing is explicit.
3. Complete the grouped baseline form in one pass. Select illustrated body areas or answer cards where available, and add your own details. Common medicines, allergies, background and goals are collected once; each concern has its own fixed workflow questions. Save a draft, answer unknown, or choose not to answer. You may continue with an incomplete form.
4. The AI checks the recorded information and asks bounded, relevant additional questions. Baseline questions are not repeated in chat. Each extra question explains its purpose; finish at any time. Voice transcription and optional document reading return editable text for patient confirmation. PDF/JPEG/PNG/WebP uploads remain private until approved sharing.
5. Generate an AI summary with a patient overview, clinician brief, concern summaries, appointment agenda and uncertainties. Expand source references to compare the wording with the current recorded facts. Correct or remove details before approving. A failed AI operation is explicitly labelled; structured fallback notes remain available. Existing unapproved summaries can be regenerated through the same review action.
6. Explicit approval shares exactly that reviewed version with the selected configured clinician.
7. The clinician signs in to the doctor portal using their allowlisted email and reads approved assigned summaries and attachments. They can mark a summary reviewed and print it.
8. Withdrawing sharing immediately removes doctor access. Deleting a preparation removes its local record and uploaded files. Downloads/printouts already made by a clinician cannot be recalled.

## Illustrated questions

The light ivory and teal interface gives all 30 topics a specific anatomical or care-related icon. Location questions have interactive diagrams for legs, lower back, neck/shoulders, arms/hands, head, abdomen, and skin/body locations. Front/back views explicitly label the patient's own left and right. Every selectable diagram region also has a labelled button; the diagram is a location aid, not a diagnostic image or a substitute for a precise description.

Choice cards help describe patterns, sensations, sleep difficulties, daily impact and appointment priorities. Single-choice questions replace the earlier selection; multi-choice questions allow several answers. No option is selected automatically. Medicines, allergies, exact readings, dates and personal narratives remain editable text where precise information is needed. Existing text is preserved visibly rather than interpreted as a selection.

Choices and optional detail are saved as human-readable patient-authored text through the same baseline API. Unknown and declined statuses keep their existing meaning. These presentation changes do not add diagnostic scores, advice or automatic clinical interpretation.

## Models and data flow

Default: `gpt-6-sol`. Alternate: `gpt-5.6-sol`. Speech: `gpt-4o-mini-transcribe`. These IDs were verified against official OpenAI documentation and the configured account's model listing during integration. Separate bounded Responses operations extract facts and activation signals, choose useful extra questions from backend-eligible targets, and synthesize the final patient/clinician summary. The backend controls applicability, stopping, source IDs, corrections and approval. Actual operation/model/latency records support the university demonstration; they are not clinical quality scores. A provider error is visible, not silently represented as live AI. The baseline form remains usable during an API outage.

Text submitted to the agent goes to OpenAI. Voice audio goes to OpenAI for transcription and is not retained by this app. Uploaded documents are kept locally; clicking document reading sends the selected file to OpenAI. Responses requests use `store:false`, which is not a guarantee of zero provider-side retention. Email addresses go to Resend solely to deliver sign-in codes. Review provider data-processing settings before using real patient data.

The 30 workflow templates and source are preserved in `docs/workflows-30-source.md`. They are preparation templates, not clinically validated protocols or a triage system. Safety interruption wording inherited from the academic prototype has not received clinical sign-off. This deployment must not be represented as a validated medical device or an emergency service. Before a real clinical rollout, arrange review of the clinical protocol, consent, privacy, retention and operational responsibilities.

## Storage and recovery

- Application database: `backend/data/product.sqlite3` (SQLite WAL, private filesystem permissions).
- Uploads: `backend/data/uploads/` (opaque IDs, 10 MB/file, up to 12 per preparation; PDF limit 30 pages).
- Server credentials: `backend/.env`.

Stop the service before a filesystem backup, then copy `backend/data/` and retain credentials separately in a secure store. An online SQLite backup must use SQLite's backup API; copying only the main database file while it is running can omit WAL changes. FileVault protects the Mac's disk when locked; this app does not itself encrypt each database row or file. Patient and clinician account isolation, cookie session expiry, CSRF checks, OTP rate limits and attachment authorization are enforced server-side.

## Public server option

Local use is supported without a real server. To serve other people's devices reliably, use a server with a persistent disk, TLS reverse proxy, process supervision and backups. Build the frontend, install backend dependencies, set `APP_ENV=production` and `APP_BASE_URL`/`FRONTEND_ORIGIN` to the HTTPS origin, mount persistent `PRODUCT_DB_PATH`/`UPLOAD_DIR`, and run a single Uvicorn worker. Production cookies require HTTPS. Keep secrets in the host's secret manager. Restrict proxy trust to your reverse proxy.

SQLite is appropriate for this single-instance local product. Horizontal scaling requires a shared transactional database and shared attachment storage; OSS is an option then. No public hosting account has been provisioned, purchased, or deployed by this integration.

## Verification

An optional v2 live synthetic check is available as `.venv/bin/python scripts/smoke-product-v2.py`. It exercises a bilingual, three-concern baseline, adaptive turns, final synthesis and a removal correction using several billable OpenAI calls. It does not use real accounts or the product database and never runs automatically. Its synthetic output can seed `scripts/product-browser-server.py` for visual checks without additional provider calls. The earlier extraction-only smoke remains in `scripts/smoke-openai.py`.

For a university demonstration, show the grouped form, the optional question and its purpose, the recorded model operations, the two summary perspectives, and a source reference. Then correct a fact, generate a new version, approve it and open the clinician view. This demonstrates implemented behavior without claiming superior clinical outcomes. Source-ID, ownership, uncertainty and numeric checks reduce specific failure modes; they do not prove full semantic entailment or clinical accuracy. Human review remains part of the workflow.

Run product tests from `backend/` with `../.venv/bin/python -m pytest tests/test_product*.py`. Historical teaching API regression tests use `FRONTEND_ORIGIN= ENABLE_LEGACY_API=1 ../.venv/bin/python -m pytest`; never enable that variable in a running deployment. Run frontend checks with `npm test`, `npm run lint`, and `npm run build` in `frontend/`. Product browser tests use isolated synthetic data and are separate from the preserved upstream mock-UI browser scenarios.

## References

- [GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol)
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [OpenAI speech transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI file inputs](https://developers.openai.com/api/docs/guides/file-inputs)
- [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction)
