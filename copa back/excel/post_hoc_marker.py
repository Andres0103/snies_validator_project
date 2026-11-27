
"""Marca visualmente los errores y advertencias encontrados en un Excel."""

from __future__ import annotations

from collections import defaultdict

from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from openpyxl.workbook.workbook import Workbook
from openpyxl.cell.cell import MergedCell

from excel.reader import read_headers
from validators.post_hoc_validator import SheetValidationResult


ERROR_FILL = PatternFill(
    fill_type="solid",
    fgColor="FCE4E4",
)

WARNING_FILL = PatternFill(
    fill_type="solid",
    fgColor="FFF2CC",
)

MARKER_COMMENT = "VALIDACIÓN SNIES"


def mark_workbook(
    workbook: Workbook,
    results: list[SheetValidationResult],
) -> Workbook:
    """Marca las celdas que presentan errores o advertencias.

    Los errores tienen prioridad sobre las advertencias cuando
    una misma celda presenta ambas incidencias.
    """
    
        # --------------------------------------------------------
    # LIMPIAR MARCAS DE VALIDACIONES ANTERIORES
    # --------------------------------------------------------

    generated_fill_colors = {
        "FCE4E4",  # Error
        "FFF2CC",  # Advertencia
    }

    for ws in workbook.worksheets:

        for row in ws.iter_rows():

            for cell in row:

                # Limpiar únicamente los colores que utiliza
                # este marcador para errores y advertencias.
                if cell.fill.fill_type == "solid":

                    color = cell.fill.fgColor

                    if color.type == "rgb" and color.rgb:

                        rgb = color.rgb[-6:].upper()

                        if rgb in generated_fill_colors:
                            cell.fill = PatternFill(fill_type=None)

                # Retirar exclusivamente la sección generada
                # por el validador de comentarios existentes.
                if cell.comment and MARKER_COMMENT in cell.comment.text:

                    previous_text = cell.comment.text.split(
                        MARKER_COMMENT,
                        1,
                    )[0].strip()

                    if previous_text:

                        cell.comment = Comment(
                            previous_text,
                            cell.comment.author or "Usuario",
                        )

                    else:

                        cell.comment = None

    for sheet_result in results:

        if sheet_result.sheet_name not in workbook.sheetnames:
            continue

        ws = workbook[sheet_result.sheet_name]

        # Relacionar el nombre de cada columna con su letra en Excel.
        headers = read_headers(ws)

        column_letters = {
            header.column_name: header.column_letter
            for header in headers
        }

        # Agrupar incidencias por celda para no sobrescribir
        # mensajes cuando una celda tenga varias validaciones.
        issues_by_cell = defaultdict(list)

        for issue in sheet_result.issues:

            column_letter = column_letters.get(issue.column_name)

            if column_letter is None:
                continue

            if issue.row < 1 or issue.row > ws.max_row:
                continue

            coordinate = f"{column_letter}{issue.row}"
            issues_by_cell[coordinate].append(issue)

        # Aplicar formato y comentarios.
        for coordinate, issues in issues_by_cell.items():

            cell = ws[coordinate]

            # Las celdas secundarias de rangos combinados
            # no permiten asignar comentarios.
            if isinstance(cell, MergedCell):
                continue

            has_error = any(
                issue.severity.lower() == "error"
                for issue in issues
            )

            # Si existe al menos un error, el rojo tiene prioridad.
            cell.fill = ERROR_FILL if has_error else WARNING_FILL

            messages = []

            for issue in issues:

                severity = (
                    "ERROR"
                    if issue.severity.lower() == "error"
                    else "ADVERTENCIA"
                )

                messages.append(
                    f"{severity}: {issue.message}"
                )

            generated_comment = (
                f"{MARKER_COMMENT}\n"
                + "\n".join(messages)
            )

            # Preservar comentarios anteriores que no hayan sido
            # generados por este marcador.
            previous_comment = ""

            if cell.comment and cell.comment.text:

                previous_comment = "\n".join(
                    line
                    for line in cell.comment.text.splitlines()
                    if MARKER_COMMENT not in line
                ).strip()

            if previous_comment:
                comment_text = (
                    f"{previous_comment}\n\n"
                    f"{generated_comment}"
                )
            else:
                comment_text = generated_comment

            cell.comment = Comment(
                comment_text,
                "Validador SNIES",
            )

    return workbook
