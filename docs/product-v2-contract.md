# Preparation experience v2

Patient journey: choose topics → grouped baseline form → optional adaptive follow-up → AI summary and correction → explicit approval. Existing sessions remain readable; approved versions cannot change until sharing is withdrawn. All interface text is English.

## API and ownership contract

`POST /api/v1/intakes` adds `custom_concerns: string[]` (max 10, each max 150). Empty predefined and custom selections are valid and create a GENERAL concern. New sessions have `experience_version: 2`, `stage: baseline`, and `baseline: {completed: false}`. The existing status field retains active/review/approved/etc semantics.

`GET /api/v1/intakes/{id}/form` returns `{groups: [{id, title, description, fields: [{concern_id, key, label, question, value, status, required, input_type, requires_permission}]}], completed: boolean, revision: number}`. Shared background is collected once. Topic fields come from the fixed workflow bank; additional conditional fields belong to follow-up. `required` identifies core preparation information; patients may still leave it unresolved, answer unknown, or decline. Form may be saved incomplete.

`PUT /api/v1/intakes/{id}/baseline` accepts `{answers: [{concern_id, key, value: string|null, status: FILLED|UNCERTAIN|SKIPPED|MISSING}], complete: boolean, revision?:number}`. Each answer is limited to 6,000 characters. Validate all fields before applying; preserve exact form evidence. Empty fields remain MISSING. Draft save returns public session. Complete accepts partial preparation, marks missing baseline fields as deferred (never pretends skipped), calls `pipeline.start_followup(session)`, returns public session. Never repeat baseline questions in chat, including baseline fields left unanswered. Follow-up can use newly activated extra fields and other explicitly relevant schema fields. `stage` becomes `followup`. The UI supplies revisions, serializes autosaves and flushes unsaved changes before navigation. `POST /intakes/{id}/followup` retries optional AI after a completed form without resetting the question budget.

Normal messages and review use `pipeline.process_message(session,text,action)` and `pipeline.build_review(session,correction=None)`. These wrap the existing evidence engine and preserve safety, correction reconciliation, uncertainty, skipped fields, revision protection, and approval boundary. Legacy sessions may use the form endpoint and baseline flow too. `stage` becomes `review` after summary.

## Adaptive AI contract

`session.assistant` is `{mode: live|unavailable|ready, overview: string, focus: string, rationale: string, suggested_topics: string[], questions_remaining: number, question_count: number}`. `current_question` retains `{key, concern_id?, question}` and may add `why`. Backend validates AI-selected targets against eligible missing non-baseline fields and bounds follow-ups (default 6). Unknown/skipped/answered targets are never repeated. Concise visible rationale describes purpose; no hidden chain of thought. Honest unavailable state offers review/retry instead of long fallback interviews.

`session.ai_activity` is a bounded array of `{operation, model, status, duration_ms, created_at}` for actual operations; no simulated latency or quality scores.

## Summary contract

Existing deterministic `summary.sections/gaps/text` remain for evidence and fallback compatibility. New `summary.synthesis` is `{status: live|unavailable, model, generated_at, patient_overview: [{text,source_ids:string[]}], clinician_brief: [{text,source_ids:string[]}], concern_summaries: [{concern_id,title,summary,source_ids:string[]}], appointment_agenda: [{text,source_ids:string[]}], uncertainties: [{text,source_ids:string[]}], sources: [{id,concern_id,key,label,value,status}], message?:string}`.

Synthesis uses only current handoff-eligible facts and explicit uncertainty, no raw transcript/history/superseded facts. Backend validates cited IDs and concern ownership. No diagnosis, causal speculation, report interpretation, triage, or treatment suggestions. English prose preserves original-language facts in source details. Patient must review translations. AI unavailable clearly labels structured notes; never calls fallback notes AI-generated. Corrections regenerate synthesis only after successful reconciliation; pending corrections block approval. Regeneration upgrades old unapproved summaries through existing review POST. Clinician reads the exact approved version and sees source-backed current facts, not private conversation/history.

## Presentation

Crisp navy/blue/white visual system, readable 16px body, responsive sidebar/header, clear 4-stage progress, compact topic selection with multi-select and custom concerns, grouped baseline form with autosave/draft status and one continue action. AI follow-up has question purpose and optional conversation, summary has separate patient and clinician views plus expandable source details. Doctor workspace prioritizes concise approved brief and per-concern information. Existing voice, upload, extracted-text confirmation, approval, withdrawal and auth isolation remain functional.
