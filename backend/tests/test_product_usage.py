"""Token, latency and cost accounting for model calls.

The tutor asked what a preparation costs. Tokens and latency are measured from
the calls themselves; price is not something this codebase can know, so these
tests pin that an unpriced model reports its tokens with a null cost rather than
a fabricated figure.
"""

import json

import pytest

from app.product import usage


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.delenv("MODEL_PRICES_AUD", raising=False)
    from app.product.database import init_db

    init_db()
    usage.init_usage_table()


def test_tokens_are_read_from_an_openai_response():
    body = {"usage": {"input_tokens": 1200, "output_tokens": 340}}
    assert usage.tokens_from_response(body) == (1200, 340)


def test_chat_completions_style_usage_is_also_understood():
    body = {"usage": {"prompt_tokens": 50, "completion_tokens": 7}}
    assert usage.tokens_from_response(body) == (50, 7)


@pytest.mark.parametrize("body", [None, {}, {"usage": None}, {"usage": {}}, "nonsense"])
def test_unexpected_shapes_record_zero_rather_than_raising(body):
    # Usage accounting must never be the reason a working feature fails.
    assert usage.tokens_from_response(body) == (0, 0)


def test_cost_is_null_when_no_rate_is_configured():
    assert usage.cost_aud("gpt-6-sol", 1_000_000, 1_000_000) is None


def test_cost_uses_the_configured_rate(monkeypatch):
    monkeypatch.setenv(
        "MODEL_PRICES_AUD", json.dumps({"gpt-6-sol": {"input": 1.25, "output": 10.0}})
    )
    # 1M input at $1.25 + 0.5M output at $10.00
    assert usage.cost_aud("gpt-6-sol", 1_000_000, 500_000) == 6.25


def test_malformed_price_config_is_ignored_rather_than_trusted(monkeypatch):
    monkeypatch.setenv("MODEL_PRICES_AUD", "{not json")
    assert usage.cost_aud("gpt-6-sol", 100, 100) is None
    monkeypatch.setenv("MODEL_PRICES_AUD", json.dumps({"gpt-6-sol": {"input": "free"}}))
    assert usage.cost_aud("gpt-6-sol", 100, 100) is None


def test_usage_for_one_intake_aggregates_its_calls():
    usage.record(purpose=usage.EXTRACTION, model="m1", input_tokens=100,
                 output_tokens=20, latency_ms=300, intake_id="intake-a")
    usage.record(purpose=usage.ASSESSMENT, model="m1", input_tokens=900,
                 output_tokens=400, latency_ms=2000, intake_id="intake-a")
    usage.record(purpose=usage.EXTRACTION, model="m1", input_tokens=5,
                 output_tokens=5, latency_ms=10, intake_id="intake-b")

    summary = usage.usage_for_intake("intake-a")
    assert summary["calls"] == 2
    assert summary["input_tokens"] == 1000
    assert summary["output_tokens"] == 420
    assert summary["latency_ms_total"] == 2300
    assert summary["by_purpose"] == {usage.EXTRACTION: 1, usage.ASSESSMENT: 1}
    assert summary["cost_aud"] is None  # no rate configured


def test_failed_calls_are_recorded_not_dropped():
    # A timeout still consumed time and sometimes tokens; excluding it would
    # make the cost picture look better than reality.
    usage.record(purpose=usage.EXTRACTION, model="m1", latency_ms=90_000,
                 intake_id="intake-c", failed=True)
    summary = usage.usage_for_intake("intake-c")
    assert summary["calls"] == 1
    assert summary["failed_calls"] == 1
    assert summary["latency_ms_total"] == 90_000


def test_totals_report_average_cost_per_intake(monkeypatch):
    monkeypatch.setenv(
        "MODEL_PRICES_AUD", json.dumps({"m1": {"input": 1.0, "output": 1.0}})
    )
    for intake in ("i1", "i2"):
        usage.record(purpose=usage.ASSESSMENT, model="m1", input_tokens=500_000,
                     output_tokens=500_000, latency_ms=100, intake_id=intake)

    totals = usage.usage_totals()
    assert totals["intakes"] == 2
    assert totals["cost_aud"] == 2.0
    assert totals["cost_aud_per_intake"] == 1.0


def test_a_single_unpriced_model_makes_the_total_null(monkeypatch):
    # A partial sum would read as the full cost and quietly understate it.
    monkeypatch.setenv("MODEL_PRICES_AUD", json.dumps({"priced": {"input": 1.0, "output": 1.0}}))
    usage.record(purpose=usage.EXTRACTION, model="priced", input_tokens=10, output_tokens=10)
    usage.record(purpose=usage.ASSESSMENT, model="unpriced", input_tokens=10, output_tokens=10)
    assert usage.usage_totals()["cost_aud"] is None


def test_track_times_the_call_and_keeps_the_exception():
    with pytest.raises(RuntimeError):
        with usage.track(usage.EXTRACTION, "m1", "intake-d"):
            raise RuntimeError("provider exploded")
    summary = usage.usage_for_intake("intake-d")
    assert summary["calls"] == 1 and summary["failed_calls"] == 1


def test_recording_never_raises_even_if_the_table_is_unusable(monkeypatch):
    monkeypatch.setattr(usage, "init_usage_table", lambda: (_ for _ in ()).throw(OSError("disk")))
    usage.record(purpose=usage.EXTRACTION, model="m1")  # must not raise


# --- regressions from the PR 26 review ---------------------------------
# The review found four defects that the original tests could not catch,
# because they only exercised the accounting helpers in isolation. These
# drive the provider code paths instead.


def _ok_response(input_tokens=100, output_tokens=20, cached=0, status="completed", text='{"a": 1}'):
    body = {
        "status": status,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_tokens_details": {"cached_tokens": cached},
        },
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
    }
    return body


class _FakeResponse:
    def __init__(self, body, status_code=200, raises=False):
        self._body = body
        self.status_code = status_code
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._body


def _extract(monkeypatch, response):
    """Run the real extraction provider against a canned HTTP response."""
    from app.product import provider

    monkeypatch.setattr(provider.httpx, "post", lambda *a, **k: response)
    monkeypatch.setattr(
        provider, "get_settings",
        lambda: type("S", (), {"openai_api_key": "k", "openai_base_url": "https://x"})(),
    )
    session = {"id": "intake-x", "model": "m1", "concerns": [], "shared_slots": {}}
    try:
        provider.OpenAIProvider().extract(session, "hello")
    except Exception:
        pass


def test_finding3_incomplete_output_is_recorded_as_a_failure(monkeypatch):
    # HTTP 200 with status != completed is not a success, but its tokens were spent.
    _extract(monkeypatch, _FakeResponse(_ok_response(status="incomplete")))
    summary = usage.usage_for_intake("intake-x")
    assert summary["calls"] == 1
    assert summary["failed_calls"] == 1
    assert summary["input_tokens"] == 100  # tokens retained, not discarded


def test_finding3_unparseable_body_still_produces_a_record(monkeypatch):
    # Previously this raised before the record was written, so the call vanished.
    _extract(monkeypatch, _FakeResponse(None, raises=True))
    summary = usage.usage_for_intake("intake-x")
    assert summary["calls"] == 1 and summary["failed_calls"] == 1


def test_finding3_usable_output_is_recorded_as_success(monkeypatch):
    _extract(monkeypatch, _FakeResponse(_ok_response(
        text='{"new_concerns": [], "facts": [], "signals": [], "items": [], "priority_order": []}')))
    summary = usage.usage_for_intake("intake-x")
    assert summary["calls"] == 1 and summary["failed_calls"] == 0


def test_finding4_cached_input_is_priced_at_the_cached_rate(monkeypatch):
    # The review's figures: 10k input of which 9k cached, 100 output.
    monkeypatch.setenv("MODEL_PRICES_AUD", json.dumps(
        {"m1": {"input": 1.0, "output": 1.0, "cached_input": 0.10}}))
    assert usage.cost_aud("m1", 10_000, 100, 9_000) == 0.002


def test_finding4_cached_tokens_without_a_cached_rate_are_not_charged_as_fresh(monkeypatch):
    monkeypatch.setenv("MODEL_PRICES_AUD", json.dumps({"m1": {"input": 1.0, "output": 1.0}}))
    # Overcharging silently is worse than admitting the rate is unknown.
    assert usage.cost_aud("m1", 10_000, 100, 9_000) is None
    # A call with no cache hits is unaffected.
    assert usage.cost_aud("m1", 10_000, 100, 0) == 0.0101


def test_finding4_cached_breakdown_survives_into_the_summary():
    usage.record(purpose=usage.EXTRACTION, model="m1", input_tokens=10_000,
                 output_tokens=100, cached_input_tokens=9_000, intake_id="intake-cache")
    summary = usage.usage_for_intake("intake-cache")
    assert summary["cached_input_tokens"] == 9_000
    assert summary["by_model"]["m1"]["cached_input_tokens"] == 9_000


def test_finding4_a_nonsense_cached_count_cannot_exceed_the_input_total():
    assert usage.token_breakdown(
        {"usage": {"input_tokens": 100, "output_tokens": 1,
                   "input_tokens_details": {"cached_tokens": 999}}}
    )["cached_input_tokens"] == 100


def test_finding1_every_purpose_constant_is_actually_used():
    # The constants were documented as covered while nothing emitted them.
    import pathlib

    source = " ".join(
        path.read_text()
        for path in pathlib.Path("app/product").glob("*.py")
        if path.name != "usage.py"
    )
    for constant in (usage.EXTRACTION, usage.ASSESSMENT, usage.INTELLIGENCE,
                     usage.TRANSCRIPTION, usage.IMAGE):
        name = constant.upper()
        assert f"usage.{name}" in source, f"{constant} is documented but never recorded"
