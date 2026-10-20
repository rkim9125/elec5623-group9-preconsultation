"""ABO-only patient reports must not acquire an inferred Rh factor."""
import pytest
from pydantic import ValidationError

from app.product.profiles import PatientProfileInput


@pytest.mark.parametrize("value", ["", "unknown", "A", "B", "AB", "O", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
def test_blood_group_preserves_exact_known_information(value):
    assert PatientProfileInput(blood_group=value).model_dump()["blood_group"] == value


@pytest.mark.parametrize("value", ["C", "+", "-", "O positive", "Rh+", "unknown+"])
def test_invalid_blood_groups_are_rejected(value):
    with pytest.raises(ValidationError):
        PatientProfileInput(blood_group=value)
