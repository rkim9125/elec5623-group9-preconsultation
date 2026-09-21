import logging
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APIConnectionError

from app.core.config import Settings
from app.core.models import SessionState, SlotStatus
from app.core.schema import SCHEMA_VERSION, build_initial_slots
from app.llm.azure import (
    AzureLLM,
    _CandidateBatch,
    _CandidatePayload,
    _QuestionPayload,
    _SummaryItem,
    _SummaryPayload,
)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="azure",
        llm_api_key="test-key",
        llm_base_url="https://example.test/openai/v1/",
        llm_model="test-model",
    )


def _azure_llm() -> AzureLLM:
    client = AzureLLM(_settings())
    client._client = Mock()
    return client


def _state() -> SessionState:
    return SessionState(
        session_id="test-session",
        schema_version=SCHEMA_VERSION,
        slots=build_initial_slots(),
    )


@pytest.mark.parametrize(
    "field",
    ["llm_api_key", "llm_base_url", "llm_model"],
)
def test_init_rejects_missing_required_setting(field: str):
    values = {
        "llm_provider": "azure",
        "llm_api_key": "test-key",
        "llm_base_url": "https://example.test/openai/v1/",
        "llm_model": "test-model",
    }
    values[field] = ""

    with pytest.raises(ValueError):
        AzureLLM(Settings(_env_file=None, **values))


def test_client_has_bounded_retries_and_timeout():
    client = AzureLLM(_settings())

    assert client._client.max_retries == 2
    assert client._client.timeout == 30.0


def test_extract_candidates_filters_unknown_slots_and_invalid_evidence():
    client = _azure_llm()
    message = "I have had a severe headache for 3 days."
    parsed = _CandidateBatch(
        candidates=[
            _CandidatePayload(
                slot_id="symptom_duration_days",
                value=3,
                confidence=0.95,
                evidence_span="for 3 days",
                rationale="Explicit duration.",
            ),
            _CandidatePayload(
                slot_id="invented_slot",
                value="invented",
                confidence=0.9,
                evidence_span="severe headache",
                rationale="Invalid slot.",
            ),
            _CandidatePayload(
                slot_id="symptom_severity",
                value="severe",
                confidence=0.9,
                evidence_span="text not present in the message",
                rationale="Invalid evidence.",
            ),
        ]
    )
    client._client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed)

    candidates = client.extract_candidates(
        message=message,
        slots=build_initial_slots(),
        schema_version=SCHEMA_VERSION,
    )

    assert len(candidates) == 1
    assert candidates[0].slot_id == "symptom_duration_days"
    assert candidates[0].value == 3
    assert candidates[0].model == "test-model"


def test_extract_candidates_returns_empty_when_parsing_has_no_result():
    client = _azure_llm()
    client._client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

    candidates = client.extract_candidates(
        message="No useful information.",
        slots=build_initial_slots(),
        schema_version=SCHEMA_VERSION,
    )

    assert candidates == []


def test_extract_candidates_falls_back_on_api_failure():
    client = _azure_llm()
    client._client.responses.parse.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://example.test/openai/v1/responses")
    )

    candidates = client.extract_candidates(
        message="I have a headache.",
        slots=build_initial_slots(),
        schema_version=SCHEMA_VERSION,
    )

    assert candidates == []


def test_success_log_records_prompt_version_tokens_and_latency(caplog):
    client = _azure_llm()
    parsed = _CandidateBatch(candidates=[])
    client._client.responses.parse.return_value = SimpleNamespace(
        output_parsed=parsed,
        usage=SimpleNamespace(input_tokens=10, output_tokens=4, total_tokens=14),
    )
    caplog.set_level(logging.INFO, logger="app.llm.azure")

    client.extract_candidates(
        message="Nothing relevant.",
        slots=build_initial_slots(),
        schema_version=SCHEMA_VERSION,
    )

    assert "prompt_version=extract-v1" in caplog.text
    assert "input_tokens=10" in caplog.text
    assert "output_tokens=4" in caplog.text
    assert "total_tokens=14" in caplog.text
    assert "latency_ms=" in caplog.text


def test_phrase_question_uses_structured_result():
    client = _azure_llm()
    state = _state()
    parsed = _QuestionPayload(question="What medications are you currently taking?")
    client._client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed)

    question = client.phrase_question(state.slots["current_medications"], state)

    assert question == "What medications are you currently taking?"
    request = client._client.responses.parse.call_args.kwargs
    assert '"required": true' in request["input"][1]["content"]


def test_phrase_question_falls_back_when_parsing_has_no_result():
    client = _azure_llm()
    state = _state()
    client._client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

    question = client.phrase_question(state.slots["allergies"], state)

    assert question == "Could you tell me about known allergies?"


def test_generate_summary_uses_only_resolved_slots():
    client = _azure_llm()
    state = _state()

    state.slots["chief_complaint"].status = SlotStatus.CONFIRMED
    state.slots["chief_complaint"].value = "Severe headache"
    state.slots["allergies"].status = SlotStatus.SKIPPED
    state.slots["past_conditions"].status = SlotStatus.UNKNOWN
    state.slots["symptom_location"].status = SlotStatus.CANDIDATE
    state.slots["symptom_location"].value = "unconfirmed secret value"

    parsed = _SummaryPayload(
        items=[
            _SummaryItem(
                slot_id="chief_complaint",
                text="The patient reports a severe headache.",
            ),
            _SummaryItem(
                slot_id="symptom_location",
                text="This unconfirmed value must be rejected.",
            ),
        ],
        patient_questions=[
            "Question one?",
            "Question two?",
            "Question three?",
            "Question four?",
        ],
    )
    client._client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed)

    summary = client.generate_summary(state)

    assert summary.sections["Main reason for the visit"] == (
        "The patient reports a severe headache."
    )
    assert summary.sections["Known allergies"] == "(patient chose to skip)"
    assert summary.sections["Relevant past medical conditions"] == (
        "(patient does not know)"
    )
    assert "Where the symptoms are located" not in summary.sections
    assert len(summary.patient_questions) == 3
    assert summary.model == "test-model"

    request = client._client.responses.parse.call_args.kwargs
    assert "unconfirmed secret value" not in request["input"][1]["content"]
