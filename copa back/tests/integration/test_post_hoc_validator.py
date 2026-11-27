
from openpyxl import Workbook

from validators.post_hoc_validator import validate_workbook


def create_workbook(sheet_name="CONSULTORIA"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    return wb, ws


def get_result(results, sheet_name):
    return next(
        result for result in results
        if result.sheet_name == sheet_name
    )


def test_workbook_without_supported_template_returns_structure_error():
    wb, ws = create_workbook("HOJA_DESCONOCIDA")
    ws.append(["CAMPO"])
    ws.append(["valor"])

    results = validate_workbook(wb)

    assert len(results) == 1

    result = results[0]

    assert result.sheet_name == "ESTRUCTURA_LIBRO"
    assert len(result.issues) == 1
    assert result.issues[0].column_name == "PLANTILLA"
    assert result.issues[0].severity == "error"


def test_workbook_with_multiple_templates_returns_structure_error():
    wb, _ = create_workbook("CONSULTORIA")
    wb.create_sheet("SERVICIOS_EXTENSION")

    results = validate_workbook(wb)

    assert len(results) == 1

    result = results[0]

    assert result.sheet_name == "ESTRUCTURA_LIBRO"
    assert result.issues[0].column_name == "PLANTILLA"
    assert result.issues[0].severity == "error"


def test_unexpected_sheet_is_reported():
    wb, ws = create_workbook()
    ws.append(["CODIGO_CONSULTORIA"])
    ws.append(["A" * 30])

    # Se agregan las hojas obligatorias de la plantilla.
    wb.create_sheet("CONSULTORIA_REC_HUMANO")

    # Se agrega una hoja que no pertenece a la plantilla.
    other = wb.create_sheet("HOJA_INESPERADA")
    other.append(["CAMPO"])
    other.append(["valor"])

    results = validate_workbook(wb)

    structure_result = get_result(
        results,
        "ESTRUCTURA_LIBRO",
    )

    assert len(structure_result.issues) == 1

    issue = structure_result.issues[0]

    assert issue.column_name == "HOJAS"
    assert issue.severity == "error"
    assert "HOJA_INESPERADA" in issue.message


def test_sheet_without_headers_returns_structure_issue():
    wb, _ = create_workbook()

    results = validate_workbook(wb)

    result = get_result(results, "CONSULTORIA")

    assert result.total_rows == 0
    assert len(result.issues) == 1
    assert result.issues[0].severity == "error"


def test_empty_rows_are_not_validated_as_data():
    wb, ws = create_workbook()

    ws.append(["CODIGO_CONSULTORIA"])
    ws.append(["A" * 30])
    ws.append([None])

    results = validate_workbook(wb)

    result = get_result(results, "CONSULTORIA")

    assert result.total_rows == 2
    assert not any(
        issue.row == 3
        for issue in result.issues
    )


def test_valid_configured_field_does_not_generate_error():
    wb, ws = create_workbook()

    ws.append(["CODIGO_CONSULTORIA"])
    ws.append(["A" * 30])

    results = validate_workbook(wb)

    result = get_result(results, "CONSULTORIA")

    assert not any(
        issue.column_name == "CODIGO_CONSULTORIA"
        for issue in result.issues
    )


def test_validation_returns_result_for_each_expected_sheet():
    wb, ws = create_workbook()

    ws.append(["CODIGO_CONSULTORIA"])
    ws.append(["A" * 30])

    wb.create_sheet("CONSULTORIA_REC_HUMANO")

    results = validate_workbook(wb)

    result_names = {
        result.sheet_name
        for result in results
    }

    assert "CONSULTORIA" in result_names
    assert "CONSULTORIA_REC_HUMANO" in result_names


def test_validation_does_not_modify_workbook_values():
    wb, ws = create_workbook()

    ws.append(["CODIGO_CONSULTORIA"])
    ws.append(["A" * 30])

    original_values = [
        [cell.value for cell in row]
        for row in ws.iter_rows()
    ]

    validate_workbook(wb)

    final_values = [
        [cell.value for cell in row]
        for row in ws.iter_rows()
    ]

    assert final_values == original_values
