# API Contract — draft v0.1

> **Change rule:** any change to the API (routes, payloads, status objects, slot
> schema, error shape, or LLM candidate format) must be made in the **same PR**
> that changes the code, and this document updated to match. Assign the owner of
> each affected component (backend API, LLM extraction, frontend patient,
> frontend clinician) as a reviewer on that PR.

Status: **draft v0.1** — shapes are provisional and may change without deprecation
until v1.0.

## Conventions

- Base URL: `/api`
- Content type: `application/json`
- Timestamps: ISO 8601 UTC (`2026-09-10T04:20:00Z`)
- IDs: opaque strings; do not parse

---

## 1. Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET`  | `/api/health` | Liveness check |
| `POST` | `/api/sessions` | Create a pre-consultation session |
| `GET`  | `/api/sessions/{session_id}` | Fetch full session state |
| `POST` | `/api/sessions/{session_id}/messages` | Submit a patient message; returns updated state + next prompt |
| `POST` | `/api/sessions/{session_id}/slots/{slot_id}` | Confirm, edit, or skip a slot value |
| `POST` | `/api/sessions/{session_id}/complete` | Finalise intake and generate clinician summary |
| `GET`  | `/api/sessions/{session_id}/summary` | Clinician-facing structured summary |

All bodies are JSON. `POST /api/sessions` takes `{"patient_ref": null, "locale": "en-AU"}`
(both optional) and returns the [session state object](#2-session-state-object)
with `201`.

Example — `POST /api/sessions/{session_id}/messages`:

```json
{
  "request": {
    "text": "I've had a sore throat and a fever since Monday"
  },
  "response": {
    "session_id": "sess_a1b2c3",
    "status": "in_progress",
    "next_prompt": {
      "slot_id": "symptom_duration_days",
      "text": "How many days have you had these symptoms?"
    },
    "updated_slots": ["chief_complaint", "associated_symptoms"],
    "stopped": false,
    "stop_reason": null,
    "safety": { "triggered": false, "category": null, "message": null },
    "completeness": { "coverage": 0.0, "resolution": 0.0, "unresolved_required": ["symptom_duration_days", "symptom_severity", "associated_symptoms", "current_medications", "allergies", "patient_worry", "appointment_goal", "clinician_questions"] }
  }
}
```

When `safety.triggered` is `true` the turn short-circuits: `stopped` is `true`,
`updated_slots` is empty, `next_prompt` is `null`, and `safety.message` carries
the fixed wording to show the patient.

Example — `POST /api/sessions/{session_id}/slots/{slot_id}`:

```json
{
  "request": { "action": "edit", "value": "moderate" },
  "response": {
    "session_id": "sess_a1b2c3",
    "status": "in_progress",
    "slot_id": "symptom_severity",
    "outcome": "accepted",
    "detail": null,
    "next_prompt": { "slot_id": "current_medications", "text": "..." },
    "completeness": { "coverage": 0.09, "resolution": 0.33, "unresolved_required": ["associated_symptoms", "current_medications", "allergies"] }
  }
}
```

`action` is `confirm` (promotes the top candidate, or uses `value` if given),
`edit` (requires `value`), `skip` (patient declined to answer), or `unknown`
(patient answered "I don't know" — distinct from `skip`, see
[slot schema](#3-slot-schema)). `outcome` is `accepted` / `rejected` /
`contradiction` / `inactive` / `unknown_slot`; a `rejected` value returns `422`.

Example — `POST /api/sessions/{session_id}/complete` → `{"session_id", "status": "completed", "summary_ref": "sum_sess_a1b2c3"}`.

Example — `GET /api/sessions/{session_id}/summary` (only after `complete`, else `409`):

```json
{
  "session_id": "sess_a1b2c3",
  "summary_ref": "sum_sess_a1b2c3",
  "sections": { "Main reason for the visit": "sore throat", "Current severity": "moderate" },
  "patient_questions": ["What are the most likely causes of my symptoms?"],
  "model": "fake-llm-0"
}
```

> **v0.1 gap:** there is no explicit "patient approves the summary" step yet.
> `completed` currently means the patient confirmed slots individually and hit
> finish. To be settled with C1/C2 before the clinician view is trusted.

---

## 2. Session state object

Returned by `GET /api/sessions/{session_id}` and embedded (partially) in message
responses.

- `status`: `in_progress` | `awaiting_confirmation` | `completed` | `abandoned`
- `schema_version`: consultation schema the session was created against (currently `"0.3"`)
- `slots`: map of `slot_id` → [slot object](#3-slot-schema)
- `current_prompt`: the slot the intake flow is currently asking about, or `null`
- `history`: append-only audit trail of slot state transitions (correction
  history) — see below
- `summary_ref`: id of the generated summary once `status` is `completed`

```json
{
  "session_id": "sess_a1b2c3",
  "status": "in_progress",
  "created_at": "2026-09-10T04:15:00Z",
  "updated_at": "2026-09-10T04:20:00Z",
  "patient_ref": "pat_9f8e7d",
  "locale": "en-AU",
  "schema_version": "0.3",
  "current_prompt": { "slot_id": "symptom_duration_days", "text": "How many days have you had these symptoms?" },
  "slots": {
    "chief_complaint": {
      "slot_id": "chief_complaint",
      "label": "Chief complaint",
      "type": "string",
      "required": true,
      "value": "Sore throat and fever",
      "status": "candidate",
      "source": "llm"
    }
  },
  "transcript": [
    { "role": "patient", "text": "I've had a sore throat and a fever since Monday", "at": "2026-09-10T04:19:50Z" },
    { "role": "assistant", "text": "How many days have you had these symptoms?", "at": "2026-09-10T04:20:00Z" }
  ],
  "history": [
    {
      "slot_id": "symptom_severity",
      "event": "corrected",
      "previous_value": "mild",
      "previous_status": "confirmed",
      "new_value": "moderate",
      "new_status": "confirmed",
      "source": "patient",
      "at": "2026-09-10T04:21:00Z"
    }
  ],
  "summary_ref": null
}
```

`history` entries are append-only — nothing in the backend ever edits or removes
one. `event` is `confirmed` (first value set), `corrected` (a confirmed value
changed), `skipped`, `marked_unknown`, or `reopened` (a skipped/unknown slot
got new candidate evidence). Re-confirming an already-confirmed slot with the
same value does not add an entry, and a rejected edit (`422`) never reaches
history. C6 persists this list verbatim — it's the provenance/correction-history
trail the proposal requires.

---

## 3. Slot schema

One structured field the intake flow tries to fill.

- `type`: `string` | `number` | `boolean` | `enum` | `date` | `list`
- `status`: `empty` | `candidate` (LLM-proposed, unconfirmed) | `confirmed` |
  `skipped` (patient declined to answer) | `unknown` (patient answered "I don't
  know" — an affirmative answer, not a decline; present it differently in the
  clinician summary)
- `source`: `patient` (typed directly) | `llm` (extracted) | `clinician` (overridden)
- `options`: present only when `type` is `enum`
- `candidates`: [LLM candidate values](#5-llm-extraction-candidate-value) not yet confirmed

```json
{
  "slot_id": "symptom_duration_days",
  "label": "Symptom duration (days)",
  "type": "number",
  "required": true,
  "options": null,
  "value": null,
  "status": "candidate",
  "source": "llm",
  "candidates": [
    {
      "value": 3,
      "confidence": 0.72,
      "evidence_span": "since Monday",
      "model": "gpt-4o-mini",
      "extracted_at": "2026-09-10T04:20:01Z"
    }
  ],
  "updated_at": "2026-09-10T04:20:01Z"
}
```

---

## 4. Error response format

All non-2xx responses use this envelope. HTTP status carries the class; `error.code`
is the stable machine string.

- `code`: stable `SCREAMING_SNAKE_CASE` identifier
- `message`: human-readable, safe to show to the patient
- `details`: optional array of field-level problems
- `request_id`: echo for support / log correlation

```json
{
  "error": {
    "code": "SLOT_VALIDATION_FAILED",
    "message": "Symptom duration must be a whole number of days.",
    "details": [
      { "field": "value", "issue": "expected number, got \"a while\"" }
    ],
    "request_id": "req_5k4j3h"
  }
}
```

Common codes: `SESSION_NOT_FOUND` (404), `SESSION_ALREADY_COMPLETED` (409),
`SLOT_NOT_FOUND` (404), `SLOT_VALIDATION_FAILED` (422),
`REQUEST_VALIDATION_FAILED` (422, malformed/mistyped body — FastAPI's own
validation, normalised into this envelope), `SUMMARY_NOT_READY` (409),
`LLM_UNAVAILABLE` (503), `RATE_LIMITED` (429), `INTERNAL` (500, catch-all for
anything unhandled — also normalised into this envelope).

C6 adds `PERSISTENCE_CONFLICT` (409) for stale concurrent updates or SQLite lock
contention. Reload the session before retrying. Requests commit database writes
before reporting success; summary generation and session completion are atomic.
The existing request/response shapes are unchanged. The explicit patient-summary
approval gap described above remains open; database approval metadata does not
add an approval endpoint. See [database.md](database.md) for transaction and DAO contracts.

---

## 5. LLM extraction candidate value

Emitted by `app/llm/` when parsing a patient message into slot values. Never
written straight to `slot.value`; it lands in `slot.candidates[]` with
`status: "candidate"` until confirmed by the patient or clinician.

- `slot_id`: target slot
- `value`: typed per the slot's `type`
- `confidence`: model-reported, `0.0`–`1.0`
- `evidence_span`: verbatim substring of the patient message supporting the value
- `rationale`: short model explanation (for review UI / debugging)
- `model`: model id used, for reproducibility

```json
{
  "slot_id": "associated_symptoms",
  "value": ["fever", "sore throat"],
  "confidence": 0.88,
  "evidence_span": "a sore throat and a fever",
  "rationale": "Both symptoms stated explicitly in the same sentence as the complaint.",
  "model": "gpt-4o-mini",
  "extracted_at": "2026-09-10T04:20:01Z"
}
```
