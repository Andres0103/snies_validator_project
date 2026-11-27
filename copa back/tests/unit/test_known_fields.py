
import pytest

from rules.known_fields import _load_allowed_values
from rules.general_model import AllowedValue


def test_load_allowed_values_accepts_simple_values():
    result = _load_allowed_values(
        [1, 2, "CC"],
        "SEMESTRE",
    )

    assert result == [
        AllowedValue(code="1", label="1"),
        AllowedValue(code="2", label="2"),
        AllowedValue(code="CC", label="CC"),
    ]


def test_load_allowed_values_accepts_dictionaries():
    result = _load_allowed_values(
        [
            {
                "code": "1",
                "label": "Periodo anual",
            },
            {
                "code": "2",
                "label": "Periodo semestral",
            },
        ],
        "SEMESTRE",
    )

    assert result == [
        AllowedValue(code="1", label="Periodo anual"),
        AllowedValue(code="2", label="Periodo semestral"),
    ]


def test_load_allowed_values_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicado"):
        _load_allowed_values(
            [1, "1"],
            "SEMESTRE",
        )


def test_load_allowed_values_rejects_boolean():
    with pytest.raises(ValueError):
        _load_allowed_values(
            [True, False],
            "SEMESTRE",
        )


def test_load_allowed_values_rejects_invalid_dictionary():
    with pytest.raises(ValueError, match="code"):
        _load_allowed_values(
            [{"code": "1"}],
            "SEMESTRE",
        )


def test_load_allowed_values_rejects_empty_values():
    with pytest.raises(ValueError, match="vacío"):
        _load_allowed_values(
            [""],
            "SEMESTRE",
        )
