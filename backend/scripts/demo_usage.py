"""Show model usage accounting end to end, without needing to sign in.

    cd backend
    ./.venv/bin/python scripts/demo_usage.py            # offline, fake numbers
    ./.venv/bin/python scripts/demo_usage.py --live     # one real OpenAI call

Writes to a throwaway database, so it never touches your real data.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TMP = Path(tempfile.mkdtemp(prefix="usage-demo-"))
os.environ["PRODUCT_DB_PATH"] = str(TMP / "demo.sqlite3")
os.environ["UPLOAD_DIR"] = str(TMP / "uploads")
# Example rates only. Replace with the provider's real pricing before quoting
# any figure in the report.
os.environ.setdefault(
    "MODEL_PRICES_USD",
    json.dumps({"gpt-4o-mini": {"input": 0.15, "output": 0.60},
                "gpt-6-sol": {"input": 1.25, "output": 10.00}}),
)

from app.product import usage                      # noqa: E402
from app.product.database import init_db           # noqa: E402


def show(title: str, data: dict) -> None:
    print(f"\n--- {title} ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def offline() -> None:
    print("Simulating one preparation: 3 extraction calls + 1 AI report.")
    for tokens_in, tokens_out, ms in [(820, 110, 900), (1240, 180, 1100), (1500, 240, 1300)]:
        usage.record(purpose=usage.EXTRACTION, model="gpt-6-sol", input_tokens=tokens_in,
                     output_tokens=tokens_out, latency_ms=ms, intake_id="demo-intake")
    usage.record(purpose=usage.ASSESSMENT, model="gpt-6-sol", input_tokens=9400,
                 output_tokens=2600, latency_ms=18000, intake_id="demo-intake")
    # A timeout still cost time, so it is recorded rather than dropped.
    usage.record(purpose=usage.EXTRACTION, model="gpt-6-sol", latency_ms=90000,
                 intake_id="demo-intake", failed=True)

    show("GET /api/v1/intakes/demo-intake/usage", usage.usage_for_intake("demo-intake"))
    show("GET /api/v1/usage", usage.usage_totals())

    print("\nNow the same data with no configured rate:")
    os.environ["MODEL_PRICES_USD"] = ""
    print(f"  cost_usd = {usage.usage_for_intake('demo-intake')['cost_usd']}"
          "   <- 'no rate configured', not 'free'")


def live() -> None:
    import time
    import httpx
    from app.product.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        sys.exit("OPENAI_API_KEY is not set in backend/.env")

    model = "gpt-4o-mini"
    print(f"Calling OpenAI for real ({model})...")
    started = time.perf_counter()
    response = httpx.post(
        settings.openai_base_url.rstrip("/") + "/responses",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": model, "input": "Reply with the single word: ok",
              "max_output_tokens": 16},
        timeout=30,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        sys.exit(f"OpenAI returned {response.status_code}: {response.text[:200]}")

    body = response.json()
    tokens_in, tokens_out = usage.tokens_from_response(body)
    print(f"  provider's usage block : {json.dumps(body.get('usage'))}")
    print(f"  parsed by our code     : input={tokens_in} output={tokens_out}")

    usage.record(purpose=usage.EXTRACTION, model=model, input_tokens=tokens_in,
                 output_tokens=tokens_out, latency_ms=elapsed_ms, intake_id="live-demo")
    show("GET /api/v1/intakes/live-demo/usage", usage.usage_for_intake("live-demo"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="make one real OpenAI call")
    args = parser.parse_args()

    init_db()
    usage.init_usage_table()
    live() if args.live else offline()
    print(f"\n(throwaway database: {TMP})")
