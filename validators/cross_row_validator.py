"""Reglas que comparan valores ENTRE filas distintas.

Esto es precisamente lo que la validación nativa de Excel no puede hacer
(una `DataValidation` solo ve la celda que se está editando), y por eso
en `rules/patterns/business_rules.yaml` estas reglas están marcadas como
`cross_row_consistency_note`: quedan documentadas en la plantilla, pero
se aplican de verdad aquí, con Python, que sí puede recorrer toda la
columna.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class CrossRowIssue:
    row: int
    column_name: str
    message: str
    severity: str = "error"


def check_uniqueness(
    column_name: str,
    rows: list[dict[str, Any]],
    row_numbers: list[int],
    severity: str = "warning",
    message_template: str | None = None,
) -> list[CrossRowIssue]:
    """Genera una alerta cuando un valor se repite en una columna que debería
    identificar de forma única cada fila de la hoja."""
    issues: list[CrossRowIssue] = []
    seen: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        value = row.get(column_name)
        if value is None or str(value).strip() == "":
            continue
        seen[str(value).strip()].append(i)

    for value, indices in seen.items():
        if len(indices) < 2:
            continue
        for i in indices:
            msg = message_template or f"'{value}' está repetido en '{column_name}' ({len(indices)} filas)."
            issues.append(CrossRowIssue(row=row_numbers[i], column_name=column_name, message=msg, severity=severity))

    return issues


def check_code_consistency(
    code_column: str,
    check_columns: list[str],
    rows: list[dict[str, Any]],
    row_numbers: list[int],
    group_by: str | None = None,
) -> list[CrossRowIssue]:
    """Para un mismo valor de `code_column` (+ `group_by` si se indica), las
    columnas en `check_columns` deben coincidir entre filas del grupo.

    Solo se comparan las columnas explícitamente listadas — nunca "todas
    las columnas de la hoja" — para no generar falsos positivos en hojas
    donde es normal que otras columnas varíen dentro del mismo grupo (ej.
    varias personas bajo el mismo código en una hoja de recurso humano).
    """
    issues: list[CrossRowIssue] = []

    groups: dict[Any, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        code_value = row.get(code_column)
        if code_value is None or str(code_value).strip() == "":
            continue
        key = str(code_value).strip()
        if group_by:
            secondary = row.get(group_by)
            key = (key, str(secondary).strip() if secondary is not None else "")
        groups[key].append(i)

    for key, indices in groups.items():
        if len(indices) < 2:
            continue
        for col in check_columns:
            distinct_values = {
                str(rows[i].get(col)).strip()
                for i in indices
                if rows[i].get(col) is not None and str(rows[i].get(col)).strip() != ""
            }
            if len(distinct_values) > 1:
                for i in indices:
                    issues.append(
                        CrossRowIssue(
                            row=row_numbers[i],
                            column_name=col,
                            message=(
                                f"Inconsistencia: filas con {code_column}='{key}' "
                                f"tienen valores distintos en '{col}': {sorted(distinct_values)}."
                            ),
                        )
                    )

    return issues
