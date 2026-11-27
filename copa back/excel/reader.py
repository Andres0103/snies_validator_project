
"""
Lectura de plantillas Excel.

Responsabilidades:
    - Identificar las hojas que contienen datos.
    - Excluir las hojas de control y auxiliares.
    - Leer los encabezados de las hojas de datos.
    - Extraer los comentarios asociados a los encabezados.

El módulo no valida reglas de negocio ni interpreta el contenido
de los comentarios. Esa responsabilidad corresponde a otros
componentes del motor.

Convención actual:
    - La primera fila contiene los encabezados.
    - Las hojas de control se identifican por su nombre.
    - Las hojas auxiliares comienzan por "_".
"""

from __future__ import annotations

from dataclasses import dataclass

from openpyxl.cell.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook.workbook import Workbook


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Nombres de las hojas que no contienen información de datos.
#
# Se comparan sin distinguir mayúsculas y minúsculas
# y eliminando espacios al principio y al final.
CONTROL_SHEET_NAMES = {
    "INFO",
}

# Fila donde se encuentran los encabezados.
HEADER_ROW = 1


# ============================================================
# MODELO DE ENCABEZADO
# ============================================================

@dataclass
class HeaderCell:
    """
    Representa un encabezado encontrado en una hoja Excel.

    Attributes:
        sheet_name:
            Nombre de la hoja donde se encuentra.

        column_name:
            Nombre del campo obtenido de la celda.

        column_letter:
            Letra de la columna en Excel.

        comment_text:
            Texto del comentario asociado al encabezado.
            Puede ser None si no existe comentario.

        cell:
            Referencia a la celda original de openpyxl.
            Permite acceder a sus propiedades sin modificarla.
    """

    sheet_name: str
    column_name: str
    column_letter: str
    comment_text: str | None
    cell: Cell


# ============================================================
# IDENTIFICACIÓN DE HOJAS
# ============================================================

def is_data_sheet(sheet_name: str) -> bool:
    """
    Determina si una hoja debe procesarse como hoja de datos.

    Se excluyen:
        - Hojas de control declaradas en CONTROL_SHEET_NAMES.
        - Hojas auxiliares cuyo nombre comienza por "_".

    La comparación de nombres ignora mayúsculas y espacios
    exteriores.

    Args:
        sheet_name:
            Nombre de la hoja de Excel.

    Returns:
        True si es una hoja de datos.
        False si es una hoja de control o auxiliar.
    """

    normalized_name = sheet_name.strip().upper()

    # Excluir nombres vacíos.
    if not normalized_name:
        return False

    # Excluir hojas de control.
    if normalized_name in CONTROL_SHEET_NAMES:
        return False

    # Excluir hojas auxiliares.
    if normalized_name.startswith("_"):
        return False

    return True


def iter_data_sheets(
    workbook: Workbook,
) -> list[Worksheet]:
    """
    Obtiene las hojas que contienen datos.

    Recorre las hojas del workbook respetando su orden original.

    Args:
        workbook:
            Libro de Excel cargado con openpyxl.

    Returns:
        Lista de hojas que deben procesarse.
    """

    return [
        workbook[sheet_name]
        for sheet_name in workbook.sheetnames
        if is_data_sheet(sheet_name)
    ]


# ============================================================
# LECTURA DE ENCABEZADOS
# ============================================================

def read_headers(
    worksheet: Worksheet,
) -> list[HeaderCell]:
    """
    Lee los encabezados de la primera fila de una hoja.

    Para cada celda con contenido distinto de None, obtiene:
        - Nombre de la columna.
        - Letra de la columna.
        - Comentario asociado, si existe.
        - Referencia a la celda original.

    IMPORTANTE:
    Las celdas cuyo valor es None se omiten.

    Las celdas cuyo valor es una cadena vacía o contiene
    solamente espacios se conservan como encabezados vacíos.
    Esto permite que otros módulos detecten encabezados
    incorrectos sin perder su posición.

    Args:
        worksheet:
            Hoja de Excel que se desea leer.

    Returns:
        Lista de objetos HeaderCell.
    """

    headers: list[HeaderCell] = []

    # Obtener las celdas de la fila de encabezados.
    # La iteración también funciona cuando la hoja está vacía.
    for cell in worksheet.iter_rows(
        min_row=HEADER_ROW,
        max_row=HEADER_ROW,
    ):
        for header_cell in cell:

            # Una celda realmente vacía no genera encabezado.
            # Se conserva la cadena vacía para que el validador
            # estructural pueda identificarla.
            if header_cell.value is None:
                continue

            # Convertir el encabezado a texto y eliminar
            # espacios exteriores.
            column_name = str(header_cell.value).strip()

            # Extraer el comentario sin modificar su contenido.
            comment_text = (
                header_cell.comment.text
                if header_cell.comment is not None
                else None
            )

            headers.append(
                HeaderCell(
                    sheet_name=worksheet.title,
                    column_name=column_name,
                    column_letter=header_cell.column_letter,
                    comment_text=comment_text,
                    cell=header_cell,
                )
            )

    return headers
