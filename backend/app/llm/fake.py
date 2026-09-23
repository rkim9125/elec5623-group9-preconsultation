"""Deterministic stand-in for the real LLM (C4).

Rule-based, no network. Good enough to develop and test C3's state engine and
session APIs. Not intended to be accurate — just structurally valid and stable.
"""

from __future__ import annotations

import re

from app.core.models import SessionState, Slot, SlotStatus
from app.llm.base import ExtractedCandidate, GeneratedSummary

MODEL_NAME = "fake-llm-0"

_SEVERITY_WORDS = {"mild": "mild", "moderate": "moderate", "severe": "severe", "bad": "severe"}
_SYMPTOM_WORDS = ["fever", "cough", "sore throat", "headache", "nausea", "fatigue", "rash"]


def _first_int(text: str) -> int | None:
    m = re.search(r"\b(\d{1,3})\b", text)
    return int(m.group(1)) if m else None


class FakeLLM:
    """Implements the `LLMClient` protocol."""

    def extract_candidates(
        self,
        message: str,
        slots: dict[str, Slot],
        schema_version: str,
    ) -> list[ExtractedCandidate]:
        text = message.lower().strip()
        out: list[ExtractedCandidate] = []

        def add(slot_id: str, value: object, confidence: float, span: str) -> None:
            if slot_id in slots:
                out.append(
                    ExtractedCandidate(
                        slot_id=slot_id,
                        value=value,
                        confidence=confidence,
                        evidence_span=span,
                        rationale="fake keyword match",
                        model=MODEL_NAME,
                    )
                )

        chief = slots.get("chief_complaint")
        if chief is not None and chief.status == SlotStatus.EMPTY and text:
            add("chief_complaint", message.strip(), 0.5, message.strip()[:120])

        found = [w for w in _SYMPTOM_WORDS if w in text]
        if found:
            add("associated_symptoms", found, 0.8, ", ".join(found))

        n = _first_int(text)
        if n is not None and ("day" in text or "week" in text or "since" in text):
            days = n * 7 if "week" in text else n
            add("symptom_duration_days", days, 0.6, str(n))
            if "fever" in found:
                add("fever_duration_days", days, 0.55, str(n))

        for word, canonical in _SEVERITY_WORDS.items():
            if re.search(rf"\b{word}\b", text):
                add("symptom_severity", canonical, 0.7, word)
                break

        if "no medication" in text or "not taking anything" in text:
            add("current_medications", [], 0.7, text)
        if "no allerg" in text or "no known allerg" in text:
            add("allergies", [], 0.75, text)

        return out

    def phrase_question(self, slot: Slot, state: SessionState) -> str:
        return f"Could you tell me about: {slot.label.lower()}?"

    def generate_summary(self, state: SessionState) -> GeneratedSummary:
        sections: dict[str, str] = {}
        for slot in state.slots.values():
            if slot.status == SlotStatus.CONFIRMED and slot.value not in (None, [], ""):
                sections[slot.label] = str(slot.value)
            elif slot.status == SlotStatus.SKIPPED:
                sections[slot.label] = "(patient chose not to answer)"
            elif slot.status == SlotStatus.UNKNOWN:
                sections[slot.label] = "(patient did not know)"
        return GeneratedSummary(
            sections=sections,
            patient_questions=self._patient_questions(state),
            model=MODEL_NAME,
        )

    @staticmethod
    def _patient_questions(state: SessionState) -> list[str]:
        """The patient's own questions win. Generated suggestions are only a
        fallback for when they haven't given any — never a replacement."""
        slot = state.slots.get("clinician_questions")
        if slot is not None and slot.status == SlotStatus.CONFIRMED and slot.value:
            return [str(q) for q in slot.value]
        return [
            "What are the most likely causes of my symptoms?",
            "Is there anything I should do or avoid before the appointment?",
        ]
