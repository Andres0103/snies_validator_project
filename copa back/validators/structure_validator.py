"""Validaciones estructurales de los encabezados de hojas SNIES.

Este módulo comprueba condiciones que pueden detectarse directamente en la
fila de encabezados, sin depender de las reglas particulares de una plantilla:

1. Encabezados duplicados, ignorando mayúsculas/minúsculas y diferencias de
   espacios externos o repetidos.
2. Columnas que contienen datos, pero cuyo encabezado está vacío.

No comprueba si una columna es obligatoria ni si está permitida en una hoja.
Esas responsabilidades pertenecen al perfil estructural de cada plantilla.
"""

from __future__ import annotations

from collections import defaultdict

from openpyxl.worksheet.worksheet import Worksheet


HEADER_ROW = 1
EMPTY_HEADER_MARKER = "__ENCABEZADO_VACIO__"


def _has_value(value: object) -> bool:
    """Indica si una celda contiene un valor significativo.

    Los valores numéricos cero y los booleanos se consideran datos válidos.
    Las cadenas vacías o compuestas únicamente por espacios se consideran
    vacías. No se interpreta ni evalúa el contenido de fórmulas.
    """
    return value is not None and not (
        isinstance(value, str) and not value.strip()
    )


def normalize_header(value: object) -> str:
    """Normaliza un encabezado para detectar duplicados.

    Convierte el contenido a texto, elimina espacios externos, reduce
    secuencias de espacios internos a uno y unifica mayúsculas. No elimina
    tildes ni signos, porque hacerlo podría equiparar nombres de columnas
    que realmente son diferentes.
    """
    if not _has_value(value):
        return ""

    return " ".join(str(value).strip().upper().split())


def validate_sheet_headers(worksheet: Worksheet) -> list[dict]:
    """Detecta encabezados duplicados y columnas de datos sin encabezado.

    Cada incidencia conserva el contrato utilizado por el orquestador:
    ``row``, ``column_name``, ``value``, ``message`` y ``severity``.

    Se recorre el rango utilizado una sola vez para identificar las columnas
    con datos. Esto evita volver a recorrer todas las filas por cada encabezado
    vacío, como ocurría en la implementación anterior.
    """
    issues: list[dict] = []

    max_row = worksheet.max_row
    max_column = worksheet.max_column

    # Una hoja realmente vacía no tiene problemas de encabezados que reportar.
    if max_row < HEADER_ROW or max_column == 0:
        return issues

    # Registrar qué columnas contienen al menos un valor significativo.
    # También se obtiene la última columna utilizada para limitar el análisis.
    used_columns: set[int] = set()

    for row in worksheet.iter_rows(
        min_row=HEADER_ROW,
        max_row=max_row,
        min_col=1,
        max_col=max_column,
    ):
        for cell in row:
            if _has_value(cell.value):
                used_columns.add(cell.column)

    if not used_columns:
        return issues

    last_used_column = max(used_columns)

    # ---------------------------------------------------------
    # 1. Detectar columnas con datos debajo y encabezado vacío.
    # ---------------------------------------------------------

    for column_index in range(1, last_used_column + 1):
        header_cell = worksheet.cell(
            row=HEADER_ROW,
            column=column_index,
        )

        if _has_value(header_cell.value):
            continue

        # Una columna vacía en la fila de encabezados solo es un error si
        # tiene información en alguna fila de datos.
        has_data_below = any(
            _has_value(worksheet.cell(row=row_index, column=column_index).value)
            for row_index in range(HEADER_ROW + 1, max_row + 1)
        )

        if has_data_below:
            issues.append({
                "row": HEADER_ROW,
                "column_name": EMPTY_HEADER_MARKER,
                "value": None,
                "message": (
                    f"La columna {header_cell.column_letter} contiene datos, "
                    "pero tiene el encabezado vacío en la fila 1."
                ),
                "severity": "error",
            })

    # ---------------------------------------------------------
    # 2. Detectar encabezados duplicados.
    # ---------------------------------------------------------

    header_positions: dict[str, list[str]] = defaultdict(list)

    for column_index in range(1, last_used_column + 1):
        header_cell = worksheet.cell(
            row=HEADER_ROW,
            column=column_index,
        )

        normalized = normalize_header(header_cell.value)

        if normalized:
            header_positions[normalized].append(header_cell.column_letter)

    for normalized, positions in header_positions.items():
        if len(positions) > 1:
            issues.append({
                "row": HEADER_ROW,
                "column_name": normalized,
                "value": normalized,
                "message": (
                    f"El encabezado '{normalized}' está duplicado "
                    f"en las columnas {', '.join(positions)}."
                ),
                "severity": "error",
            })

    return issues
