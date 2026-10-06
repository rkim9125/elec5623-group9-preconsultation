# AI assessment and complete report export

This addition extends the integration product beyond the historical proposal's factual-summary scope. The existing workflow forms, adaptive follow-up and cited factual synthesis retain their original contracts. The separate assessment offers preliminary diagnostic possibilities and consultation guidance; it does not establish a diagnosis, replace examination or certify that waiting is safe.

## API

- `POST /api/v1/intakes/{id}/ai-report` generates and persists an assessment; returns the report object. It requires an existing current summary, AI-processing consent, authenticated ownership or current assigned clinician access, same-origin CSRF checks and rate limiting.
- `GET /api/v1/intakes/{id}/ai-report` returns `{ai_report: object|null}` for the current authorized record.
- Normal patient and clinician intake projections include `ai_report` only while its inputs remain current.
- `GET /api/v1/intakes/{id}/report.pdf` returns a private downloadable PDF with the factual summary, any current AI assessment, evidence and all attachments. It never invokes the provider.

Unauthorized users cannot discover or download a record. Clinician access requires the current approved sharing assignment. Generating an assessment leaves the approved factual summary unchanged. A report generated before sharing can remain valid after approval if its clinical inputs have not changed. Source corrections or attachment changes make the previous assessment stale. Revocation prevents further clinician access, including an in-flight generation or export.

## Assessment content

The report contains generation metadata, an overview, possible diagnoses with evidence and uncertainty, care guidance, suggested next steps, warning symptoms, missing information, attachment-by-attachment findings and limitations. Source references identify either current recorded facts or an attachment. Diagnostic hypotheses and general guidance are distinguished from source facts; references are not claims of clinical validation.

The provider receives current handoff-eligible sources and every uploaded image/PDF. It does not receive private chat history, old correction history, superseded slot values, local filesystem paths or API credentials as content. Source values and file contents are untrusted data, including any embedded instructions. Provider refusal, invalid output or any failed file input produces a visible error instead of a fabricated assessment.

Specialized medical images require clinical interpretation. The prompt explicitly prohibits diagnosing an X-ray, CT/MRI scan, ultrasound or ECG trace from pixels. Written medical findings are attributed to the uploaded report. Missing facts remain missing, and no finding is invented to complete a differential. AI care-timing suggestions are unvalidated guidance, never an assurance that a serious condition has been excluded.

## PDF

The server composes the report locally with ReportLab and pypdf. The document separates AI assessment, patient-reported summary and source evidence. An attachment index precedes full proportional image pages and all original pages of each uploaded PDF. Export preserves image orientation and handles multilingual source text. Untrusted PDF actions and active content are removed from the exported appendix.

All files must be available and readable; a missing attachment fails the export. Current authorization is rechecked before returning the result. Responses are non-cacheable. Report download does not create a public file URL or send attachments to another service. Existing upload limits remain 12 attachments per intake, 10 MB per file and 30 pages per PDF.

Animated WebP/APNG files include every frame, up to 30; larger animations produce an explicit conversion message instead of silently exporting one frame. The local Mac deployment embeds an available system Unicode font for multilingual source text. Other hosts should provide a compatible Unicode font for portable rendering.

## Product flow

New patient summary creation starts a separate assessment request with a visible progress state. The factual summary is available while generation runs. Existing records show **Generate AI assessment** in both authorized portals. **Regenerate assessment** explicitly runs the model again. Failures can be retried without losing a valid previous report. **Download complete PDF** is available from both review screens; a PDF generated without an assessment explicitly states that it is unavailable.

The main report heading is **AI diagnosis & consultation guidance**, with a prominent preliminary-status label. Clinician “Mark as reviewed” records viewing/review workflow only; it is not a medical signature or a confirmed diagnosis.

## Verification

`scripts/smoke-assessment.py` makes a billable live OpenAI call using the synthetic v2 fixture and newly generated diary image/two-page PDF. It never reads the product database or real patient files. It checks both file reviews, source validation and complete PDF export. Its output is stored under ignored `.local/assessment-smoke/`.

`scripts/test-assessment-browser.mjs` runs against the isolated `scripts/product-browser-server.py` on port 8001. It verifies the actual report display, authenticated PDF download, sharing/revocation and mobile accessibility; AI loading/error cases are explicitly simulated with browser routes. The server disables external AI and email providers. Backend tests cover structured provider output, attachment completeness, stale results, concurrent revocation, PDF content/layout inputs and explicit out-of-scope clinical assertions. These engineering checks are not clinical validation or proof of diagnostic accuracy.
