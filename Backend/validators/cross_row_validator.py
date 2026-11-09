
"""Reglas que comparan valores ENTRE filas distintas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class CrossRowIssue:
    row: int
    column_name: str
    message: str
    severity: str = "error"


def _is_blank(value: Any) -> bool:
    """Determina si un valor está vacío."""
    return value is None or (
        isinstance(value, str) and value.strip() == ""
    )


def _normalize_value(value: Any) -> tuple[str, Any]:
    """
    Normaliza valores para compararlos según su significado.

    - Vacíos: se representan como una misma categoría.
    - Fechas: se convierten a fecha ISO.
    - Números: se comparan mediante Decimal.
    - Textos: se eliminan espacios externos.
    """
    if _is_blank(value):
        return ("blank", "")

    if isinstance(value, datetime):
        return ("date", value.date().isoformat())

    if isinstance(value, date):
        return ("date", value.isoformat())

    if isinstance(value, bool):
        return ("boolean", value)

    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
            return ("number", number.normalize())
        except InvalidOperation:
            pass

    if isinstance(value, str):
        text = value.strip()

        # Normalización de fechas con formatos habituales.
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(text, fmt).date()
                return ("date", parsed.isoformat())
            except ValueError:
                continue

        # Normalización de números escritos como texto.
        try:
            number = Decimal(text.replace(",", ""))
            return ("number", number.normalize())
        except InvalidOperation:
            pass

        return ("text", text)

    return ("other", str(value).strip())


def check_uniqueness(
    column_name: str,
    rows: list[dict[str, Any]],
    row_numbers: list[int],
    severity: str = "warning",
    message_template: str | None = None,
) -> list[CrossRowIssue]:
    """Genera una alerta cuando un valor se repite en una columna."""
    issues: list[CrossRowIssue] = []
    seen: dict[str, list[int]] = defaultdict(list)

    for i, row in enumerate(rows):
        value = row.get(column_name)

        if _is_blank(value):
            continue

        seen[str(value).strip()].append(i)

    for value, indices in seen.items():
        if len(indices) < 2:
            continue

        for i in indices:
            msg = (
                message_template
                or f"'{value}' está repetido en '{column_name}' "
                   f"({len(indices)} filas)."
            )

            issues.append(
                CrossRowIssue(
                    row=row_numbers[i],
                    column_name=column_name,
                    message=msg,
                    severity=severity,
                )
            )

    return issues


def check_code_consistency(
    code_column: str,
    check_columns: list[str],
    rows: list[dict[str, Any]],
    row_numbers: list[int],
    group_by: str | None = None,
) -> list[CrossRowIssue]:
    """
    Verifica que las columnas configuradas mantengan los mismos valores
    para cada código y, opcionalmente, grupo adicional.

    Los valores vacíos también se comparan: vacío y diligenciado
    representan valores diferentes.
    """
    issues: list[CrossRowIssue] = []

    groups: dict[Any, list[int]] = defaultdict(list)

    for i, row in enumerate(rows):
        code_value = row.get(code_column)

        if _is_blank(code_value):
            continue

        key: Any = str(code_value).strip()

        if group_by:
            secondary = row.get(group_by)
            secondary_key = (
                "" if _is_blank(secondary)
                else str(secondary).strip()
            )
            key = (key, secondary_key)

        groups[key].append(i)

    for key, indices in groups.items():
        if len(indices) < 2:
            continue

        for column in check_columns:
            distinct_values = {
                _normalize_value(rows[i].get(column))
                for i in indices
            }

            if len(distinct_values) <= 1:
                continue

            displayed_values = sorted(
                "(vacío)" if kind == "blank" else str(value)
                for kind, value in distinct_values
            )

            for i in indices:
                issues.append(
                    CrossRowIssue(
                        row=row_numbers[i],
                        column_name=column,
                        message=(
                            f"Inconsistencia: filas con {code_column}='{key}' "
                            f"tienen valores distintos en '{column}': "
                            f"{displayed_values}."
                        ),
                    )
                )

    return issues
