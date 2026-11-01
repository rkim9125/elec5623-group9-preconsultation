"""Prepare exact requests offline by default; --live explicitly enables billing."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import httpx

from common import ROOT, REPO, append_jsonl, digest, load_cases, write_json
from capture import BudgetExceeded, PreparedRequest, Recorder

sys.path.insert(0, str(REPO / "backend"))
from app.product import config, engine, intelligence, pipeline, provider  # noqa: E402


def extraction_state(case, turn, model):
    state = engine.new_intake({"id": "synthetic-eval", "email": "patient@example.test"},
                              model, [c["workflow_id"] for c in case["concerns"]])
    state["locale"] = "en"
    for actual, specified in zip(state["concerns"], case["concerns"]):
        actual.update(id=specified["id"], title=specified["title"])
    state["current_question"] = None
    for row in turn.get("prior_slots", []):
        slots = state["shared_slots"] if row["owner"] == "session" else next(
            c["slots"] for c in state["concerns"] if c["id"] == row["owner"])
        slots[row["key"]].update(value=row["value"], status=row["status"])
    state["items"] = deepcopy(turn.get("prior_items", []))
    return pipeline._extraction_view(state)


def jobs(case, model):
    for turn in case["turns"]:
        yield {"job_id": f"{case['case_id']}-extract-{turn['id']}", "operation": "extraction",
               "turn_id": turn["id"], "gold_task": f"extraction:{turn['id']}",
               "invoke": lambda turn=turn: provider.OpenAIProvider().extract(
                   extraction_state(case, turn, model), turn["text"], correction=turn.get("correction", False))}
    context = case["generation_input"]
    client = intelligence.OpenAIIntelligence()
    yield {"job_id": f"{case['case_id']}-planning", "operation": "planning", "gold_task": "planning",
           "invoke": lambda: client.plan(model=model, sources=context["sources"], concerns=case["concerns"],
                                         targets=context["targets"], locale="en")}
    yield {"job_id": f"{case['case_id']}-synthesis", "operation": "synthesis", "gold_task": "synthesis",
           "invoke": lambda: client.synthesize(model=model, sources=context["sources"],
                                                concerns=case["concerns"], locale="en")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing runs are never overwritten")
    parser.add_argument("--cases", nargs="+", help="Case IDs; default all six")
    parser.add_argument("--model", help="Default uses product configuration")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-reserved-output-tokens", type=int,
                        help="Sum of requested max_output_tokens, not actual usage or an input-token/cost cap")
    args = parser.parse_args(argv)
    if args.live and (not args.max_calls or args.max_calls < 1 or
                      not args.max_reserved_output_tokens or args.max_reserved_output_tokens < 1):
        parser.error("--live requires positive --max-calls and --max-reserved-output-tokens")
    settings = config.get_settings()
    endpoint = httpx.URL(settings.openai_base_url)
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        parser.error("Base URL must not contain credentials, query parameters or fragments")
    if args.live and not settings.openai_api_key:
        parser.error("Live mode needs the existing OPENAI_API_KEY configuration; do not put the key on the command line")
    cases = load_cases()
    if args.cases:
        unknown = set(args.cases) - {c["case_id"] for c in cases}
        if unknown:
            parser.error(f"Unknown case IDs: {sorted(unknown)}")
        cases = [c for c in cases if c["case_id"] in args.cases]
    model = args.model or settings.openai_model
    if args.output.exists():
        parser.error("Output directory already exists; select a new run directory")
    args.output.mkdir(parents=True, mode=0o700)
    for filename in ("requests.jsonl", "responses.jsonl", "outcomes.jsonl"):
        descriptor = os.open(args.output / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    for name in ("cases", "gold"):
        for case in cases:
            source = ROOT / name / f"{case['case_id']}.json"
            # Snapshot source files separately. Only cases are passed to model-call code.
            target = args.output / name / source.name
            target.parent.mkdir(exist_ok=True, mode=0o700)
            target.write_bytes(source.read_bytes())
            target.chmod(0o600)
    files = [*sorted((REPO / "backend/app").rglob("*.py")), *sorted(ROOT.glob("*.py")),
             *sorted((ROOT / "cases").glob("*.json")), *sorted((ROOT / "gold").glob("*.json"))]
    manifest = {"mode": "live" if args.live else "prepare", "created_at": datetime.now(timezone.utc).isoformat(),
                "model": model, "base_url": settings.openai_base_url, "locale": "en",
                "prompt_cache_switch": os.getenv("OPENAI_PROMPT_CACHE", "1"),
                "evaluation_mode": "controlled_stage_inputs_not_end_to_end",
                "context_policy": "Authored patient/form snapshots; later jobs do not consume earlier model results",
                "case_ids": [c["case_id"] for c in cases],
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                "source_sha256": {str(p.relative_to(REPO)): digest(p.read_bytes()) for p in files},
                "max_calls": args.max_calls, "max_reserved_output_tokens": args.max_reserved_output_tokens,
                "status": "running", "jobs": [],
                "planned_jobs": [{"case_id": c["case_id"], **{k: v for k, v in j.items() if k != "invoke"}}
                                 for c in cases for j in jobs(c, model)]}
    write_json(args.output / "manifest.json", manifest)
    recorder = Recorder(args.output, base_url=settings.openai_base_url, live=args.live,
                        max_calls=args.max_calls or 0, max_reserved_output_tokens=args.max_reserved_output_tokens or 0)
    offline_key = patch.dict(os.environ, {"OPENAI_API_KEY": "offline-not-a-real-key"}) if not args.live else nullcontext()
    stopped = False
    with offline_key, recorder.installed():
        for case in cases:
            for job in jobs(case, model):
                metadata = {"case_id": case["case_id"], **{k: v for k, v in job.items() if k != "invoke"}}
                manifest["jobs"].append(metadata)
                with recorder.job(**metadata):
                    try:
                        result = job["invoke"]()
                        outcome = {"status": "returned", "validated_result": result}
                    except PreparedRequest:
                        outcome = {"status": "prepared", "model_response_received": False}
                    except BudgetExceeded:
                        outcome = {"status": "budget_exhausted"}
                        stopped = True
                    except Exception as exc:
                        # Full provider body is in responses; don't serialize exception strings or keys.
                        outcome = {"status": "operation_failed", "error_type": type(exc).__name__}
                    append_jsonl(args.output / "outcomes.jsonl", {**metadata, **outcome})
                    print(f"{job['job_id']}: {outcome['status']}", flush=True)
                write_json(args.output / "manifest.json", manifest)
                if stopped:
                    break
            if stopped:
                break
    manifest.update(status="budget_exhausted" if stopped else "finished", captured_requests=recorder.calls,
                    reserved_output_tokens=recorder.reserved_output_tokens)
    write_json(args.output / "manifest.json", manifest)
    print(f"Saved {recorder.calls} {'live' if args.live else 'offline prepared'} requests to {args.output}")
    return 2 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
