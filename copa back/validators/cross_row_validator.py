"""Reglas que comparan valores ENTRE filas distintas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from rules.general_model import DataType

from validators.blank_utils import is_blank


def _is_blank(value: Any) -> bool:
    """Compatibilidad con código y pruebas existentes."""
    return is_blank(value)


@dataclass
class CrossRowIssue:
    """Representa una inconsistencia encontrada entre diferentes filas."""

    row: int
    column_name: str
    message: str
    severity: str = "error"


def _normalize_value(
    value: Any,
    data_type: DataType,
) -> tuple[str, Any]:
    """
    Normaliza valores para compararlos según su tipo configurado.

    Reglas:
    - Vacíos: se representan con la categoría "blank".
    - Fechas: se convierten a una representación ISO.
    - Números: se comparan mediante Decimal.
    - Textos: se eliminan los espacios externos.
    - Tipos desconocidos: se tratan como texto.
    - Valores que no pueden convertirse: se identifican como "invalid".
    """

    # Los valores vacíos se identifican antes de cualquier conversión.
    if is_blank(value):
        return ("blank", "")

    # Normalización de tipos textuales.
    # Se conservan los ceros iniciales y el contenido del texto.
    if data_type in {
        DataType.ALPHANUMERIC,
        DataType.TEXT,
        DataType.ALPHABETIC,
    }:
        text_value = str(value).strip()
        return ("text", text_value)

    # Normalización de enteros y decimales.
    # Decimal evita imprecisiones propias de los números float.
    if data_type in {DataType.INTEGER, DataType.DECIMAL}:
        try:
            number = Decimal(str(value))

            if number.is_finite():
                return ("number", number.normalize())

            return ("invalid", str(value))

        except (InvalidOperation, ValueError):
            return ("invalid", str(value))

    # Normalización de fechas.
    if data_type == DataType.DATE:

        # datetime hereda de date, por eso se comprueba primero.
        if isinstance(value, datetime):
            return ("date", value.date().isoformat())

        if isinstance(value, date):
            return ("date", value.isoformat())

        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    parsed = datetime.strptime(value.strip(), fmt).date()
                    return ("date", parsed.isoformat())

                except ValueError:
                    continue

            return ("invalid", str(value))

        return ("invalid", str(value))

    # Si desconocemos el tipo, tratamos el valor como texto.
    # No inferimos números o fechas a partir de su contenido.
    if data_type == DataType.UNKNOWN:
        text_value = str(value).strip()
        return ("text", text_value)

    # Protección para tipos de datos no contemplados.
    return ("other", str(value).strip())


def check_uniqueness(
    column_name: str,
    rows: list[dict[str, Any]],
    row_numbers: list[int],
    column_types: dict[str, DataType],
    severity: str = "warning",
    message_template: str | None = None,
) -> list[CrossRowIssue]:
    """
    Genera una alerta cuando un valor se repite en una columna.

    La comparación respeta el tipo de dato configurado para la columna.
    Los valores vacíos se ignoran.
    """

    issues: list[CrossRowIssue] = []

    # Diccionario que agrupa los índices de las filas según el valor
    # normalizado de la columna.
    seen: dict[tuple[str, Any], list[int]] = defaultdict(list)

    # Obtener el tipo configurado. Si no existe, utilizar UNKNOWN.
    configured = column_types.get(column_name, DataType.UNKNOWN)

    # Recorrer las filas y agrupar los valores equivalentes.
    for i, row in enumerate(rows):

        # Obtener el valor de la columna.
        column_value = row.get(column_name)

        # Ignorar valores vacíos.
        if is_blank(column_value):
            continue

        # Normalizar el valor según su tipo configurado.
        normalized_value = _normalize_value(
            column_value,
            configured,
        )

        # Guardar el índice de la fila en el grupo correspondiente.
        seen[normalized_value].append(i)

    # Identificar los valores que aparecen más de una vez.
    for value, indices in seen.items():

        if len(indices) < 2:
            continue

        # Descomponer la tupla devuelta por _normalize_value().
        kind, normalized_value = value

        # Preparar una representación legible del valor duplicado.
        displayed_value = "(vacío)" if kind == "blank" else str(normalized_value)

        # Generar una incidencia para cada fila involucrada.
        for i in indices:

            msg = (
                message_template
                or f"'{displayed_value}' está repetido en '{column_name}' "
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
    column_types: dict[str, DataType] | None = None,
    group_by: str | None = None,
) -> list[CrossRowIssue]:
    """Comprueba consistencia de columnas seleccionadas por código/grupo."""
    issues: list[CrossRowIssue] = []
    column_types = column_types or {}
    groups: dict[Any, list[int]] = defaultdict(list)

    code_type = column_types.get(code_column, DataType.UNKNOWN)

    for i, row in enumerate(rows):
        code_value = row.get(code_column)

        if is_blank(code_value):
            continue

        code_key = _normalize_value(code_value, code_type)

        if group_by:
            secondary_value = row.get(group_by)
            secondary_type = column_types.get(
                group_by,
                DataType.UNKNOWN,
            )
            secondary_key = _normalize_value(
                secondary_value,
                secondary_type,
            )
            key = (code_key, secondary_key)
        else:
            key = code_key

        groups[key].append(i)

    for key, indices in groups.items():
        if len(indices) < 2:
            continue

        for col in check_columns:
            data_type = column_types.get(col, DataType.UNKNOWN)

            distinct_values = {
                _normalize_value(
                    rows[i].get(col),
                    data_type,
                )
                for i in indices
            }

            if len(distinct_values) <= 1:
                continue

            if group_by:
                code_key, secondary_key = key
                group_description = (
                    f"{code_column}='{code_key[1]}' "
                    f"y {group_by}='{secondary_key[1]}'"
                )
            else:
                group_description = f"{code_column}='{key[1]}'"

            values_description = ", ".join(
                sorted(repr(value[1]) for value in distinct_values)
            )

            for i in indices:
                issues.append(
                    CrossRowIssue(
                        row=row_numbers[i],
                        column_name=col,
                        message=(
                            f"Inconsistencia: las filas agrupadas por "
                            f"{group_description} tienen valores distintos "
                            f"en '{col}': {values_description}."
                        ),
                    )
                )

    return issues
