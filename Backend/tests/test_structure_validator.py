
from openpyxl import Workbook

from validators.structure_validator import (
    validate_sheet_headers,
)


def test_headers_without_errors():

    wb = Workbook()
    ws = wb.active

    ws.append(["AÑO", "SEMESTRE", "CODIGO_SERVICIO"])
    ws.append([2026, 1, 100])

    issues = validate_sheet_headers(ws)

    assert issues == []


def test_duplicate_headers():

    wb = Workbook()
    ws = wb.active

    ws.append(["AÑO", "SEMESTRE", "AÑO"])
    ws.append([2026, 1, 2026])

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "duplicado" in issues[0]["message"]


def test_blank_header_with_data_below():

    wb = Workbook()
    ws = wb.active

    ws.append(["AÑO", None, "CODIGO_SERVICIO"])
    ws.append([2026, 1, 100])

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert issues[0]["column_name"] == "__ENCABEZADO_VACIO__"
    assert "columna B" in issues[0]["message"]


def test_blank_header_without_data_below():

    wb = Workbook()
    ws = wb.active

    ws.append(["AÑO", None, "CODIGO_SERVICIO"])
    ws.append([2026, None, 100])

    issues = validate_sheet_headers(ws)

    assert issues == []


def test_duplicate_headers_ignore_case_and_spaces():

    wb = Workbook()
    ws = wb.active

    ws.append(["AÑO", " año ", "SEMESTRE"])
    ws.append([2026, 2026, 1])

    issues = validate_sheet_headers(ws)

    assert len(issues) == 1
    assert "duplicado" in issues[0]["message"]
