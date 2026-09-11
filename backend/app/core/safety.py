"""Predefined safety interruption.

This is **pattern matching against a fixed list**, not triage, diagnosis or an
urgency score. When a patient message matches a red-flag pattern, the flow shows
the approved fixed wording for that category and pauses; a human decides what
happens next.

The patterns and wording below are PLACEHOLDERS pending team + supervisor
sign-off (proposal: "predefined safety controls and approved fixed wording").
Do not treat them as clinically reviewed.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_DISCLAIMER = (
    "This tool cannot assess urgent or emergency situations and is not a "
    "substitute for medical advice."
)


class SafetyRule(BaseModel):
    category: str
    pattern: str  # regex, matched case-insensitively against the raw message
    message: str


class SafetyResult(BaseModel):
    triggered: bool
    category: str | None = None
    message: str | None = None
    stop: bool = False


SAFETY_RULES: list[SafetyRule] = [
    SafetyRule(
        category="cardiac",
        pattern=r"chest pain|chest tightness|pressure in (my )?chest|crushing chest",
        message=(
            "You mentioned chest pain or chest tightness. If you have this now, "
            "especially with shortness of breath, sweating, or pain in the arm or "
            "jaw, call 000 or go to your nearest emergency department now. "
            + _DISCLAIMER
        ),
    ),
    SafetyRule(
        category="breathing",
        pattern=r"can('?t| ?not) breathe|struggling to breathe|gasping for air|severe shortness of breath",
        message=(
            "You mentioned serious difficulty breathing. If you are struggling to "
            "breathe now, call 000 or go to your nearest emergency department. "
            + _DISCLAIMER
        ),
    ),
    SafetyRule(
        category="stroke",
        pattern=r"face (is )?drooping|drooping face|(slurred|slurring) speech|speech (is )?slurred|sudden weakness on one side|can('?t| ?not) move (my )?(arm|leg|face)",
        message=(
            "The symptoms you described can be signs of a stroke. This needs "
            "urgent assessment - call 000 now. " + _DISCLAIMER
        ),
    ),
    SafetyRule(
        category="anaphylaxis",
        pattern=r"throat (is )?closing|tongue swelling|lips swelling|anaphylaxis|can('?t| ?not) swallow",
        message=(
            "You described possible signs of a severe allergic reaction. If your "
            "throat feels tight or your tongue or lips are swelling, use an "
            "adrenaline autoinjector if you have one and call 000. " + _DISCLAIMER
        ),
    ),
    SafetyRule(
        category="self_harm",
        pattern=r"kill(ing)? myself|suicid(e|al)|end my life|don'?t want to (be alive|live)|harm(ing)? myself",
        message=(
            "It sounds like you may be going through a very difficult time. If you "
            "are thinking about harming yourself, please contact Lifeline on "
            "13 11 14 or call 000 now. You deserve support. " + _DISCLAIMER
        ),
    ),
    SafetyRule(
        category="severe_bleeding",
        pattern=r"(won('?t| ?not) stop|heavy|uncontrolled) bleeding|bleeding heavily",
        message=(
            "You mentioned heavy or uncontrolled bleeding. Apply firm pressure and "
            "call 000 or go to your nearest emergency department. " + _DISCLAIMER
        ),
    ),
]

_COMPILED = [(r, re.compile(r.pattern, re.IGNORECASE)) for r in SAFETY_RULES]


def check_safety(message: str) -> SafetyResult:
    """Return the first matching rule, or a non-triggered result."""
    for rule, rx in _COMPILED:
        if rx.search(message):
            return SafetyResult(
                triggered=True,
                category=rule.category,
                message=rule.message,
                stop=True,
            )
    return SafetyResult(triggered=False)
