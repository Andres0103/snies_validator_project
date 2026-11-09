
"""Validaciones estructurales de encabezados de hojas SNIES."""

from __future__ import annotations

from collections import defaultdict
from openpyxl.worksheet.worksheet import Worksheet


def normalize_header(value: object) -> str:
    """
    Normaliza un encabezado para comparar duplicados.

    Elimina espacios externos, unifica espacios internos
    y no diferencia mayúsculas de minúsculas.
    """
    if value is None:
        return ""

    return " ".join(str(value).strip().upper().split())


def validate_sheet_headers(
    worksheet: Worksheet,
) -> list[dict]:
    """
    Detecta problemas estructurales en la fila de encabezados.

    Por ahora comprueba:
    - Encabezados duplicados.
    - Encabezados vacíos entre columnas utilizadas.

    No determina todavía qué columnas son obligatorias
    ni cuáles están autorizadas para cada hoja.
    """

    issues = []

    header_row = 1

    # Identificar la última columna que contiene información
    # en cualquier fila de la hoja.
    last_used_column = 0

    for row in worksheet.iter_rows():

        for cell in row:

            if cell.value is not None and str(cell.value).strip():
                last_used_column = max(
                    last_used_column,
                    cell.column,
                )

    if last_used_column == 0:
        return issues

    # ---------------------------------------------------------
    # 1. Detectar encabezados vacíos entre columnas utilizadas.
    # ---------------------------------------------------------

    for column_index in range(1, last_used_column + 1):

        cell = worksheet.cell(
            row=header_row,
            column=column_index,
        )

        if cell.value is None or not str(cell.value).strip():

            # Solo se reporta si existe información debajo
            # de una columna cuyo encabezado está vacío.
            has_data_below = any(
                worksheet.cell(
                    row=row_index,
                    column=column_index,
                ).value is not None
                and str(
                    worksheet.cell(
                        row=row_index,
                        column=column_index,
                    ).value
                ).strip()
                for row_index in range(2, worksheet.max_row + 1)
            )

            if has_data_below:

                issues.append({
                    "row": header_row,
                    "column_name": "__ENCABEZADO_VACIO__",
                    "value": None,
                    "message": (
                        "La columna "
                        f"{cell.column_letter} contiene datos, "
                        "pero no tiene encabezado en la fila 1."
                    ),
                    "severity": "error",
                })

    # ---------------------------------------------------------
    # 2. Detectar encabezados duplicados.
    # ---------------------------------------------------------

    header_positions = defaultdict(list)

    for column_index in range(1, last_used_column + 1):

        cell = worksheet.cell(
            row=header_row,
            column=column_index,
        )

        normalized = normalize_header(cell.value)

        if normalized:
            header_positions[normalized].append(
                cell.column_letter
            )

    for normalized, positions in header_positions.items():

        if len(positions) > 1:

            issues.append({
                "row": header_row,
                "column_name": normalized,
                "value": normalized,
                "message": (
                    f"El encabezado '{normalized}' está duplicado "
                    f"en las columnas {', '.join(positions)}."
                ),
                "severity": "error",
            })

    return issues
