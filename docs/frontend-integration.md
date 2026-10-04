> Integration note: this document describes the preserved upstream prototype. For the running authenticated product, use [local product setup](local-product.md) and [the integration API contract](integration-contract.md). The legacy unauthenticated session API is disabled by default.

# Frontend → Backend integration guide

For whoever wires the UI (C1/C2) to the backend (C3). Nothing in this guide
requires a backend change — the API is live on `develop` today. If something
here doesn't fit the UI, say so and the contract gets changed, not worked
around.

Reference spec: [api-contract.md](api-contract.md). This guide is the practical
"how do I actually connect" version.

## 1. Run the backend

```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m app.db.manage init      # REQUIRED — creates the SQLite tables
uvicorn app.core.main:app --reload
```

`python -m app.db.manage init` is easy to miss and the failure is confusing:
every request returns `500 INTERNAL` with `no such table: sessions` in the
server log. Run it once; it is safe to repeat.

Check it's up: <http://localhost:8000/api/health> → `{"status":"ok"}`
Interactive API docs (try every endpoint from the browser):
<http://localhost:8000/docs>

**CORS:** leave `FRONTEND_ORIGIN` empty in `backend/.env` (or have no `.env`).
Empty means "any `localhost`/`127.0.0.1` port", which covers the Vite dev
server including when it falls back to 5174+. You do not need to tell the
backend which port you're on.

## 2. The call sequence

Six calls, in this order. Full request/response shapes are in
[api-contract.md](api-contract.md) §1.

| # | Call | When |
|---|---|---|
| 1 | `POST /api/sessions` | Patient starts. Returns the session; keep `session_id`. |
| 2 | `POST /api/sessions/{id}/messages` | Patient types free text. |
| 3 | `POST /api/sessions/{id}/slots/{slot_id}` | Patient answers/confirms/edits/skips one field. |
| 4 | `GET /api/sessions/{id}` | Re-read full state (e.g. rendering the review screen). |
| 5 | `POST /api/sessions/{id}/complete` | Patient finishes the intake. |
| 6 | `GET /api/sessions/{id}/summary` | Show the draft summary for review. |
| 7 | `POST /api/sessions/{id}/summary/approve` | Patient approves what they just read. |
| 8 | `GET /api/sessions/{id}/summary` | Clinician view — **only render it if `approved` is true**. |

### The one structural thing to know

**The backend chooses the next question.** Every response to calls 2 and 3
carries `next_prompt`:

```json
"next_prompt": { "slot_id": "symptom_severity", "text": "Right now, would you say it is mild, moderate or severe?" }
```

Render `next_prompt.text` and send the answer back against `next_prompt.slot_id`.
When `next_prompt` is `null` and `stopped` is `true`, the intake is done —
move to review.

This is the adaptive planning the proposal is built around: which field comes
next depends on what the patient already said, what's still missing, and
conditional rules (e.g. `fever_duration_days` only becomes askable once
`associated_symptoms` contains `"fever"`). A fixed client-side question order
will drift out of sync with it.

### Minimal client

Drop this anywhere in the frontend and adapt — it is a reference, not a
prescription.

```js
const BASE = "/api";  // or "http://localhost:8000/api" without a Vite proxy

async function call(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  const body = await res.json();
  if (!res.ok) throw Object.assign(new Error(body.error?.message), body.error);
  return body;
}

export const api = {
  createSession: () => call("/sessions", { method: "POST", body: "{}" }),
  getSession: (id) => call(`/sessions/${id}`),
  sendMessage: (id, text) =>
    call(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
  // action: "confirm" | "edit" | "skip" | "unknown"
  slotAction: (id, slotId, action, value = null) =>
    call(`/sessions/${id}/slots/${slotId}`, {
      method: "POST",
      body: JSON.stringify({ action, value }),
    }),
  complete: (id) => call(`/sessions/${id}/complete`, { method: "POST" }),
  getSummary: (id) => call(`/sessions/${id}/summary`),
  approveSummary: (id, version, approvedBy = "patient") =>
    call(`/sessions/${id}/summary/approve`, {
      method: "POST",
      body: JSON.stringify({ version, approved_by: approvedBy }),
    }),
};
```

A Vite proxy avoids CORS entirely if you prefer — in `vite.config.js`:

```js
server: { proxy: { "/api": "http://localhost:8000" } }
```

### Approval: the summary is a draft until the patient says otherwise

`complete` finishes the *intake*; it does not mean the patient has agreed to the
summary. `GET /summary` returns `version`, `approved` and `approved_at`.

- Patient review screen: show the summary, then on "this matches what I entered"
  call `approveSummary(id, summary.version)`.
- Clinician view: **check `approved` before presenting anything as the final
  handoff.** An unapproved summary is a draft the patient has not signed off.
- Pass back the `version` you displayed. If the summary was regenerated in the
  meantime you get `409 SUMMARY_VERSION_CONFLICT` — re-fetch and ask the patient
  to review again rather than approving text they never saw.

## 3. Patient controls → API actions

The four patient controls map onto one endpoint. **Skip and "I don't know" are
deliberately different** — the clinician summary shows them differently.

| UI control | Call |
|---|---|
| Answer / change an answer | `slotAction(id, slotId, "edit", value)` |
| Accept what the system extracted | `slotAction(id, slotId, "confirm")` |
| "Prefer not to answer" | `slotAction(id, slotId, "skip")` |
| "I don't know" | `slotAction(id, slotId, "unknown")` |
| Finish | `complete(id)` |
| "I have read the summary and it matches" | `approveSummary(id, version)` |

## 4. Field mapping

The current UI model and the backend schema were designed independently, so
names don't line up. This is the mapping as of schema `v0.3`.

| UI field (`model.js`) | Backend slot | Type | Note |
|---|---|---|---|
| `reasons[0]` | `chief_complaint` | string (required) | |
| `onset` | `symptom_duration_days` **or** `symptom_onset` | number / enum | See below — these are two different questions |
| `course` | `symptom_progression` | enum `improving/worsening/unchanged` | |
| `frequency` | — | — | No backend slot yet. Tell me if you need one. |
| `severity` | `symptom_severity` | enum `mild/moderate/severe` | UI currently sends Korean free text; needs to map to the three options |
| `impact` | `functional_impact` | string | |
| `history` | `past_conditions` | list | Backend also has `hospitalizations`, `specialist_care`, `family_history` if you want to split it |
| `medicines` | `current_medications` | list | |
| `allergies` | `allergies` | list | |
| `questions` | `clinician_questions` | list (required) | The patient's own questions; they now flow into the summary verbatim |
| — | `patient_worry` (required) | string | "What concerns you most?" — no UI field yet |
| — | `appointment_goal` (required) | string | "What do you want from the appointment?" — no UI field yet |
| — | `associated_symptoms` (required) | list | "Any other symptoms?" |

**`onset` is two questions in the backend.** `symptom_onset` is *how* it
started (`sudden` / `gradual`); `symptom_duration_days` is *how long* it has
been going (a number). The UI currently collects one field that mixes both.
Easiest fix: send the duration to `symptom_duration_days` and leave
`symptom_onset` alone (it's optional).

Three backend slots are **required** but have no UI field yet:
`patient_worry`, `appointment_goal`, `associated_symptoms`. Until they're
answered (or skipped), `complete` still works but `resolution` won't reach 1.0
and the summary will be missing the patient's agenda. Adding three questions is
the simplest route; skipping them via `"skip"` is the fallback.

The full slot list with types and options: `backend/app/core/schema.py`, or
`GET /api/sessions/{id}` on a fresh session.

### Status mapping

The UI's statuses and the backend's line up almost exactly:

| UI status | Backend `slot.status` |
|---|---|
| `unasked` | `empty` |
| `unanswered` | `empty` (or `candidate` if the system extracted a guess) |
| `answered` | `confirmed` |
| `unknown` | `unknown` |
| `declined` | `skipped` |
| — | `candidate` — extracted from free text, waiting for the patient to confirm |

`candidate` is the only new one: when the patient writes free text, the backend
proposes values but never commits them. `slot.candidates[]` holds the proposals
(with the evidence span they came from). Show them as "is this right?" and call
`confirm`, or `edit` to override.

## 5. Things that will bite

- **`complete` is one-way.** After it, messages and slot actions return `409`.
- **The summary is only available after `complete`** — before that, `GET /summary` returns `409 SUMMARY_NOT_READY`.
- **Safety interruption short-circuits a turn.** If a message mentions e.g. chest pain, the response has `safety.triggered: true`, `stopped: true`, `next_prompt: null`, and `safety.message` holds fixed wording that must be shown to the patient. Nothing was extracted from that message. This must not fall through to the normal completion screen.
- **Every error has the same shape** — `{"error": {"code", "message", "details", "request_id"}}`. Switch on `error.code`, not on the message text. Codes are listed in [api-contract.md](api-contract.md) §4.
- **Sessions live in the database**, so `session_id` survives a backend restart — but there's no auth yet. Anyone with the id can read the session. Fine for the demo; don't put it in a URL you'd share.
- **`value: null` with `action: "edit"`** returns `422`. Use `skip` or `unknown` for "no answer".

## 6. Contract changes

If the API shape doesn't fit the UI, that's a contract problem, not a frontend
problem. Raise it — changes to [api-contract.md](api-contract.md) and the schema
go through C3, and the version bump is tracked so C4 and C6 stay in sync.
