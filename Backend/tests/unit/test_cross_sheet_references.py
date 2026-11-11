
from openpyxl import Workbook

from backend.rules.general_model import DataType
from validators.cross_sheet_validator import (
    validate_sheet_references,
    _normalize_key_value,
    _build_row_key,
)


def create_consultoria_workbook(parent_rows, child_rows):
    wb = Workbook()

    parent = wb.active
    parent.title = "CONSULTORIA"
    parent.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])

    for row in parent_rows:
        parent.append(row)

    child = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    child.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])

    for row in child_rows:
        child.append(row)

    return wb


def test_matching_reference_generates_no_issues():
    wb = create_consultoria_workbook(
        [[2026, -1, "CON-001"]],
        [[2026, -1, "CON-001"]],
    )

    assert validate_sheet_references(
        wb, "CONSULTORIA"
    ) == []


def test_missing_parent_sheet_skips_reference_validation():
    wb = Workbook()
    ws = wb.active
    ws.title = "CONSULTORIA_REC_HUMANO"
    ws.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    ws.append([2026, -1, "CON-999"])

    assert validate_sheet_references(
        wb, "CONSULTORIA"
    ) == []


def test_missing_child_sheet_skips_reference_validation():
    wb = Workbook()
    ws = wb.active
    ws.title = "CONSULTORIA"
    ws.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    ws.append([2026, -1, "CON-001"])

    assert validate_sheet_references(
        wb, "CONSULTORIA"
    ) == []


def test_missing_key_column_generates_structure_issue():
    wb = Workbook()

    parent = wb.active
    parent.title = "CONSULTORIA"
    parent.append(["AÑO", "CODIGO_CONSULTORIA"])
    parent.append([2026, "CON-001"])

    child = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    child.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    child.append([2026, -1, "CON-001"])

    issues = validate_sheet_references(
        wb, "CONSULTORIA"
    )

    assert len(issues) == 1
    assert issues[0]["row"] == 1
    assert issues[0]["severity"] == "error"
    assert "SEMESTRE" in issues[0]["message"]


def test_duplicate_parent_keys_are_valid_references():
    wb = create_consultoria_workbook(
        [
            [2026, -1, "CON-001"],
            [2026, -1, "CON-001"],
        ],
        [[2026, -1, "CON-001"]],
    )

    assert validate_sheet_references(
        wb, "CONSULTORIA"
    ) == []


def test_reference_with_blank_key_component_is_ignored():
    wb = create_consultoria_workbook(
        [[2026, -1, "CON-001"]],
        [[2026, -1, None]],
    )

    assert validate_sheet_references(
        wb, "CONSULTORIA"
    ) == []


def test_sheet_names_are_matched_without_case_sensitivity():
    wb = Workbook()

    parent = wb.active
    parent.title = "consultoria"
    parent.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    parent.append([2026, -1, "CON-001"])

    child = wb.create_sheet("consultoria_rec_humano")
    child.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    child.append([2026, -1, "CON-999"])

    issues = validate_sheet_references(
        wb, "CONSULTORIA"
    )

    assert len(issues) == 1
    assert issues[0]["row"] == 2


def test_text_normalization_preserves_leading_zeros():
    assert _normalize_key_value(
        "00123",
        DataType.TEXT,
    ) == "00123"


def test_text_normalization_ignores_case_and_outer_spaces():
    assert _normalize_key_value(
        "  con-001  ",
        DataType.TEXT,
    ) == "CON-001"


def test_integer_normalization_accepts_equivalent_values():
    values = [2026, 2026.0, "2026", "2026.0"]

    normalized = {
        _normalize_key_value(value, DataType.INTEGER)
        for value in values
    }

    assert normalized == {"2026"}


def test_integer_normalization_rejects_fractional_values():
    assert _normalize_key_value(
        "2026.5",
        DataType.INTEGER,
    ) is None


def test_decimal_normalization_accepts_equivalent_values():
    values = [10, 10.0, "10.000"]

    normalized = {
        _normalize_key_value(value, DataType.DECIMAL)
        for value in values
    }

    assert normalized == {"10"}


def test_date_normalization_accepts_supported_formats():
    values = [
        "2026-12-10",
        "10/12/2026",
        "10-12-2026",
    ]

    normalized = {
        _normalize_key_value(value, DataType.DATE)
        for value in values
    }

    assert normalized == {"2026-12-10"}


def test_build_row_key_returns_none_when_component_is_missing():
    row = {
        "AÑO": 2026,
        "SEMESTRE": None,
        "CODIGO_CONSULTORIA": "CON-001",
    }

    result = _build_row_key(
        row,
        ["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"],
        {
            "AÑO": DataType.INTEGER,
            "SEMESTRE": DataType.INTEGER,
            "CODIGO_CONSULTORIA": DataType.TEXT,
        },
    )

    assert result is None


def test_build_row_key_normalizes_all_components():
    row = {
        "AÑO": "2026.0",
        "SEMESTRE": "-1.0",
        "CODIGO_CONSULTORIA": " con-001 ",
    }

    result = _build_row_key(
        row,
        ["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"],
        {
            "AÑO": DataType.INTEGER,
            "SEMESTRE": DataType.INTEGER,
            "CODIGO_CONSULTORIA": DataType.TEXT,
        },
    )

    assert result == ("2026", "-1", "CON-001")
