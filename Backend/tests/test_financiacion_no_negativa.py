
from openpyxl import Workbook
from openpyxl.comments import Comment

from validators.post_hoc_validator import validate_workbook


def crear_hoja_consultoria():

    workbook = Workbook()
    ws = workbook.active
    ws.title = "CONSULTORIA"

    encabezados = [
        "ID_FUENTE_NACIONAL",
        "VLR_FINANCIACION_NACIONAL",
        "ID_FUENTE_INTERNACIONAL",
        "VLR_FINANCIACION_INTERNACIONAL",
    ]

    comentarios = [
        "Opcional, numérico (2).",
        "Opcional, numérico (15).",
        "Opcional, numérico (2).",
        "Opcional, numérico (15).",
    ]

    for columna, (nombre, comentario) in enumerate(
        zip(encabezados, comentarios),
        start=1
    ):
        celda = ws.cell(
            row=1,
            column=columna,
            value=nombre
        )
        celda.comment = Comment(comentario, "Prueba")

    return workbook, ws


def test_financiaciones_negativas_generan_error():

    workbook, ws = crear_hoja_consultoria()

    # Financiación nacional negativa.
    ws.append([1, -100, None, None])

    # Financiación internacional negativa.
    ws.append([None, None, 1, -200])

    # Valores positivos: válidos.
    ws.append([1, 100, 1, 200])

    # Cero: válido, no es negativo.
    ws.append([1, 0, 1, 0])

    # Valores negativos sin fuente informada:
    # la regla de no negatividad también debe detectarlos.
    ws.append([None, -50, None, -75])

    resultados = validate_workbook(workbook)

    consultoria = next(
        resultado
        for resultado in resultados
        if resultado.sheet_name == "CONSULTORIA"
    )

    errores_financiacion = [
        issue
        for issue in consultoria.issues
        if issue.column_name in (
            "VLR_FINANCIACION_NACIONAL",
            "VLR_FINANCIACION_INTERNACIONAL",
        )
        and issue.message in (
            "El valor de financiación nacional no puede ser negativo.",
            "El valor de financiación internacional no puede ser negativo.",
        )
    ]

    encontrados = {
        (issue.row, issue.column_name)
        for issue in errores_financiacion
    }

    esperados = {
        (2, "VLR_FINANCIACION_NACIONAL"),
        (3, "VLR_FINANCIACION_INTERNACIONAL"),
        (6, "VLR_FINANCIACION_NACIONAL"),
        (6, "VLR_FINANCIACION_INTERNACIONAL"),
    }

    assert encontrados == esperados, (
        f"Errores esperados: {esperados}. "
        f"Errores encontrados: {encontrados}"
    )


def test_financiaciones_cero_y_positivas_son_validas():

    workbook, ws = crear_hoja_consultoria()

    ws.append([1, 0, 1, 0])
    ws.append([1, 100, 1, 200])

    resultados = validate_workbook(workbook)

    consultoria = next(
        resultado
        for resultado in resultados
        if resultado.sheet_name == "CONSULTORIA"
    )

    errores_financiacion = [
        issue
        for issue in consultoria.issues
        if issue.column_name in (
            "VLR_FINANCIACION_NACIONAL",
            "VLR_FINANCIACION_INTERNACIONAL",
        )
        and "no puede ser negativo" in issue.message
    ]

    assert errores_financiacion == []
