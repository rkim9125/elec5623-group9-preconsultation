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
      "slot_id": "symptom_duration",
      "text": "How many days have you had these symptoms?"
    },
    "updated_slots": ["chief_complaint", "associated_symptoms"]
  }
}
```

---

## 2. Session state object

Returned by `GET /api/sessions/{session_id}` and embedded (partially) in message
responses.

- `status`: `in_progress` | `awaiting_confirmation` | `completed` | `abandoned`
- `slots`: map of `slot_id` → [slot object](#3-slot-schema)
- `current_prompt`: the slot the intake flow is currently asking about, or `null`
- `summary_ref`: id of the generated summary once `status` is `completed`

```json
{
  "session_id": "sess_a1b2c3",
  "status": "in_progress",
  "created_at": "2026-09-10T04:15:00Z",
  "updated_at": "2026-09-10T04:20:00Z",
  "patient_ref": "pat_9f8e7d",
  "locale": "en-AU",
  "current_prompt": { "slot_id": "symptom_duration", "text": "How many days have you had these symptoms?" },
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
  "summary_ref": null
}
```

---

## 3. Slot schema

One structured field the intake flow tries to fill.

- `type`: `string` | `number` | `boolean` | `enum` | `date` | `list`
- `status`: `empty` | `candidate` (LLM-proposed, unconfirmed) | `confirmed` | `skipped`
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
`SLOT_NOT_FOUND` (404), `SLOT_VALIDATION_FAILED` (422), `LLM_UNAVAILABLE` (503),
`RATE_LIMITED` (429), `INTERNAL` (500).

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
