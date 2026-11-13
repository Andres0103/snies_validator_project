
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
