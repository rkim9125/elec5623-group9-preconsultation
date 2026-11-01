"""Check the synthetic corpus and gold mappings without making model calls."""
from __future__ import annotations

import json
import sys
from common import ROOT, REPO, load_cases, read_json

sys.path.insert(0, str(REPO / "backend"))
from app.product.workflows import question_definitions, SHARED_QUESTIONS


def validate():
    cases = {c["case_id"]: c for c in load_cases()}
    if set(cases) != {"N01", "N02", "N03", "N04", "I01", "I02"}:
        raise ValueError("Expected exactly the six specified cases")
    fact_count, job_count = 0, 0
    for cid, case in cases.items():
        gold = read_json(ROOT / "gold" / f"{cid}.json")
        assert gold["case_id"] == cid and case["locale"] == "en" and case["synthetic_only"] is True
        assert len({c["id"] for c in case["concerns"]}) == len(case["concerns"])
        fields = {c["id"]: {q["key"] for q in question_definitions(c["workflow_id"])} for c in case["concerns"]}
        fields["session"] = set(SHARED_QUESTIONS)
        for turn in case["turns"]:
            facts = gold["tasks"]["extraction:" + turn["id"]]["facts"]
            assert len({f["id"] for f in facts}) == len(facts)
            for fact in facts:
                if fact["owner"].startswith("medication:"):
                    assert all(k.startswith("medication.") or k == "remove_item" for k in fact["keys"])
                else:
                    assert all(k in fields[fact["owner"]] for k in fact["keys"]), (cid, fact)
                assert fact["certainty"] in {"stated", "unknown", "declined"}
                assert fact["operation"] in {"set", "remove"}
                if fact["operation"] == "set":
                    assert any(v and v in turn["text"] for v in fact["accepted_values"]), (cid, fact)
                evidence = fact["source_evidence"]
                assert turn["text"][evidence["start"]:evidence["end"]] == evidence["quote"]
            fact_count += len(facts)
        context = case["generation_input"]
        assert len({s["id"] for s in context["sources"]}) == len(context["sources"])
        for t in context["targets"]:
            assert t["key"] in fields[t["concern_id"]]
        assert {t["target_id"] for t in context["targets"]} == set(gold["tasks"]["planning"]["allowed_target_ids"])
        assert set(case["followup_responses"]) == set(gold["tasks"]["planning"]["allowed_target_ids"])
        if case.get("attack"):
            clean = cases[case["paired_normal"]]
            attack = case["attack"]["text"]
            assert case["turns"][0]["text"] == clean["turns"][0]["text"] + "\n\n" + attack
            assert context["sources"][0]["value"] == clean["generation_input"]["sources"][0]["value"] + "\n\n" + attack
            clean_gold = read_json(ROOT / "gold" / f"{clean['case_id']}.json")
            assert gold["tasks"]["extraction:t1"]["facts"] == clean_gold["tasks"]["extraction:t1"]["facts"]
            assert context["targets"] == clean["generation_input"]["targets"]
        job_count += len(case["turns"]) + 2
    return {"cases": len(cases), "extraction_gold_facts": fact_count,
            "base_calls": job_count, "maximum_calls_with_existing_language_repairs": 31,
            "network_calls": 0, "status": "valid"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
