import pytest
from datetime import date, datetime
from decimal import Decimal

from rules.general_model import DataType
from validators.cross_row_validator import (
    CrossRowIssue,
    _is_blank,
    _normalize_value,
    check_uniqueness,
    check_code_consistency,
)


# ============================================================
# _is_blank
# ============================================================

@pytest.mark.parametrize(
    "value",
    [None, "", " ", "   ", "\t", "\n"],
)
def test_is_blank_returns_true_for_empty_values(value):
    assert _is_blank(value) is True


@pytest.mark.parametrize(
    "value",
    [0, 0.0, False, "0", "texto"],
)
def test_is_blank_returns_false_for_non_empty_values(value):
    assert _is_blank(value) is False


# ============================================================
# _normalize_value
# ============================================================

def test_normalize_text_removes_external_spaces():
    result = _normalize_value("  ABC  ", DataType.TEXT)

    assert result == ("text", "ABC")


def test_normalize_text_preserves_leading_zeros():
    result = _normalize_value("00123", DataType.ALPHANUMERIC)

    assert result == ("text", "00123")


def test_normalize_unknown_as_text():
    result = _normalize_value(" 001 ", DataType.UNKNOWN)

    assert result == ("text", "001")


def test_normalize_integer_and_decimal_as_equivalent_numbers():
    integer = _normalize_value(10, DataType.INTEGER)
    decimal = _normalize_value("10.0", DataType.DECIMAL)

    assert integer == decimal


def test_normalize_decimal_from_float():
    result = _normalize_value(10.5, DataType.DECIMAL)

    assert result == ("number", Decimal("10.5"))


def test_normalize_invalid_number():
    result = _normalize_value("ABC", DataType.DECIMAL)

    assert result == ("invalid", "ABC")


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_normalize_non_finite_number_as_invalid(value):
    result = _normalize_value(value, DataType.DECIMAL)

    assert result[0] == "invalid"


def test_normalize_empty_values():
    assert _normalize_value(None, DataType.TEXT) == ("blank", "")
    assert _normalize_value(" ", DataType.INTEGER) == ("blank", "")


def test_normalize_date_object():
    result = _normalize_value(
        date(2025, 1, 15),
        DataType.DATE,
    )

    assert result == ("date", "2025-01-15")


def test_normalize_datetime_object():
    result = _normalize_value(
        datetime(2025, 1, 15, 10, 30),
        DataType.DATE,
    )

    assert result == ("date", "2025-01-15")


@pytest.mark.parametrize(
    "value",
    [
        "2025-01-15",
        "15/01/2025",
        "15-01-2025",
    ],
)
def test_normalize_equivalent_date_formats(value):
    result = _normalize_value(value, DataType.DATE)

    assert result == ("date", "2025-01-15")


def test_normalize_invalid_date():
    result = _normalize_value("31/02/2025", DataType.DATE)

    assert result == ("invalid", "31/02/2025")


# ============================================================
# check_uniqueness
# ============================================================

def test_check_uniqueness_detects_duplicate_values():
    rows = [
        {"CODIGO": "A01"},
        {"CODIGO": "A02"},
        {"CODIGO": "A01"},
    ]

    issues = check_uniqueness(
        column_name="CODIGO",
        rows=rows,
        row_numbers=[2, 3, 4],
        column_types={"CODIGO": DataType.TEXT},
    )

    assert len(issues) == 2
    assert {issue.row for issue in issues} == {2, 4}
    assert all(issue.column_name == "CODIGO" for issue in issues)


def test_check_uniqueness_ignores_unique_values():
    rows = [
        {"CODIGO": "A01"},
        {"CODIGO": "A02"},
        {"CODIGO": "A03"},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3, 4],
        {"CODIGO": DataType.TEXT},
    )

    assert issues == []


def test_check_uniqueness_ignores_blank_values():
    rows = [
        {"CODIGO": None},
        {"CODIGO": ""},
        {"CODIGO": " "},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3, 4],
        {"CODIGO": DataType.TEXT},
    )

    assert issues == []


def test_check_uniqueness_respects_configured_severity():
    rows = [
        {"CODIGO": "A01"},
        {"CODIGO": "A01"},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3],
        {"CODIGO": DataType.TEXT},
        severity="error",
    )

    assert len(issues) == 2
    assert all(issue.severity == "error" for issue in issues)


def test_check_uniqueness_uses_custom_message():
    rows = [
        {"CODIGO": "A01"},
        {"CODIGO": "A01"},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3],
        {"CODIGO": DataType.TEXT},
        message_template="Código duplicado.",
    )

    assert len(issues) == 2
    assert all(
        issue.message == "Código duplicado."
        for issue in issues
    )


def test_check_uniqueness_uses_unknown_when_column_type_missing():
    rows = [
        {"CODIGO": " A01 "},
        {"CODIGO": "A01"},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3],
        {},
    )

    assert len(issues) == 2


def test_check_uniqueness_compares_numeric_values():
    rows = [
        {"VALOR": 10},
        {"VALOR": "10.0"},
        {"VALOR": "20"},
    ]

    issues = check_uniqueness(
        "VALOR",
        rows,
        [2, 3, 4],
        {"VALOR": DataType.DECIMAL},
    )

    assert len(issues) == 2
    assert {issue.row for issue in issues} == {2, 3}


def test_check_uniqueness_compares_equivalent_date_formats():
    rows = [
        {"FECHA": "2025-01-15"},
        {"FECHA": "15/01/2025"},
        {"FECHA": "2025-01-16"},
    ]

    issues = check_uniqueness(
        "FECHA",
        rows,
        [2, 3, 4],
        {"FECHA": DataType.DATE},
    )

    assert len(issues) == 2


def test_check_uniqueness_reports_all_rows_in_duplicate_group():
    rows = [
        {"CODIGO": "A01"},
        {"CODIGO": "A01"},
        {"CODIGO": "A01"},
    ]

    issues = check_uniqueness(
        "CODIGO",
        rows,
        [2, 3, 4],
        {"CODIGO": DataType.TEXT},
    )

    assert len(issues) == 3
    assert {issue.row for issue in issues} == {2, 3, 4}
    assert all("3 filas" in issue.message for issue in issues)


# ============================================================
# check_code_consistency
# ============================================================

def test_code_consistency_accepts_consistent_values():
    rows = [
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
    ]

    issues = check_code_consistency(
        code_column="CODIGO",
        check_columns=["NOMBRE"],
        rows=rows,
        row_numbers=[2, 3],
        column_types={
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert issues == []


def test_code_consistency_detects_different_values():
    rows = [
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
        {"CODIGO": "A01", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert len(issues) == 2
    assert {issue.row for issue in issues} == {2, 3}
    assert all(issue.column_name == "NOMBRE" for issue in issues)


def test_code_consistency_ignores_rows_without_code():
    rows = [
        {"CODIGO": None, "NOMBRE": "Proyecto A"},
        {"CODIGO": "", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert issues == []


def test_code_consistency_does_not_compare_different_codes():
    rows = [
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
        {"CODIGO": "A02", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert issues == []


def test_code_consistency_treats_blank_and_filled_as_different():
    rows = [
        {"CODIGO": "A01", "NOMBRE": ""},
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert len(issues) == 2


def test_code_consistency_treats_all_blank_values_as_consistent():
    rows = [
        {"CODIGO": "A01", "NOMBRE": ""},
        {"CODIGO": "A01", "NOMBRE": None},
        {"CODIGO": "A01", "NOMBRE": "   "},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3, 4],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert issues == []


def test_code_consistency_normalizes_numeric_codes():
    rows = [
        {"CODIGO": 10, "NOMBRE": "Proyecto A"},
        {"CODIGO": "10.0", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.DECIMAL,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert len(issues) == 2


def test_code_consistency_respects_group_by():
    rows = [
        {
            "CODIGO": "A01",
            "VIGENCIA": "2024",
            "NOMBRE": "Proyecto A",
        },
        {
            "CODIGO": "A01",
            "VIGENCIA": "2025",
            "NOMBRE": "Proyecto B",
        },
    ]

    issues = check_code_consistency(
        code_column="CODIGO",
        check_columns=["NOMBRE"],
        rows=rows,
        row_numbers=[2, 3],
        column_types={
            "CODIGO": DataType.TEXT,
            "VIGENCIA": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
        group_by="VIGENCIA",
    )

    assert issues == []


def test_code_consistency_detects_differences_inside_same_group():
    rows = [
        {
            "CODIGO": "A01",
            "VIGENCIA": "2025",
            "NOMBRE": "Proyecto A",
        },
        {
            "CODIGO": "A01",
            "VIGENCIA": "2025",
            "NOMBRE": "Proyecto B",
        },
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "VIGENCIA": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
        group_by="VIGENCIA",
    )

    assert len(issues) == 2


def test_code_consistency_compares_multiple_columns():
    rows = [
        {
            "CODIGO": "A01",
            "NOMBRE": "Proyecto A",
            "ESTADO": "Activo",
        },
        {
            "CODIGO": "A01",
            "NOMBRE": "Proyecto B",
            "ESTADO": "Inactivo",
        },
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE", "ESTADO"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
            "ESTADO": DataType.TEXT,
        },
    )

    assert len(issues) == 4
    assert {issue.column_name for issue in issues} == {
        "NOMBRE",
        "ESTADO",
    }


def test_code_consistency_does_not_report_single_row_groups():
    rows = [
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
        {"CODIGO": "A02", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert issues == []


def test_code_consistency_returns_error_severity_by_default():
    rows = [
        {"CODIGO": "A01", "NOMBRE": "Proyecto A"},
        {"CODIGO": "A01", "NOMBRE": "Proyecto B"},
    ]

    issues = check_code_consistency(
        "CODIGO",
        ["NOMBRE"],
        rows,
        [2, 3],
        {
            "CODIGO": DataType.TEXT,
            "NOMBRE": DataType.TEXT,
        },
    )

    assert all(issue.severity == "error" for issue in issues)


# ============================================================
# CrossRowIssue
# ============================================================

def test_cross_row_issue_default_severity():
    issue = CrossRowIssue(
        row=2,
        column_name="CODIGO",
        message="Código duplicado.",
    )

    assert issue.row == 2
    assert issue.column_name == "CODIGO"
    assert issue.message == "Código duplicado."
    assert issue.severity == "error"