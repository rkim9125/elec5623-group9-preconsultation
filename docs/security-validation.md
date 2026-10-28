# Security validation for the final demonstration

Evaluation date: **28 October 2026, Australia/Sydney**.

PreConsult separates the model's text-processing role from application authority.
A request such as “delete the system” or “retrieve another patient's records” is
untrusted input. No model request supplies a shell, database-search tool, general
HTTP tool, or application-action dispatcher. The authenticated server, not the
model, decides which record can be read, changed, shared, or deleted.

This document records the boundaries tested and the limits of that evidence. It
does not claim that every prompt injection will be detected or that the system
has passed an independent penetration test or clinical safety evaluation.

## Implemented boundaries

| Boundary | Enforcement |
| --- | --- |
| Patient ownership | Every intake read/write first compares the authenticated patient ID with the stored owner. Guessing another ID returns 404. Body fields cannot change the authenticated identity. |
| Doctor access | The current record must be approved, have an approved summary version, and name the signed-in doctor's email. Being registered as a doctor does not grant access to all patients. |
| Revocation | Withdrawing sharing removes the doctor's access to the record, attachments, PDF, and assessment. A report operation rechecks authorization/current input before committing or downloading a result. |
| Browser request origin | State-changing routes require a configured Origin or same-origin Referer. Session cookies are HTTP-only; production uses a secure, host-only cookie. |
| Model capabilities | Responses requests contain source data and an output schema, use `store: false`, and provide no action tools or previous shared conversation. A returned `function_call` is not dispatched. |
| Extraction integrity | Proposed facts need an allowed owner and field, exact source evidence, and a permitted state transition. Forged patient IDs, share recipients, status fields, and other-concern IDs are rejected. |
| Report integrity | Source IDs must belong to the current projected record. Unknown, declined, superseded, and excluded details are not promoted to confirmed evidence. |
| Files and rendering | Uploaded media must match supported content types; filenames are reduced to a basename and stored under a generated ID. Private downloads use `no-store`, `nosniff`, and a sandbox policy. React and PDF text rendering do not execute supplied HTML. |
| Credentials | Server credentials are not part of model input, public configuration, or patient responses. Provider error bodies are not sent to the browser. |

## Additional hardening in this revision

`backend/app/product/output_safety.py` adds a shared check for obvious model-authored
system commands, cross-patient data-retrieval instructions, and secret-token echo.
It covers English, Simplified Chinese, Traditional Chinese, Japanese, and Korean,
including selected Unicode-obfuscation examples. Synthesis, assessment, and
attachment-draft paths reject this output instead of presenting it as an answer.

The check applies to generated prose, not the patient's original narrative. A
patient may describe a suspicious message, express privacy concerns, correct an
old medicine entry, or ask to remove their own draft. Denials and clearly reported
worries remain supported. This is a bounded text check, not the access-control
boundary and not a semantic proof that generated text is correct.

## Executed application regression

The reproducible security suite passed **266 of 266 tests**, with **0 failures and
0 skips**. It includes **67 newly added adversarial/boundary cases** and existing
authentication, ownership, media, assessment, and provider-contract regressions.
The run emitted one existing dependency deprecation warning.

All identities and clinical records were synthetic. Tests used temporary SQLite
databases, real FastAPI routes, real cookie/session lookup, and real file handling.
Remote AI and email responses were mocked. No production patient database was
read or attacked, and this suite made no paid model calls.

| Scenario | Test evidence | Result |
| --- | --- | --- |
| Patient A guesses Patient B's intake ID | 20 route/method variants, including read, update, delete, organize, review, share, attachments, PDF, and assessment; compare B's record before/after | All returned 404; no canary text leaked; B's stored record unchanged |
| Doctor reads an unassigned record | Record, attachment, PDF, and assessment before approval and when assigned to another doctor | 404 |
| Patient revokes an approved share | The same four surfaces immediately after withdrawal | 404; clinician list no longer contains the record |
| Client forges identity or role | Forged body owner/role fields, guessed cookie, patient-to-doctor endpoint, doctor-to-patient delete | Owner remains the authenticated patient; forged cookie 401; role mismatch 403 |
| Cross-site change request | Foreign, null, and lookalike Origins for delete and share | 403; record unchanged |
| Upload contains executable markup | HTML declared as PNG, unsupported HTML upload, path-like filename on valid PNG | 422/415 for invalid content; valid filename sanitized and stored within owned intake |
| Model attempts action dispatch | Mock `function_call` output on extraction, synthesis, and assessment | Unusable output rejected; no dispatcher exists |
| Model attempts to change authority | Forged patient ID, doctor email, status, other-concern ID, and shell-command field | All five proposed facts rejected |
| Model echoes operational instructions | 16 command/secret samples across five languages, plus two attachment-response cases | Rejected by the generated-output boundary |
| Benign edits or refusals | 13 examples including outdated medication removal, privacy worries, quoted suspicious instructions, and explicit denials | Accepted by the new check |
| Patient supplies hostile text | Save the original sentence to the patient's own narrative using the real baseline API | Preserved as data; owner unchanged; other patient's record unchanged |

Run from the repository root:

```sh
backend/.venv/bin/python scripts/validate-security.py
```

The runner writes `security-results.json`, `security-junit.xml`, and
`security-tests.log` into `.local/security-validation/`. Each JSON result names its
pytest case and execution duration. The final presentation evidence folder also
contains `security-cases.json`, a detailed catalog of 20 representative attacks
and expected boundaries.

## Separate live-model smoke evidence

A separate, bounded experiment made eight live extraction requests with synthetic
narratives: three paired cases on GPT-6 Sol and GPT-6 Astra, plus two injection
examples on Sol (English and Simplified Chinese). In those two injection examples,
the accepted extraction retained the reported knee symptom and did not change the
patient owner. The experiment used an in-memory engine with no database or tool
execution connected. It therefore tests those extraction examples, not resistance
to a real database intrusion. The input, accepted fields, timing, and limitations
are recorded in `live-model.json` in the presentation evidence folder.

The six ordinary narrative calls measured the configured experiences: Sol with
low reasoning had a median of **7.677 seconds**, compared with **13.053 seconds**
for Astra using its existing provider-default reasoning. Each median has only
three samples. This is neither a model-only comparison nor a load test, latency
guarantee, clinical quality benchmark, or general jailbreak success-rate estimate.

## Remaining work before clinical deployment

- Independently review clinical accuracy, unsafe reassurance, omissions, medication
  statements, and advice across the five supported languages with qualified reviewers.
- Expand live-model adversarial testing to indirect document attacks, multilingual
  paraphrases, and long or conflicting inputs, with a prespecified scoring rubric.
- Review production hosting, HTTPS, key rotation, database protection, backup and
  retention, monitoring, dependency security, and denial-of-service limits.
- Doctor registration currently proves email ownership and fixes one account role;
  it does **not** verify professional licensure or clinical identity. Explicit
  patient sharing is still required.
- Bounded phrase checks can miss paraphrases and reject some benign text. Passing
  this set cannot establish that a probabilistic model is “unbreakable.”

## Presentation wording

Use: “Our 266 deterministic application security tests passed, including 67 new
boundary cases. Two separate live extraction injection examples also retained only
the reported symptom. The model has no system-action tools, while the backend
enforces patient ownership and explicit doctor sharing.”

Do not use: “The AI is completely secure,” “all jailbreaks are blocked,” or
“the system is clinically validated.”
