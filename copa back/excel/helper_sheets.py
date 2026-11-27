
"""Construye la hoja auxiliar oculta que respalda las listas desplegables.

Responsabilidades:
1. Crear o reutilizar la hoja auxiliar.
2. Limpiar los catÃ¡logos generados anteriormente.
3. Escribir los cÃ³digos y sus descripciones.
4. Crear o actualizar los nombres definidos de Excel.
5. Evitar que se acumulen listas obsoletas entre generaciones.

La hoja auxiliar utiliza dos columnas por catÃ¡logo:
- Primera columna: cÃ³digo que aparecerÃ¡ en el desplegable.
- Segunda columna: descripciÃ³n del cÃ³digo.

Los nombres definidos son administrados por este mÃ³dulo y utilizan
el prefijo reservado 'Lista_'.
"""

from __future__ import annotations

import re

from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.worksheet import Worksheet

from rules.general_model import ValidationRule


HELPER_SHEET_NAME = "_Listas_Auxiliares"

# Los nombres que comienzan con este prefijo pertenecen
# a las listas desplegables administradas por este mÃ³dulo.
DEFINED_NAME_PREFIX = "Lista_"

_INVALID_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _safe_defined_name(
    column_name: str,
    used_names: set[str],
) -> str:
    """
    Genera un nombre vÃ¡lido y Ãºnico para un rango de Excel.

    Excel no permite espacios ni caracteres especiales en los
    nombres definidos. TambiÃ©n debemos evitar nombres duplicados
    despuÃ©s de normalizar los caracteres.

    Ejemplo:
        CODIGO_SERVICIO -> Lista_CODIGO_SERVICIO
        AÃ‘O             -> Lista_A_O
    """

    cleaned = _INVALID_NAME_CHARS.sub(
        "_",
        column_name.strip(),
    )

    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"

    base_name = (
        f"{DEFINED_NAME_PREFIX}{cleaned}"
    )

    # Excel limita los nombres definidos a 255 caracteres.
    base_name = base_name[:255]

    candidate = base_name
    counter = 2

    # Los nombres definidos no distinguen mayÃºsculas
    # de minÃºsculas para efectos de unicidad.
    while candidate.upper() in used_names:

        suffix = f"_{counter}"

        candidate = (
            base_name[:255 - len(suffix)]
            + suffix
        )

        counter += 1

    used_names.add(candidate.upper())

    return candidate


def _clear_helper_sheet(helper_ws: Worksheet) -> None:
    """
    Elimina el contenido anterior de la hoja auxiliar.

    Se eliminan filas y columnas para evitar que queden cÃ³digos
    o descripciones de catÃ¡logos que ya no existen.
    """

    if helper_ws.max_row > 0:
        helper_ws.delete_rows(
            1,
            helper_ws.max_row,
        )

    if helper_ws.max_column > 0:
        helper_ws.delete_cols(
            1,
            helper_ws.max_column,
        )

    # La hoja auxiliar siempre debe permanecer oculta.
    helper_ws.sheet_state = "hidden"


def _remove_previous_defined_names(workbook) -> None:
    """
    Elimina los nombres definidos generados por este mÃ³dulo.

    No elimina nombres definidos ajenos a las listas auxiliares.
    """

    names_to_remove = [
        name
        for name in workbook.defined_names.keys()
        if name.startswith(DEFINED_NAME_PREFIX)
    ]

    # Compatibilidad con nombres generados por versiones
    # anteriores de este mÃ³dulo.
    for name in names_to_remove:
        workbook.defined_names.pop(
            name,
            None,
        )


def _validate_rules(
    rules_with_lists: list[ValidationRule],
) -> None:
    """
    Comprueba que no existan catÃ¡logos diferentes para una
    misma columna.

    La implementaciÃ³n actual de writer.py identifica las listas
    por nombre de columna. Por tanto, no puede representar dos
    catÃ¡logos diferentes para columnas con el mismo nombre.

    Esta comprobaciÃ³n evita reutilizar un catÃ¡logo incorrecto.
    """

    catalogs_by_column: dict[str, list[tuple[str, str]]] = {}

    for rule in rules_with_lists:

        if not rule.allowed_values:
            continue

        current_catalog = [
            (
                str(value.code),
                str(value.label),
            )
            for value in rule.allowed_values
        ]

        existing_catalog = catalogs_by_column.get(
            rule.column_name
        )

        if existing_catalog is None:

            catalogs_by_column[
                rule.column_name
            ] = current_catalog

            continue

        if existing_catalog != current_catalog:
            raise ValueError(
                f"La columna '{rule.column_name}' tiene "
                "catÃ¡logos diferentes. No es posible generar "
                "un Ãºnico rango definido para esa columna."
            )


def build_helper_sheet(
    workbook,
    rules_with_lists: list[ValidationRule],
) -> dict[str, str]:
    """
    Construye la hoja auxiliar y los rangos definidos.

    ParÃ¡metros:
        workbook:
            Libro Excel que recibirÃ¡ la hoja auxiliar.

        rules_with_lists:
            Reglas cuyas columnas tienen valores permitidos.

    Retorna:
        Diccionario con esta estructura:

            {
                "CODIGO_SERVICIO": "Lista_CODIGO_SERVICIO",
                "TIPO_DOCUMENTO": "Lista_TIPO_DOCUMENTO"
            }

    El diccionario es utilizado posteriormente por
    build_list_validation() para construir las listas desplegables.
    """

    # --------------------------------------------------------
    # 1. Validar los catÃ¡logos recibidos.
    # --------------------------------------------------------

    _validate_rules(rules_with_lists)

    # --------------------------------------------------------
    # 2. Obtener o crear la hoja auxiliar.
    # --------------------------------------------------------

    if HELPER_SHEET_NAME in workbook.sheetnames:

        helper_ws: Worksheet = workbook[
            HELPER_SHEET_NAME
        ]

    else:

        helper_ws = workbook.create_sheet(
            HELPER_SHEET_NAME
        )

    # --------------------------------------------------------
    # 3. Limpiar los datos generados anteriormente.
    # --------------------------------------------------------

    _clear_helper_sheet(helper_ws)

    # Eliminar los nombres definidos anteriores para que
    # las referencias se reconstruyan con los rangos actuales.
    _remove_previous_defined_names(workbook)

    defined_names: dict[str, str] = {}

    used_names: set[str] = set()

    # --------------------------------------------------------
    # 4. Reconstruir los catÃ¡logos.
    # --------------------------------------------------------

    next_column = 1

    for rule in rules_with_lists:

        if not rule.allowed_values:
            continue

        column_letter = get_column_letter(
            next_column
        )

        description_letter = get_column_letter(
            next_column + 1
        )

        # Encabezados de la hoja auxiliar.
        helper_ws.cell(
            row=1,
            column=next_column,
            value=f"{rule.column_name} (cÃ³digo)",
        )

        helper_ws.cell(
            row=1,
            column=next_column + 1,
            value="DescripciÃ³n",
        )

        # Escribir los valores del catÃ¡logo.
        for row_number, value in enumerate(
            rule.allowed_values,
            start=2,
        ):

            helper_ws.cell(
                row=row_number,
                column=next_column,
                value=value.code,
            )

            helper_ws.cell(
                row=row_number,
                column=next_column + 1,
                value=value.label,
            )

        # Ãšltima fila ocupada por el catÃ¡logo.
        last_row = (
            len(rule.allowed_values) + 1
        )

        # Generar un nombre definido vÃ¡lido y Ãºnico.
        defined_name_str = _safe_defined_name(
            rule.column_name,
            used_names,
        )

        # Construir la referencia absoluta al rango de cÃ³digos.
        reference = (
            f"'{HELPER_SHEET_NAME}'!"
            f"${column_letter}$2:"
            f"${column_letter}${last_row}"
        )

        # Registrar el nombre definido en el workbook.
        defined_name = DefinedName(
            defined_name_str,
            attr_text=reference,
        )

        workbook.defined_names.add(
            defined_name
        )

        # Mantener la interfaz actual de writer.py:
        # {nombre_columna: nombre_definido}
        defined_names[
            rule.column_name
        ] = defined_name_str

        # Cada catÃ¡logo utiliza dos columnas:
        # una para cÃ³digos y otra para descripciones.
        next_column += 2

    # --------------------------------------------------------
    # 5. Mantener la hoja auxiliar oculta.
    # --------------------------------------------------------

    helper_ws.sheet_state = "hidden"

    return defined_names

