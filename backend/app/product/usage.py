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
                cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                happened_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS usage_intake ON model_usage(intake_id);
            """
        )
        # Databases created before cached-input accounting need the column too.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(model_usage)")}
        if "cached_input_tokens" not in columns:
            conn.execute(
                "ALTER TABLE model_usage ADD COLUMN cached_input_tokens INTEGER NOT NULL DEFAULT 0"
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
    """`cached_input` is optional; without it, cached tokens are not priced."""
    rate = _prices().get(model)
    if not isinstance(rate, dict):
        return None
    try:
        resolved = {"input": float(rate["input"]), "output": float(rate["output"])}
    except (KeyError, TypeError, ValueError):
        return None
    if "cached_input" in rate:
        try:
            resolved["cached_input"] = float(rate["cached_input"])
        except (TypeError, ValueError):
            return None
    return resolved


def cost_aud(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> float | None:
    """None means "cannot price this", never "free".

    Cached input is billed at its own rate. If a call used cached input but the
    model has no `cached_input` rate configured, this returns None rather than
    charging cache hits at the full input rate — silently overcharging is worse
    than admitting the rate is unknown.
    """
    rate = configured_rate(model)
    if rate is None:
        return None
    cached = min(max(0, cached_input_tokens), input_tokens)
    if cached and "cached_input" not in rate:
        return None
    fresh = input_tokens - cached
    total = fresh * rate["input"] + cached * rate.get("cached_input", 0.0)
    total += output_tokens * rate["output"]
    return round(total / 1_000_000, 6)


def tokens_from_response(payload: object) -> tuple[int, int]:
    """Total input and output tokens. Kept for callers that don't need detail."""
    breakdown = token_breakdown(payload)
    return breakdown["input_tokens"], breakdown["output_tokens"]


def token_breakdown(payload: object) -> dict[str, int]:
    """Input/output tokens plus the cached-input split.

    Cached input is billed at a lower rate than fresh input, so collapsing them
    into one number makes a cached request look more expensive than it was —
    and the detail can't be recovered afterwards. `input_tokens` stays the
    provider's total; `cached_input_tokens` is the part of it that was cached.

    Tolerant on purpose — usage accounting must never break a working feature,
    so an unexpected shape yields zeros rather than raising.
    """
    empty = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
    if not isinstance(payload, dict):
        return empty
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return empty

    def read(source: dict, *names: str) -> int:
        for name in names:
            value = source.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(0, int(value))
        return 0

    details = usage.get("input_tokens_details")
    details = details if isinstance(details, dict) else {}
    total_input = read(usage, "input_tokens", "prompt_tokens")
    cached = read(details, "cached_tokens")
    if not cached:
        # chat/completions reports it as prompt_tokens_details.cached_tokens
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, dict):
            cached = read(prompt_details, "cached_tokens")
    return {
        "input_tokens": total_input,
        "output_tokens": read(usage, "output_tokens", "completion_tokens"),
        # Never let a malformed cached count exceed the total it is part of.
        "cached_input_tokens": min(cached, total_input),
    }


def record(
    *,
    purpose: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
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
                " output_tokens, cached_input_tokens, latency_ms, failed, happened_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid4().hex,
                    intake_id,
                    purpose,
                    model,
                    max(0, int(input_tokens)),
                    max(0, int(output_tokens)),
                    min(max(0, int(cached_input_tokens)), max(0, int(input_tokens))),
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
        breakdown = token_breakdown(entry.get("response"))
        record(
            purpose=purpose,
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            intake_id=intake_id,
            # A call that returned HTTP 200 but no usable output still failed,
            # and its tokens were still spent — keep both facts.
            failed=failed or bool(entry.get("failed")),
            **breakdown,
        )


def _summarise(rows: list) -> dict:
    calls = [dict(row) for row in rows]
    by_model: dict[str, dict] = {}
    for call in calls:
        bucket = by_model.setdefault(
            call["model"],
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0},
        )
        bucket["calls"] += 1
        bucket["input_tokens"] += call["input_tokens"]
        bucket["output_tokens"] += call["output_tokens"]
        bucket["cached_input_tokens"] += call["cached_input_tokens"]

    total_cost = 0.0
    priced = True
    for model, bucket in by_model.items():
        bucket["cost_aud"] = cost_aud(
            model,
            bucket["input_tokens"],
            bucket["output_tokens"],
            bucket["cached_input_tokens"],
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
        "cached_input_tokens": sum(call["cached_input_tokens"] for call in calls),
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
