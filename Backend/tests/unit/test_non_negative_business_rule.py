from openpyxl import Workbook

from validators.post_hoc_validator import validate_workbook


def test_negative_values_are_rejected():
    wb = Workbook()

    # Hoja principal: permite identificar la plantilla.
    ws_principal = wb.active
    ws_principal.title = "EVENTO_CULTURAL"

    ws_principal.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_EVENTO",
    ])

    ws_principal.append([
        2026,
        1,
        "U001",
        "E001",
    ])

    # Hoja secundaria donde se prueban los valores negativos.
    ws = wb.create_sheet("EVENTO_CULT_BENEFICIARIOS")

    ws.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_EVENTO",
        "ID_TIPO_BENEFICIARIO",
        "TOTAL_ASISTENTES",
        "VALOR_ENTRADA",
    ])

    ws.append([
        2026,
        1,
        "U001",
        "E001",
        1,
        -5,
        -100,
    ])

    results = validate_workbook(wb)

    # Buscar únicamente los errores de la hoja que estamos probando.
    issues = [
        issue
        for result in results
        if result.sheet_name == "EVENTO_CULT_BENEFICIARIOS"
        for issue in result.issues
    ]

    assert len(issues) == 2
    assert any(
        issue.column_name == "TOTAL_ASISTENTES"
        and issue.value == -5
        and issue.message == "El valor debe ser mayor o igual a 0."
        for issue in issues
    )
    assert any(
        issue.column_name == "VALOR_ENTRADA"
        and issue.value == -100
        and issue.message == "El valor debe ser mayor o igual a 0."
        for issue in issues
    )


def test_zero_values_are_accepted():
    wb = Workbook()
    ws = wb.active
    ws.title = "EVENTO_CULT_BENEFICIARIOS"

    ws.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_EVENTO",
        "ID_TIPO_BENEFICIARIO",
        "TOTAL_ASISTENTES",
        "VALOR_ENTRADA",
    ])

    ws.append([
        2026,
        1,
        "U001",
        "E001",
        1,
        0,
        0,
    ])

    results = validate_workbook(wb)

    event_result = results[0]

    negative_issues = [
        issue
        for issue in event_result.issues
        if issue.column_name in {
            "TOTAL_ASISTENTES",
            "VALOR_ENTRADA",
        }
        and "no puede ser negativo" in issue.message.lower()
    ]

    assert negative_issues == []


def test_positive_values_are_accepted():
    wb = Workbook()
    ws = wb.active
    ws.title = "EVENTO_CULT_BENEFICIARIOS"

    ws.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_EVENTO",
        "ID_TIPO_BENEFICIARIO",
        "TOTAL_ASISTENTES",
        "VALOR_ENTRADA",
    ])

    ws.append([
        2026,
        1,
        "U001",
        "E001",
        1,
        100,
        25000,
    ])

    results = validate_workbook(wb)

    event_result = results[0]

    negative_issues = [
        issue
        for issue in event_result.issues
        if issue.column_name in {
            "TOTAL_ASISTENTES",
            "VALOR_ENTRADA",
        }
        and "no puede ser negativo" in issue.message.lower()
    ]

    assert negative_issues == []