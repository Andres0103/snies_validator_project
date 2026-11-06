
from openpyxl import Workbook
from openpyxl.comments import Comment

from validators.post_hoc_validator import validate_workbook


def add_headers(ws):
    headers = [
        "ID_FUENTE_NACIONAL",
        "VLR_FINANCIACION_NACIONAL",
        "ID_FUENTE_INTERNACIONAL",
        "VLR_FINANCIACION_INTERNACIONAL",
        "NOMBRE_INSTITUCION",
        "ID_PAIS_FINANCIADOR",
    ]

    comments = [
        "Opcional, numérico (2).",
        "Opcional, numérico (15).",
        "Opcional, numérico (2).",
        "Opcional, numérico (15).",
        "Opcional, alfanumérico (200).",
        "Opcional, numérico (3).",
    ]

    for col, (header, comment) in enumerate(
        zip(headers, comments), start=1
    ):
        cell = ws.cell(row=1, column=col, value=header)
        cell.comment = Comment(comment, "Prueba")


def test_post_hoc_integration():
    wb = Workbook()

    # Hoja donde sí deben aplicarse las condiciones.
    ws = wb.active
    ws.title = "CONSULTORIA"
    add_headers(ws)

    # Caso 1: fuente nacional informada, financiación vacía.
    ws.append([1, None, None, None, None, None])

    # Caso 2: sin fuente nacional ni financiación.
    ws.append([None, None, None, None, None, None])

    # Caso 3: fuente internacional informada.
    # Deben exigirse financiación, institución y país.
    ws.append([None, None, 1, None, None, None])

    # Caso 4: sin fuente internacional, pero con financiación > 0.
    # Deben exigirse institución y país.
    ws.append([None, None, None, 100, None, None])

    # Caso 5: financiación internacional igual a cero,
    # sin fuente internacional. No activa institución ni país.
    ws.append([None, None, None, 0, None, None])

    # Otra hoja: las reglas de CONSULTORIA no deben aplicarse.
    other = wb.create_sheet("OTRA_HOJA")
    add_headers(other)
    other.append([1, None, None, None, None, None])

    results = validate_workbook(wb)

    consultoria = next(
        result for result in results
        if result.sheet_name == "CONSULTORIA"
    )

    otra_hoja = next(
        result for result in results
        if result.sheet_name == "OTRA_HOJA"
    )

    # Convertir incidencias en tuplas fáciles de comparar.
    actual = {
        (issue.row, issue.column_name, issue.severity)
        for issue in consultoria.issues
    }

    expected = {
        (2, "VLR_FINANCIACION_NACIONAL", "error"),

        (4, "VLR_FINANCIACION_INTERNACIONAL", "error"),
        (4, "NOMBRE_INSTITUCION", "error"),
        (4, "ID_PAIS_FINANCIADOR", "error"),

        (5, "NOMBRE_INSTITUCION", "error"),
        (5, "ID_PAIS_FINANCIADOR", "error"),
    }

    assert actual == expected, (
        "\nLas incidencias encontradas no coinciden con las esperadas."
        f"\nEsperadas: {expected}"
        f"\nEncontradas: {actual}"
    )

    assert len(otra_hoja.issues) == 0, (
        "Las reglas condicionales de CONSULTORIA se aplicaron "
        "incorrectamente a otra hoja."
    )

    print("OK: reglas condicionales integradas en CONSULTORIA.")
    print("OK: se detectaron los seis errores esperados.")
    print("OK: las reglas no se aplicaron a OTRA_HOJA.")
    print("\nPrueba de integración superada.")


if __name__ == "__main__":
    test_post_hoc_integration()
