"""Lectura de plantillas Excel: detecta encabezados y extrae sus comentarios.

No asume nombres de columna fijos ni una estructura particular; solo
asume que la fila 1 de cada hoja de datos contiene los encabezados
(esto se cumple en las 5 plantillas de extensión inspeccionadas).
Las hojas de control (ej. "INFO") se excluyen por convención de nombre.
"""

from __future__ import annotations

from dataclasses import dataclass

from openpyxl.cell.cell import Cell
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

CONTROL_SHEET_NAMES = {"INFO"}
HEADER_ROW = 1


@dataclass
class HeaderCell:
    sheet_name: str
    column_name: str
    column_letter: str
    comment_text: str | None
    cell: Cell


def is_data_sheet(sheet_name: str) -> bool:
    return sheet_name.upper() not in CONTROL_SHEET_NAMES and not sheet_name.startswith("_")


def iter_data_sheets(workbook: Workbook) -> list[Worksheet]:
    return [workbook[name] for name in workbook.sheetnames if is_data_sheet(name)]


def read_headers(worksheet: Worksheet) -> list[HeaderCell]:
    """Lee los encabezados (fila 1) de una hoja, con su comentario asociado."""
    headers: list[HeaderCell] = []
    for cell in next(worksheet.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW)):
        if cell.value is None:
            continue
        comment_text = cell.comment.text if cell.comment else None
        headers.append(
            HeaderCell(
                sheet_name=worksheet.title,
                column_name=str(cell.value).strip(),
                column_letter=cell.column_letter,
                comment_text=comment_text,
                cell=cell,
            )
        )
    return headers
