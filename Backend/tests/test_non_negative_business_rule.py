from openpyxl import Workbook

from validators.post_hoc_validator import validate_workbook


def test_negative_values_are_rejected():
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
        -5,
        -100,
    ])

    results = validate_workbook(wb)

    assert len(results) == 1

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

    assert len(negative_issues) == 2


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