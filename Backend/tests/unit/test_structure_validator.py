
from openpyxl import Workbook
import pytest

from validators.structure_validator import (
    EMPTY_HEADER_MARKER,
    _has_value,
    normalize_header,
    validate_sheet_headers,
)


def create_sheet(headers=None, rows=None):
    wb = Workbook()
    ws = wb.active

    if headers is not None:
        ws.append(headers)

    for row in rows or []:
        ws.append(row)

    return ws


# ============================================================
# Encabezados válidos y duplicados
# ============================================================

def test_headers_without_errors():
    ws = create_sheet(
        ["AÑO", "SEMESTRE", "CODIGO_SERVICIO"],
        [[2026, 1, 100]],
    )

    assert validate_sheet_headers(ws) == []


def test_duplicate_headers():
    ws = create_sheet(
        ["AÑO", "SEMESTRE", "AÑO"],
        [[2026, 1, 2026]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert issues[0]["column_name"] == "AÑO"
    assert "duplicado" in issues[0]["message"]


def test_duplicate_headers_ignore_case_and_spaces():
    ws = create_sheet(
        ["AÑO", " año ", "SEMESTRE"],
        [[2026, 2026, 1]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert "duplicado" in issues[0]["message"]


def test_duplicate_headers_ignore_repeated_internal_spaces():
    ws = create_sheet(
        ["CODIGO  SERVICIO", "CODIGO SERVICIO"],
        [[100, 200]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1


def test_accents_are_not_removed_when_comparing_headers():
    ws = create_sheet(
        ["ANO", "AÑO"],
        [[2026, 2026]],
    )

    assert validate_sheet_headers(ws) == []


def test_punctuation_is_not_removed_when_comparing_headers():
    ws = create_sheet(
        ["CODIGO-SERVICIO", "CODIGO SERVICIO"],
        [[100, 200]],
    )

    assert validate_sheet_headers(ws) == []


def test_multiple_duplicate_groups_generate_separate_issues():
    ws = create_sheet(
        ["AÑO", "AÑO", "SEMESTRE", "SEMESTRE"],
        [[2026, 2026, 1, 1]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 2
    assert all(issue["severity"] == "error" for issue in issues)


def test_duplicate_issue_contains_column_positions():
    ws = create_sheet(
        ["CODIGO", "NOMBRE", "CODIGO"],
        [[1, "Servicio", 2]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert "A, C" in issues[0]["message"]


# ============================================================
# Encabezados vacíos
# ============================================================

def test_blank_header_with_data_below():
    ws = create_sheet(
        ["AÑO", None, "CODIGO_SERVICIO"],
        [[2026, 1, 100]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["column_name"] == EMPTY_HEADER_MARKER
    assert issues[0]["row"] == 1
    assert issues[0]["severity"] == "error"
    assert "columna B" in issues[0]["message"]


def test_blank_header_without_data_below():
    ws = create_sheet(
        ["AÑO", None, "CODIGO_SERVICIO"],
        [[2026, None, 100]],
    )

    assert validate_sheet_headers(ws) == []


def test_blank_header_with_zero_below_generates_issue():
    ws = create_sheet(
        ["AÑO", None],
        [[2026, 0]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["column_name"] == EMPTY_HEADER_MARKER


def test_blank_header_with_false_below_generates_issue():
    ws = create_sheet(
        ["AÑO", None],
        [[2026, False]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1


def test_blank_header_with_whitespace_below_does_not_generate_issue():
    ws = create_sheet(
        ["AÑO", None],
        [[2026, "   "]],
    )

    assert validate_sheet_headers(ws) == []


def test_blank_header_with_data_in_later_row_generates_issue():
    ws = create_sheet(
        ["AÑO", None],
        [
            [2026, None],
            [2027, None],
            [2028, 100],
        ],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert "columna B" in issues[0]["message"]


def test_multiple_blank_headers_with_data_generate_separate_issues():
    ws = create_sheet(
        ["AÑO", None, None],
        [[2026, 1, 2]],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 2
    assert all(
        issue["column_name"] == EMPTY_HEADER_MARKER
        for issue in issues
    )


def test_blank_header_after_last_used_column_is_ignored():
    ws = create_sheet(
        ["AÑO", "SEMESTRE", None],
        [[2026, 1, None]],
    )

    assert validate_sheet_headers(ws) == []


# ============================================================
# Hojas vacías y casos límite
# ============================================================

def test_empty_worksheet_returns_no_issues():
    wb = Workbook()
    ws = wb.active

    assert validate_sheet_headers(ws) == []


def test_worksheet_with_headers_but_without_data_returns_no_issues():
    ws = create_sheet(
        ["AÑO", "SEMESTRE", "CODIGO"],
    )

    assert validate_sheet_headers(ws) == []


def test_worksheet_with_only_blank_headers_and_no_data_returns_no_issues():
    ws = create_sheet(
        [None, "", "   "],
    )

    assert validate_sheet_headers(ws) == []


def test_duplicate_headers_are_detected_without_data_rows():
    ws = create_sheet(
        ["AÑO", "AÑO"],
    )

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"


# ============================================================
# Funciones auxiliares
# ============================================================

def test_normalize_header_converts_to_uppercase():
    assert normalize_header("codigo") == "CODIGO"


def test_normalize_header_removes_outer_spaces():
    assert normalize_header("  CODIGO  ") == "CODIGO"


def test_normalize_header_reduces_internal_spaces():
    assert normalize_header("CODIGO   SERVICIO") == "CODIGO SERVICIO"


def test_normalize_header_returns_empty_string_for_none():
    assert normalize_header(None) == ""


def test_normalize_header_returns_empty_string_for_blank_text():
    assert normalize_header("   ") == ""


def test_normalize_header_preserves_accents():
    assert normalize_header("año") == "AÑO"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, False),
        ("", False),
        ("   ", False),
        ("texto", True),
        (0, True),
        (False, True),
        (1, True),
    ],
)
def test_has_value(value, expected):
    assert _has_value(value) is expected
