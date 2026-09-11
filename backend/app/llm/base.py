"""The C3 <-> C4 boundary.

C4 implements `LLMClient`. C3 depends only on this Protocol, so the core logic can
be built and tested with `FakeLLM` (app/llm/fake.py) before C4 is ready.

Rules (see docs/api-contract.md sections 4-5 and the C3/C4 boundary notes):
- The LLM returns *candidates* and *wording*. It never decides acceptance, never
  picks a different question target, never publishes a final summary.
- C3 validates every returned value against the consultation schema and controls
  what enters session state.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.core.models import Candidate, SessionState, Slot


class ExtractedCandidate(Candidate):
    """A `Candidate` plus the slot it targets. Used only in transit from C4.

    C3 strips `slot_id` and appends the rest to `Slot.candidates[]`.
    """

    slot_id: str


class GeneratedSummary(BaseModel):
    """Grounded summary produced from validated state, for the clinician view."""

    sections: dict[str, str] = Field(default_factory=dict)
    patient_questions: list[str] = Field(default_factory=list)
    model: str = "unknown"


@runtime_checkable
class LLMClient(Protocol):
    def extract_candidates(
        self,
        message: str,
        slots: dict[str, Slot],
        schema_version: str,
    ) -> list[ExtractedCandidate]:
        """Parse a patient message into candidate slot values with evidence."""
        ...

    def phrase_question(self, slot: Slot, state: SessionState) -> str:
        """Neutral wording for asking about `slot`. Target is chosen by C3."""
        ...

    def generate_summary(self, state: SessionState) -> GeneratedSummary:
        """Summarise confirmed state. Not authoritative until patient-approved."""
        ...
