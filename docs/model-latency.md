# Model configuration and measured extraction latency

Evidence date: **28 October 2026, Australia/Sydney**. This note describes the
current application policy and the recorded experiment; no additional API calls
were made to prepare it.

## Current policy

New preparations default to **`gpt-6-sol`**. The administrator can override the
default with `OPENAI_MODEL`; patients can choose an available model in advanced
options. Existing records retain their selected model. A provider error does not
silently substitute another model.

| Operation | GPT-6 Sol reasoning effort |
| --- | --- |
| Structured fact extraction | `low` |
| Follow-up planning and wording | `low` |
| Final preparation synthesis | `medium` |
| Preliminary assessment | `medium` |

Other selected or custom models retain their provider-default reasoning settings.
The timing results below concern extraction only; they do not measure the
medium-effort synthesis or assessment operations. Reasoning settings do not grant
the model system-action or patient-retrieval permissions.

## Recorded measurements

The [live-model evidence](../../presentation-final-2026-10-28/evidence/live-model.json)
contains **eight real provider calls with synthetic data**: six ordinary
extractions across three paired inputs, followed by two injection examples.
Every recorded call completed in live mode. The evaluator used an in-memory
intake; no patient database or action tools were connected.

| Synthetic input | Sol, `low` (seconds) | Astra, provider default (seconds) |
| --- | ---: | ---: |
| Leg pain, English | 7.677 | 9.332 |
| Headache, English | 6.926 | 13.053 |
| Leg pain, Simplified Chinese | 8.084 | 17.618 |
| Median, **n = 3 per configuration** | **7.677** | **13.053** |

Each time is elapsed local `process_message` time around one live extraction,
including the network round trip and local processing. It is not time to first
token or full consultation completion time. Sol was faster for these three
paired inputs under the tested settings.

The separate English and Simplified Chinese injection calls took 5.109 and 4.150
seconds. Their accepted fields contained only the reported knee symptom, and the
in-memory patient owner stayed unchanged. They are excluded from the ordinary
latency medians. This observation does **not** establish that a real database was
protected by the model or that prompt injection can never succeed. The
[application security results](../../presentation-final-2026-10-28/evidence/security-results.json)
provide separate, deterministic server-authorization evidence.

## Interpretation limits

- This compares **configured extraction experiences**, not model-only speed:
  Sol uses explicit `low` reasoning; Astra uses its existing provider default.
- Each narrative was requested once per model, always **Sol then Astra**, in one
  sequential run. Order was not randomized; cache, network and provider-load
  effects were not controlled.
- Three samples per configuration cannot establish a reliable tail-latency or
  service-level claim. There was no concurrency/load test or end-to-end timing.
- The sample covers three synthetic narratives in two languages, not all thirty
  pathways or all five supported patient languages.
- Faster extraction does not imply equal output quality. No clinician-rated
  accuracy, safety, usability or effectiveness comparison was performed.
- Two live injection examples are a smoke check, not a general jailbreak test or
  independent penetration test. Output provenance checks are not proof of
  medical or semantic correctness.

## Reproduce deliberately

From the repository root, using the backend virtual environment and configured
server credentials:

```sh
backend/.venv/bin/python scripts/evaluate-live-models.py --output ../presentation-final-2026-10-28/evidence/live-model-rerun.json
```

This is an explicitly invoked **paid live run**, capped at eight extraction
requests. It writes to a new filename so the recorded presentation evidence is
preserved. It uses synthetic in-memory records, prints only safe status/timing
information and does not export credentials. Failed calls are recorded and are
excluded from successful-sample medians; a failed rerun is not equivalent to the
eight successful calls documented above.
