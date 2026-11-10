
"""Reglas que comparan valores ENTRE filas distintas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.rules.general_model import DataType


@dataclass
class CrossRowIssue:
    """Representa una inconsistencia encontrada entre diferentes filas."""

    row: int
    column_name: str
    message: str
    severity: str = "error"


def _is_blank(value: Any) -> bool:
    """Determina si un valor está vacío."""

    return value is None or (
        isinstance(value, str) and value.strip() == ""
    )


def _normalize_value(
    value: Any,
    data_type: DataType,
) -> tuple[str, Any]:
    """
    Normaliza valores para compararlos según su tipo configurado.

    - Vacíos: se representan como una misma categoría.
    - Fechas: se convierten a fecha ISO.
    - Números: se comparan mediante Decimal.
    - Textos: se eliminan espacios externos.
    - Tipos desconocidos: se tratan como texto.
    """

    # Los valores vacíos se identifican antes de cualquier conversión.
    if _is_blank(value):
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
    # Decimal permite comparar valores numéricos sin depender
    # de las imprecisiones propias de los números float.
    if data_type in {DataType.INTEGER, DataType.DECIMAL}:
        try:
            number = Decimal(str(value))

            if number.is_finite():
                return ("number", number.normalize())

            return ("invalid", str(value))

        except InvalidOperation:
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
    # No intentamos inferir números o fechas a partir del contenido.
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

    # Diccionario que agrupa los índices de las filas
    # según el valor normalizado de la columna.
    seen: dict[tuple[str, Any], list[int]] = defaultdict(list)

    # Obtener el tipo configurado para la columna.
    # Si no existe configuración, utilizar UNKNOWN.
    configured = column_types.get(column_name, DataType.UNKNOWN)

    # Recorrer las filas y agrupar los valores equivalentes.
    for i, row in enumerate(rows):

        # Obtener el valor de la columna.
        column_value = row.get(column_name)

        # Ignorar valores vacíos.
        if _is_blank(column_value):
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
        displayed_value = (
            "(vacío)"
            if kind == "blank"
            else str(normalized_value)
        )

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
    column_types: dict[str, DataType],
    group_by: str | None = None,
) -> list[CrossRowIssue]:
    """
    Verifica que las columnas configuradas mantengan los mismos valores
    para cada código y, opcionalmente, grupo adicional.

    Los valores vacíos también se comparan:
    vacío y diligenciado representan valores diferentes.
    """

    issues: list[CrossRowIssue] = []

    # Diccionario que agrupa los índices de las filas
    # según el código y, opcionalmente, una segunda columna.
    groups: dict[Any, list[int]] = defaultdict(list)

    # ---------------------------------------------------------
    # 1. Construir los grupos según el código y group_by.
    # ---------------------------------------------------------
    for i, row in enumerate(rows):

        # Obtener el código de la fila.
        row_key = row.get(code_column)

        # Ignorar filas sin código.
        if _is_blank(row_key):
            continue

        # Obtener el tipo configurado para el código.
        data_config = column_types.get(
            code_column,
            DataType.UNKNOWN,
        )

        # Normalizar el código según su tipo.
        code_normalized = _normalize_value(
            row_key,
            data_config,
        )

        # Si existe una columna secundaria, incluirla en la clave.
        if group_by:

            group_value = row.get(group_by)

            configured_data_type = column_types.get(
                group_by,
                DataType.UNKNOWN,
            )

            secondary_normalized = _normalize_value(
                group_value,
                configured_data_type,
            )

            key = (code_normalized, secondary_normalized)

        else:
            # Si no existe group_by, utilizar únicamente el código.
            key = code_normalized

        # Agregar el índice de la fila al grupo correspondiente.
        groups[key].append(i)

    # ---------------------------------------------------------
    # 2. Comparar los valores de las columnas configuradas.
    # ---------------------------------------------------------
    for group_key, indices in groups.items():

        # No tiene sentido comparar grupos con una sola fila.
        if len(indices) < 2:
            continue

        # Recorrer las columnas que deben mantener consistencia.
        for column in check_columns:

            # Obtener el tipo configurado para la columna.
            configured_data_type = column_types.get(
                column,
                DataType.UNKNOWN,
            )

            # Conjunto para almacenar los valores distintos.
            distinct_values = set()

            # Recorrer las filas que pertenecen al grupo.
            for i in indices:

                column_value = rows[i].get(column)

                # Normalizar el valor según su tipo.
                normalized_value = _normalize_value(
                    column_value,
                    configured_data_type,
                )

                # Los conjuntos eliminan valores duplicados.
                distinct_values.add(normalized_value)

            # Si existe un único valor, no hay inconsistencia.
            if len(distinct_values) <= 1:
                continue

            # Preparar los valores para mostrarlos en el mensaje.
            displayed_values = sorted(
                "(vacío)" if kind == "blank"
                else f"{kind}: {value}"
                for kind, value in distinct_values
            )

            # Generar una incidencia para cada fila del grupo.
            for i in indices:

                issues.append(
                    CrossRowIssue(
                        row=row_numbers[i],
                        column_name=column,
                        message=(
                            f"Inconsistencia: filas con "
                            f"{code_column}='{group_key}' "
                            f"tienen valores distintos en '{column}': "
                            f"{displayed_values}."
                        ),
                    )
                )

    return issues
