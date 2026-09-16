import pytest

from app.core.safety import SAFETY_RULES, check_safety


@pytest.mark.parametrize(
    "message, category",
    [
        ("I've had chest pain since this morning", "cardiac"),
        ("I can't breathe properly", "breathing"),
        ("my face is drooping and speech is slurred", "stroke"),
        ("my throat is closing up after eating nuts", "anaphylaxis"),
        ("sometimes I think about killing myself", "self_harm"),
        ("the cut won't stop bleeding", "severe_bleeding"),
    ],
)
def test_red_flags_trigger_with_fixed_wording(message, category):
    res = check_safety(message)
    assert res.triggered is True
    assert res.stop is True
    assert res.category == category
    assert res.message and "000" in res.message or "13 11 14" in (res.message or "")


@pytest.mark.parametrize(
    "message",
    [
        "I have a mild sore throat and a runny nose",
        "my knee has been aching for a week",
        "I need a repeat prescription for my blood pressure tablets",
    ],
)
def test_benign_messages_do_not_trigger(message):
    res = check_safety(message)
    assert res.triggered is False
    assert res.stop is False
    assert res.message is None


def test_matching_is_case_insensitive():
    assert check_safety("CHEST PAIN and sweating").triggered is True


def test_every_rule_message_carries_the_disclaimer():
    for rule in SAFETY_RULES:
        assert "cannot assess" in rule.message
