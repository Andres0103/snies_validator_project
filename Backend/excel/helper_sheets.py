"""Crea la hoja auxiliar oculta que respalda los desplegables de Excel.

Diseño: se usa SIEMPRE un rango con nombre en una hoja oculta (nunca una
lista inline en la fórmula del DataValidation), incluso para listas
cortas. Esto evita el límite práctico de ~255 caracteres de las listas
inline y mantiene un comportamiento uniforme sin casos especiales.

El desplegable solo ofrece el CÓDIGO (no "código + descripción"), porque
el propio flujo de cargue al SNIES exige el código solo — el error más
común detectado en el validador post-hoc de Andrés fue precisamente
usuarios escribiendo "1201 Medellín" en vez de "1201". La descripción de
cada código queda visible en la hoja auxiliar (por si el usuario necesita
consultarla) y, cuando cabe, también como mensaje de entrada de la celda.
"""

from __future__ import annotations

import re

from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.worksheet import Worksheet

from backend.rules.general_model import ValidationRule

HELPER_SHEET_NAME = "_Listas_Auxiliares"
_INVALID_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _safe_defined_name(column_name: str) -> str:
    """Genera un nombre de rango válido para Excel a partir del nombre de columna."""
    cleaned = _INVALID_NAME_CHARS.sub("_", column_name.strip())
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return f"Lista_{cleaned}"[:255]


def build_helper_sheet(workbook, rules_with_lists: list[ValidationRule]) -> dict[str, str]:
    """Crea (o reutiliza) la hoja auxiliar oculta y un rango con nombre por columna.

    Devuelve un dict {column_name: defined_name} para que el constructor de
    validaciones pueda referenciarlo en `formula1`.
    """
    if HELPER_SHEET_NAME in workbook.sheetnames:
        helper_ws: Worksheet = workbook[HELPER_SHEET_NAME]
    else:
        helper_ws = workbook.create_sheet(HELPER_SHEET_NAME)
        helper_ws.sheet_state = "hidden"

    defined_names: dict[str, str] = {}
    next_col = helper_ws.max_column + 1 if helper_ws.max_column and helper_ws.max_column > 0 else 1

    for rule in rules_with_lists:
        if not rule.allowed_values:
            continue

        col_letter = get_column_letter(next_col)
        helper_ws.cell(row=1, column=next_col, value=f"{rule.column_name} (código)")
        helper_ws.cell(row=1, column=next_col + 1, value="Descripción")

        for i, value in enumerate(rule.allowed_values, start=2):
            helper_ws.cell(row=i, column=next_col, value=value.code)
            helper_ws.cell(row=i, column=next_col + 1, value=value.label)

        last_row = len(rule.allowed_values) + 1
        defined_name_str = _safe_defined_name(rule.column_name)
        ref = f"'{HELPER_SHEET_NAME}'!${col_letter}$2:${col_letter}${last_row}"

        # Evitar nombres duplicados si dos columnas del mismo nombre
        # aparecen en varias hojas del mismo workbook (ej. AÑO, SEMESTRE)
        # -- en ese caso se reutiliza el primero.
        if defined_name_str not in workbook.defined_names:
            workbook.defined_names[defined_name_str] = DefinedName(
                defined_name_str, attr_text=ref
            )

        defined_names[rule.column_name] = defined_name_str
        next_col += 2

    return defined_names
