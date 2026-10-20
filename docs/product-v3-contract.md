# Preparation experience v3

The patient starts with a symptom from the existing 30-workflow catalogue, or the first “Something else” option for a direct conversation. Guided preparations show one question at a time. Existing `/form` and `/baseline` endpoints are data contracts retained for draft compatibility, not a requirement to render a long form.

## Intake creation and conversation

`POST /api/v1/intakes` retains consent, model, workflow IDs, title and custom concerns, and adds:

- `mode`: `wizard` (default) or `chat`.
- `locale`: `en` (default), `zh-CN`, `zh-TW`, `ko`, or `ja`.
- `use_profile`: defaults to `true`; `false` starts without reusable background.

New preparations have `experience_version: 3`. Wizard mode starts at `stage: baseline`. Chat mode starts at `stage: followup`, with a localized conversational opener and `baseline.completed: true`. An empty chat does not fabricate a GENERAL concern; extraction organizes the patient's first message. A provider failure retains that narrative as patient-reported text. Chat uses the same ownership, consent, safety, evidence and approval boundaries as the wizard.

`PUT /intakes/{id}/baseline`, `POST /intakes/{id}/messages`, and `PATCH /intakes/{id}/review` accept optional `locale` to update the active preparation when the patient switches language. `POST /intakes/{id}/review`, `/followup` and `/ai-report` also accept an optional `{locale}` body; a missing body remains valid. Locales are enumerated server-side; arbitrary instruction text is rejected. Locale is passed to extraction, planning, synthesis and uploaded-document processing. Original source values, quantities, units and IDs remain verbatim. Patient-facing questions, suggestion labels and values, concern/disease names, generated report prose and PDF structural labels use the patient's selected language. Clinical question identity still comes from the curated workflow bank.

`POST /intakes/{id}/locale` accepts `{locale, revision?}` for an owned, editable preparation. The language switch first flushes the current draft. Pending questions are translated in place, with unchanged batch/question IDs, draft answers and question budget; this is not another interview round. A failed translation leaves the stored session unchanged. Legacy pending batches without language metadata use the same migration path. Existing generated summaries and assessments carry their generation language; a language change requires explicit regeneration before sharing, not a relabeling of English prose. Approved records retain their original generated text until sharing is withdrawn. Deterministic factual headings can be localized in a read-only projection without changing the approved evidence.

Backend authored terminology is generated from the frontend catalogue with `node scripts/build-backend-locales.mjs`. Model prompts explicitly localize all display fields; script checks reject gross wrong-language output and allow one repair request using the same evidence. These checks do not claim perfect linguistic or clinical validation. Original patient quotations, identifiers, medication identities and uploaded source documents remain available as source evidence.

Assessment freshness hashes retain canonical source labels and concern titles, independently of translated display labels, so a catalogue update does not invalidate an approved report. Changes to clinical facts, source status, patient language, summary, profile snapshot or uploaded file contents still invalidate it. Sharing checks enforce summary/assessment language on the server as well as in the UI; an optional assessment is never required merely to share factual notes.

## Remembered background

The patient profile API is `GET /api/v1/auth/profile` and `PUT /api/v1/auth/profile`; both return `{profile: {...}}`. The structured allowlist contains date of birth, sex at birth, blood group, medical/surgical/family history, and communication/accessibility needs. It includes update timestamps. Unknown blood group and declined sex-at-birth remain uncertainty/refusal rather than positive clinical findings.

New intakes copy `profile_snapshot`, so later account edits cannot rewrite an earlier appointment. If DOB is supplied, the snapshot derives `age_years` and `age_as_of` at creation; the reusable profile never stores an aging age value. DOB remains the original patient-reported value, while age is clearly labelled as calculated in AI/report sources. Durable histories prefill the editable shared `relevant_history` slot with `patient_profile` provenance. The field includes `profile_reused: true` until edited. Current medicines, allergies, symptoms, pregnancy status, readings, weight and other per-visit data are never automatically carried forward. The existing wizard answer endpoint allows an appointment-specific correction without changing the account profile. Clinician snapshots omit original history copies, so a corrected/removed history cannot reappear alongside the approved current slot.

Blood group uses two levels in the profile: ABO (`A`, `B`, `AB`, `O`, or unknown) and optional Rh (`+`, `-`, or unknown). ABO-only values are accepted without inferring Rh; existing combined values remain compatible. The leg map accepts multiple selected locations across both sides and views while preserving existing authored details.

The first symptom question asks for a brief description and provides a concrete example for leg discomfort. The sequential wizard combines medical-history additions, worries and questions for the clinician into optional `additional_information`. Existing `relevant_history`, `patient_worry` and `clinician_questions` remain editable as `review_only` fields, preserving old drafts and profile evidence without asking them again in sequence.

`GET /intakes/{id}/form` also returns `previous_answers` for medicines and allergies from an earlier owned encounter. Each suggestion has a recording date and `requires_confirmation: true`. Suggestions do not mutate the current visit; the patient must choose to fill one and can then edit it. Later refusals, uncertainty or explicit clearing suppress older answers. No additional copy of medical history is stored in browser storage or the reusable profile.

## AI analysis and grouped follow-up

The analysis step produces one `followup_batch` with at most five questions, displayed as a wizard with one question per step. Previous/next navigation saves the draft, and an unanswered question can be marked unsure or skipped. Refresh resumes at the first unfinished question, or the final answer review if all are complete. The final review allows editing any answer before one submission of the complete batch. Each question has a stable ID, wording, rationale and up to three optional answer suggestions; custom text, voice, unsure and skip remain available. Suggested answers are not preselected or treated as patient facts. Open-ended questions can have no suggestions.

`PUT /intakes/{id}/followup/draft` stores owned, revision-checked drafts separately from clinical evidence. `POST /intakes/{id}/followup/answers` accepts `{batch_id, answers: [{question_id, value, status}], revision?, locale?}` and requires every current question exactly once. Answers are submitted together, and one extraction processes the set. A normal batch proceeds to summary review without a second interview. Only a newly introduced, explicit medicine/allergy conflict can trigger one necessary clarification batch with an explanation; retries cannot expand the limit. Material baseline edits invalidate stale questions while retaining prior draft text for reference.

## Voice input

`POST /api/v1/transcriptions` accepts multipart `file` and optional `locale` (same five values, default English). It returns `{text, locale}` to populate the editable answer. English, Korean and Japanese map to `en`, `ko`, `ja`; both Chinese scripts use the transcription language `zh` with the selected script hint. Recording cancellation must not submit audio. Server transcription does not automatically save a clinical fact. Stopping a recording starts transcription; on success, the text is appended directly to the current input and follows the normal answer draft/autosave path. There is no separate transcript confirmation step. Wizard navigation is held while recording or transcription is active, and is available again after the input is filled. In chat the transcript populates the unsent message; it never sends automatically. Before the initial consultation, microphone controls require processing consent. Audio cancellation releases device tracks and does not upload; recording is limited to two minutes. The visual waveform reads actual microphone amplitude, and reduced-motion preferences disable decorative motion.

Pressing **Stop recording**, or reaching the two-minute limit, immediately transcribes the recording into editable text. There is no separate send action during recording; sending only submits reviewed text. Failed transcription retains the recording in memory for retry or discard.

The existing `gpt-4o-mini-transcribe` integration uses the singular `language` parameter documented for existing transcription models. See the [official OpenAI transcription documentation](https://developers.openai.com/api/docs/guides/speech-to-text).

## Models and clinician registration

The application default is `gpt-6-astra`, matching the [official model catalogue](https://developers.openai.com/api/docs/models). `OPENAI_MODEL` remains an administrator override; advanced options expose the configured model plus `gpt-6-astra`, `gpt-6-sol` and `gpt-5.6-sol`. The application never silently substitutes a different model. Model access errors retain notes and display an unavailable state.

Any valid email can register as patient or doctor. An email belongs to one permanent account role; a second role requires a different email. `/config.care_team` and approval validation use registered doctor accounts rather than `DOCTOR_EMAILS`. OTP verification, CSRF protection, explicit versioned patient approval, assigned-recipient checks and withdrawal continue to apply. No account can read an unapproved preparation simply by registering as a doctor.

## Local verification

Build with `cd frontend && npm run build`; `npm test` covers locale completeness, canonical answer preservation and existing frontend logic. Product tests run from `backend/` with a configured Python environment using `python -m pytest tests/test_product*.py`.

The repeatable browser check uses synthetic accounts and a dedicated SQLite database: run `backend/.venv/bin/python scripts/product-browser-server.py`, then `node scripts/test-wizard-browser.mjs`. This harness is separate from normal startup, disables outbound AI/email, and mocks microphone/transcription responses. It covers 30 topics, all five languages, profile round trips and per-visit corrections, ABO-only blood groups, explicit historical-answer quick-fill, merged background questions, transient-data exclusion, microphone consent/denial/cancellation/initialization failure, transcript review, keyboard focus, mobile visibility and accessibility. It also submits a grouped follow-up through the real draft/answer API, checking that drafts survive reload without becoming facts and that one submission proceeds to review. `node scripts/test-followup-browser.mjs` adds focused mocked checks for exceptional clarification, save failures and old-record migration. Screenshots and the JSON report are written under ignored `.local/wizard-browser/`. Live email delivery, real microphone devices and provider access require the deployment's own configured services and are not represented as verified by these harnesses.

`node scripts/test-localization-browser.mjs` uses a separate mocked loopback server to check all five languages, canonical symptom titles/search, translation of legacy pending questions, draft preservation before language changes, localized suggested-answer display, translation retry, stale summary/assessment share/export blocking and retention of approved originals.
