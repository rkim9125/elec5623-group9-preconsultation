"""Model token usage, latency and cost.

Every OpenAI response already carries a `usage` block; until now it was read and
discarded. This records it so the project can answer "what does one preparation
actually cost" with measurements instead of estimates.

Token counts and latency are facts taken from the call. **Cost is not**: it
depends on a per-model price that changes and that nothing in the codebase can
know. Rates are supplied through MODEL_PRICES_AUD in Australian dollars (see
`configured_rate`), and a
model with no configured rate reports its tokens with `cost_aud: None` rather
than a made-up number.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from uuid import uuid4

from app.product.database import get_connection, utc_now

# Purposes are recorded per call site so cost can be attributed to a feature,
# not just to a session.
EXTRACTION = "extraction"
ASSESSMENT = "assessment"
TRANSCRIPTION = "transcription"
IMAGE = "image"
INTELLIGENCE = "intelligence"


def init_usage_table() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_usage (
                id TEXT PRIMARY KEY,
                intake_id TEXT,
                purpose TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                happened_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS usage_intake ON model_usage(intake_id);
            """
        )


def _prices() -> dict[str, dict[str, float]]:
    """Per-model AUD price per 1M tokens, e.g.

        MODEL_PRICES_AUD={"gpt-6-sol": {"input": 1.25, "output": 10.0}}

    Left unset deliberately: nothing here should invent a provider's pricing.
    """
    raw = os.getenv("MODEL_PRICES_AUD", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def configured_rate(model: str) -> dict[str, float] | None:
    rate = _prices().get(model)
    if not isinstance(rate, dict):
        return None
    try:
        return {"input": float(rate["input"]), "output": float(rate["output"])}
    except (KeyError, TypeError, ValueError):
        return None


def cost_aud(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """None means "no rate configured for this model", never "free"."""
    rate = configured_rate(model)
    if rate is None:
        return None
    return round(
        (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000, 6
    )


def tokens_from_response(payload: object) -> tuple[int, int]:
    """Pull input/output tokens out of an OpenAI response body.

    Tolerant on purpose — usage accounting must never break a working feature,
    so an unexpected shape records zeros rather than raising.
    """
    if not isinstance(payload, dict):
        return 0, 0
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return 0, 0

    def read(*names: str) -> int:
        for name in names:
            value = usage.get(name)
            if isinstance(value, (int, float)):
                return int(value)
        return 0

    return read("input_tokens", "prompt_tokens"), read("output_tokens", "completion_tokens")


def record(
    *,
    purpose: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    intake_id: str | None = None,
    failed: bool = False,
) -> None:
    """Never raises: a logging failure must not fail the request it describes."""
    try:
        init_usage_table()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO model_usage (id, intake_id, purpose, model, input_tokens,"
                " output_tokens, latency_ms, failed, happened_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid4().hex,
                    intake_id,
                    purpose,
                    model,
                    max(0, int(input_tokens)),
                    max(0, int(output_tokens)),
                    max(0, int(latency_ms)),
                    1 if failed else 0,
                    utc_now(),
                ),
            )
    except Exception:
        pass


@contextmanager
def track(purpose: str, model: str, intake_id: str | None = None):
    """Time a model call and record it, including when the call fails.

    A failed call still consumed time and may have consumed tokens, so it is
    recorded with `failed = 1` rather than dropped — otherwise the cost picture
    only reflects the happy path.

        with track(usage.EXTRACTION, model, intake_id) as entry:
            response = httpx.post(...)
            entry["response"] = response.json()
    """
    started = time.perf_counter()
    entry: dict = {"response": None}
    failed = False
    try:
        yield entry
    except Exception:
        failed = True
        raise
    finally:
        input_tokens, output_tokens = tokens_from_response(entry.get("response"))
        record(
            purpose=purpose,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            intake_id=intake_id,
            failed=failed,
        )


def _summarise(rows: list) -> dict:
    calls = [dict(row) for row in rows]
    by_model: dict[str, dict] = {}
    for call in calls:
        bucket = by_model.setdefault(
            call["model"], {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        )
        bucket["calls"] += 1
        bucket["input_tokens"] += call["input_tokens"]
        bucket["output_tokens"] += call["output_tokens"]

    total_cost = 0.0
    priced = True
    for model, bucket in by_model.items():
        bucket["cost_aud"] = cost_aud(
            model, bucket["input_tokens"], bucket["output_tokens"]
        )
        if bucket["cost_aud"] is None:
            priced = False
        else:
            total_cost += bucket["cost_aud"]

    by_purpose: dict[str, int] = {}
    for call in calls:
        by_purpose[call["purpose"]] = by_purpose.get(call["purpose"], 0) + 1

    return {
        "calls": len(calls),
        "failed_calls": sum(1 for call in calls if call["failed"]),
        "input_tokens": sum(call["input_tokens"] for call in calls),
        "output_tokens": sum(call["output_tokens"] for call in calls),
        "latency_ms_total": sum(call["latency_ms"] for call in calls),
        "by_model": by_model,
        "by_purpose": by_purpose,
        # None when any model involved has no configured rate — a partial total
        # would read as the full cost and understate it.
        "cost_aud": round(total_cost, 6) if priced and by_model else None,
    }


def usage_for_intake(intake_id: str) -> dict:
    init_usage_table()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM model_usage WHERE intake_id = ? ORDER BY happened_at",
            (intake_id,),
        ).fetchall()
    return {"intake_id": intake_id, **_summarise(rows)}


def usage_totals() -> dict:
    init_usage_table()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM model_usage").fetchall()
        intakes = conn.execute(
            "SELECT COUNT(DISTINCT intake_id) AS n FROM model_usage WHERE intake_id IS NOT NULL"
        ).fetchone()["n"]
    summary = _summarise(rows)
    cost = summary["cost_aud"]
    summary["intakes"] = intakes
    summary["cost_aud_per_intake"] = (
        round(cost / intakes, 6) if cost is not None and intakes else None
    )
    return summary
