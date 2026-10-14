# Model usage and cost

Answers "what does one preparation actually cost" with measurements rather than
estimates. Added in response to the tutor's **"report → costing?"** feedback, and
it also covers the token/latency recording listed under C4 in
[component-breakdown.md](component-breakdown.md).

## What is recorded

Every OpenAI call already returned a `usage` block; it was being discarded. Each
call now writes one row to `model_usage`:

| Column | Meaning |
|---|---|
| `intake_id` | Which preparation the call belongs to (null for calls outside one) |
| `purpose` | `extraction`, `assessment`, `transcription`, `image`, `intelligence` |
| `model` | The model actually used |
| `input_tokens` / `output_tokens` | From the provider's own `usage` block |
| `cached_input_tokens` | The cached portion of `input_tokens`, billed at a lower rate |
| `latency_ms` | Measured wall-clock time for the call |
| `failed` | Timeouts and rejected calls are recorded, not dropped |

Instrumented call sites: extraction, AI assessment (including each
per-attachment read), planning, factual synthesis, audio transcription and
attachment analysis.

A record is written **once per attempt, after the outcome is known**. HTTP 200
is not success — an incomplete, refused or unparseable body still consumed
tokens and still failed the caller, so it is recorded with `failed = 1` and its
token counts retained. Timeouts and rejected calls are recorded too; excluding
them would make the cost picture look better than reality.

## Cost is configured, never guessed

Token counts are facts. **Prices are not** — they depend on the provider's rate
card, which changes and which nothing in this codebase can know. Rates come from
`MODEL_PRICES_AUD`, in AUD per 1,000,000 tokens:

```bash
MODEL_PRICES_AUD={"gpt-6-sol": {"input": 1.25, "output": 10.00, "cached_input": 0.13}}
```

`cached_input` is optional. If a call used cached input and no cached rate is
configured, the cost is `null` rather than charging cache hits at the full input
rate — silently overcharging is worse than admitting the rate is unknown.

A model with no configured rate reports its token counts with `cost_aud: null`.
That is "no rate configured", not "free". If *any* model in a total is unpriced,
the total is `null` too — a partial sum would read as the full cost and quietly
understate it.

Copy the real numbers from the provider's pricing page before quoting any figure
in the report — and **convert them**: OpenAI publishes prices in USD, while this
field is in AUD. Pasting the USD list price straight in understates the cost by
roughly the exchange rate.

## Reading it

```
GET /api/v1/intakes/{intake_id}/usage   # patient, own preparation only
GET /api/v1/usage                       # clinician — totals and per-intake average
```

```json
{
  "calls": 7,
  "failed_calls": 1,
  "input_tokens": 18420,
  "output_tokens": 3110,
  "latency_ms_total": 21840,
  "by_purpose": { "extraction": 5, "assessment": 2 },
  "by_model": { "gpt-6-sol": { "calls": 7, "input_tokens": 18420, "output_tokens": 3110, "cost_aud": 0.054 } },
  "cost_aud": 0.054
}
```

`/api/v1/usage` adds `intakes` and `cost_aud_per_intake` — the number to quote
when asked what a preparation costs.

The totals endpoint is clinician-only: it describes spend across other people's
preparations, so it isn't something an individual patient should be able to read.

## Trying it without signing in

The endpoints need a session, and email sign-in currently only delivers to the
Resend account owner — so until that's fixed, use these instead:

```bash
cd backend
./.venv/bin/pytest tests/test_product_usage.py -v   # 16 tests
./.venv/bin/python scripts/demo_usage.py           # simulated preparation
./.venv/bin/python scripts/demo_usage.py --live    # one real OpenAI call
```

The demo writes to a throwaway database, so it never touches real data.

## Verified

Checked against a live OpenAI response, not just fixtures:

```
usage block : {"input_tokens": 9, ..., "output_tokens": 3, "total_tokens": 12}
parsed      : (9, 3)
no rate     : None
with rate   : 3e-06 AUD
```

`tests/test_product_usage.py` covers the parser (including malformed responses),
the null-cost rules, aggregation, failed-call recording, and that a logging
failure can never break the request it describes.
