# Symptom history: OLD CARTS integration

The patient preparation workflow now maps applicable symptom information to
onset, location, duration, character, aggravating factors, relieving factors,
timing and severity. This project uses **R = relieving factors**; reported
radiation/spread is recorded separately. This is a history-organising framework,
not a diagnostic protocol or a medical completeness score.

## Patient experience

- The existing one-question wizard and prominent voice composer remain.
- Continuing from a saved symptom description can organise explicit details into
  the remaining fields. Each extracted value must have a verbatim source in that
  concern's saved answer. Direct answers, uncertainty and refusal are protected.
- Prefilled details remain editable. If AI organisation fails, the manual wizard
  remains available and the saved narrative is preserved.
- Worsening and relieving factors are separate questions. Plain-language severity
  choices remain optional. The pain-specific numeric scale is optional too.
- The collapsible symptom story shows recorded, partial, unknown, skipped and
  uncollected information. It does not infer a negative from an absent answer.
- OLD CARTS applies to symptom concerns. Review-only, prescription and result
  discussions are not forced through unrelated symptom questions.
- AI follow-up remains one normal batch of at most five questions, displayed one
  at a time. Eligible gaps are ordered by the patient's concern order and then
  the history dimensions. The model may choose fewer; remaining gaps stay visible.
  The existing second-round exception remains limited to new medicine/allergy
  conflicts. Filling the history does not bypass interruption or consent gates.

## Implementation

`backend/app/product/oldcarts.py` defines the field mappings, applicability,
sanitised coverage projection and target ordering. Workflow-specific location,
character and episode fields are reused. Overall duration and episode duration
are distinct. An onset answer is no longer automatically copied into duration.
Existing ambiguous change-factor answers remain available as legacy context;
they do not silently become a directional worsening or relief fact.

`POST /api/v1/intakes/{id}/baseline/organize` accepts the current `revision` and
`locale`. It requires patient ownership, consent and an active baseline draft;
CSRF, rate limits and optimistic revision checks also apply. It does not start
an interview round. Repeating unchanged successfully organised answers reuses
the extraction fingerprint. External model work occurs outside a database lock.

The patient API exposes `symptom_history`; review saves a sanitised copy inside
`summary.symptom_history`. Approved views use that versioned snapshot. The PDF
includes the history and its gaps, with five-language structural copy. Original
patient evidence remains verbatim. Superseded, excluded and declined values are
not included in the history projection.

## Verification and limitations

Regression cases cover field applicability, onset/duration separation,
episode-specific timing, legacy drafts, uncertainty/refusal, concern isolation,
source grounding, idempotent organisation, revision/CSRF protection, bounded
follow-up, approval snapshots and PDF output. Frontend checks cover status
presentation, exclusive choices and five-language copy. These checks validate
application behaviour with synthetic inputs, not clinical safety or model
accuracy. The independent AI safety/quality evaluation discussed in the project
report remains outstanding.

Run the backend product suite with
`PYTHON_DOTENV_DISABLED=1 backend/.venv/bin/python -m pytest backend/tests/test_product*.py -q`
and frontend checks with `cd frontend && npm test && npm run build`.

Reference: [University of Maryland School of Nursing — History Components](https://cf.son.umaryland.edu/NDNP819/module1/subtopic1.htm).
Its mnemonic combines aggravating/alleviating under A and uses R for radiation;
this implementation explicitly captures both concepts under the variant above.
