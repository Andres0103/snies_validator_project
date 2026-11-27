
from openpyxl import Workbook

from validators.post_hoc_validator import validate_workbook


def add_headers(ws):
    headers = [
        "AÑO",
        "SEMESTRE",
        "CODIGO_CONSULTORIA",
        "DESCRIPCION_CONSULTORIA",
        "ID_CINE_CAMPO_DETALLADO",
        "NOMBRE_ENTIDAD",
        "ID_SECTOR_CONSULTORIA",
        "VALOR",
        "FECHA_INICIO",
        "FECHA_FINAL",
        "ID_FUENTE_NACIONAL",
        "VLR_FINANCIACION_NACIONAL",
        "NOMBRE_INSTITUCION",
        "ID_PAIS_FINANCIADOR",
        "ID_FUENTE_INTERNACIONAL",
        "VLR_FINANCIACION_INTERNACIONAL",
    ]

    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)



def test_post_hoc_integration():
    wb = Workbook()

    # Hoja principal de CONSULTORIA.
    ws = wb.active
    ws.title = "CONSULTORIA"
    add_headers(ws)

    # Función auxiliar para agregar registros de prueba.
    def append_consultoria(
        fuente_nacional=None,
        financiacion_nacional=None,
        fuente_internacional=None,
        financiacion_internacional=None,
        institucion=None,
        pais=None,
    ):
        ws.append([
            2026,                  # AÑO
            1,                     # SEMESTRE
            f"C{ws.max_row}",      # CODIGO_CONSULTORIA
            "Consultoría de prueba",
            613,                   # ID_CINE_CAMPO_DETALLADO
            "Universidad de prueba",
            1,                     # ID_SECTOR_CONSULTORIA
            1000,                  # VALOR
            "2026-01-15",          # FECHA_INICIO
            None,                  # FECHA_FINAL
            fuente_nacional,
            financiacion_nacional,
            institucion,
            pais,
            fuente_internacional,
            financiacion_internacional,
        ])

    # Caso 1: fuente nacional informada, financiación vacía.
    append_consultoria(fuente_nacional=1)

    # Caso 2: sin fuente nacional ni financiación.
    append_consultoria()

    # Caso 3: fuente internacional informada.
    # Al no informar financiación, institución ni país,
    # deben generarse las incidencias correspondientes.
    append_consultoria(fuente_internacional=1)

    # Caso 4: sin fuente internacional, pero con financiación > 0.
    # No se exige institución ni país porque no hay fuente internacional.
    append_consultoria(financiacion_internacional=100)

    # Caso 5: sin fuente internacional y financiación igual a cero.
    # Los campos relacionados pueden permanecer vacíos.
    append_consultoria(financiacion_internacional=0)

    # Hoja secundaria obligatoria del perfil.
    recurso_humano = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    recurso_humano.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_CONSULTORIA",
        "ID_TIPO_DOCUMENTO",
        "NUM_DOCUMENTO",
        "ID_MAXIMO_NIVEL_ESTUDIO",
    ])

    # Hoja inesperada para comprobar la validación de estructura.
    other = wb.create_sheet("OTRA_HOJA")
    other.append(["CAMPO"])
    other.append(["valor"])

    results = validate_workbook(wb)

    consultoria = next(
        result for result in results
        if result.sheet_name == "CONSULTORIA"
    )

    estructura = next(
        result for result in results
        if result.sheet_name == "ESTRUCTURA_LIBRO"
    )

    # Convertir incidencias en tuplas fáciles de comparar.
    actual = {
        (issue.row, issue.column_name, issue.severity)
        for issue in consultoria.issues
    }

    # Solo esperamos incidencias derivadas de las reglas aplicables.
    expected = {
        # Caso 1: fuente nacional informada sin financiación.
        (2, "VLR_FINANCIACION_NACIONAL", "error"),

        # Caso 3: fuente internacional informada sin financiación,
        # institución ni país.
        (4, "VLR_FINANCIACION_INTERNACIONAL", "error"),
        (4, "NOMBRE_INSTITUCION", "error"),
        (4, "ID_PAIS_FINANCIADOR", "error"),
    }

    assert actual == expected, (
        "\nLas incidencias encontradas no coinciden con las esperadas."
        f"\nEsperadas: {expected}"
        f"\nEncontradas: {actual}"
    )

    # Comprobar que la hoja inesperada fue reportada.
    assert any(
        issue.severity == "error"
        for issue in estructura.issues
    )


if __name__ == "__main__":
    test_post_hoc_integration()

def test_empty_header_does_not_block_cross_row_consistency():
    wb = Workbook()

    ws = wb.active
    ws.title = "CONSULTORIA"

    add_headers(ws)

    # Agregar una columna con encabezado vacío, pero con datos.
    ws.cell(row=1, column=17, value=None)
    ws.cell(row=2, column=17, value="dato sin encabezado")
    ws.cell(row=3, column=17, value="otro dato")

    # Dos registros con el mismo código, pero con inconsistencias.
    ws.append([
        2026,
        1,
        "TEST-001",
        "Descripción de consultoría A",
        613,
        "Universidad de prueba",
        1,
        1000,
        "2026-01-15",
        "2026-02-15",
        None,
        None,
        None,
        None,
        None,
        None,
    ])

    ws.append([
        2026,
        2,
        "TEST-001",
        "Descripción de consultoría B",
        614,
        "Universidad de prueba",
        1,
        1000,
        "2026-01-15",
        "2026-02-15",
        None,
        None,
        None,
        None,
        None,
        None,
    ])

    # Crear la hoja secundaria requerida por la plantilla.
    rh = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    rh.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_CONSULTORIA",
        "ID_TIPO_DOCUMENTO",
        "NUM_DOCUMENTO",
        "ID_MAXIMO_NIVEL_ESTUDIO",
    ])

    results = validate_workbook(wb)

    consultoria = next(
        result for result in results
        if result.sheet_name == "CONSULTORIA"
    )

    # Buscar las inconsistencias entre los registros con código TEST-001.
    consistency_issues = [
        issue for issue in consultoria.issues
        if "TEST-001" in str(issue.value)
        or "consistencia" in issue.message.lower()
        or "mismo código" in issue.message.lower()
        or "mismo codigo" in issue.message.lower()
    ]

    # La hoja debe reportar el encabezado vacío.
    empty_header_issues = [
        issue for issue in consultoria.issues
        if issue.column_name == "__ENCABEZADO_VACIO__"
    ]

    assert empty_header_issues, (
        "No se reportó el encabezado vacío con datos."
    )

    assert consistency_issues, (
        "No se detectaron las inconsistencias entre registros "
        "con el mismo CODIGO_CONSULTORIA."
    )