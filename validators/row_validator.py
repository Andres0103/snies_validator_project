"""Validación de una celda individual contra su `ValidationRule`.

Este módulo es el "espejo" de `validation/excel_validation_builder.py`:
mientras ese construye restricciones para prevenir el error mientras se
escribe, este detecta el error después de que los datos ya existen. Ambos
comparten la misma fuente de reglas (`rules/interpreter.py`), así que
nunca pueden desalinearse entre sí.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from rules.models import DataType, ValidationRule


@dataclass
class Issue:
    message: str
    severity: str = "error"  # "error" | "warning"


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _is_codigo_field(column_name: str) -> bool:
    return column_name.strip().upper().startswith("CODIGO")


def _to_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _to_date(value: Any, formats: list[str]) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    if isinstance(value, str):
        for fmt in formats or ["%d-%m-%Y", "%d/%m/%Y"]:
            try:
                return datetime.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue

    return None


def validate_cell(
    rule: ValidationRule,
    value: Any,
    conditional_applies: bool | None = None,
) -> list[Issue]:
    """Valida obligatoriedad, tipo, longitud y valores permitidos de una celda."""
    issues: list[Issue] = []

    if _is_blank(value):
        if rule.required:
            issues.append(
                Issue(f"Campo obligatorio vacío ('{rule.column_name}').")
            )
        elif rule.conditional_requirement:
            if conditional_applies is True:
                issues.append(
                    Issue(
                        f"Campo obligatorio por condición: "
                        f"{rule.conditional_requirement.raw_text}.",
                        severity="error",
                    )
                )
            elif conditional_applies is None:
                issues.append(
                    Issue(
                        f"Campo vacío; verificar si aplica: "
                        f"{rule.conditional_requirement.raw_text}.",
                        severity="warning",
                    )
                )

        return issues

    # Texto utilizado para validar caracteres y longitud.
    text_value = str(value).strip()

    # Validación del tipo de dato.
    if rule.datatype == DataType.ALPHANUMERIC:
        # CODIGO_CONSULTORIA admite signos y separadores.
        # Para los demás campos alfanuméricos se aplica la validación estricta.
        if (
            rule.column_name.strip().upper() != "CODIGO_CONSULTORIA"
            and not text_value.isalnum()
        ):
            issues.append(
                Issue(
                    "El campo debe contener únicamente letras y números."
                )
            )

    elif rule.datatype == DataType.ALPHABETIC:
        if not text_value.isalpha():
            issues.append(
                Issue("El campo debe contener únicamente letras.")
            )

    elif rule.datatype == DataType.INTEGER:
        num = _to_number(value)

        if num is None or not num.is_integer():
            issues.append(
                Issue("El campo debe contener un número entero válido.")
            )

    elif rule.datatype == DataType.DECIMAL:
        if _to_number(value) is None:
            issues.append(
                Issue("El campo debe contener un valor numérico válido.")
            )

    elif rule.datatype == DataType.DATE:
        if _to_date(value, rule.date_formats) is None:
            fmt = rule.date_formats[0] if rule.date_formats else "DD-MM-AAAA"
            issues.append(
                Issue(
                    f"El campo debe contener una fecha válida "
                    f"(formato esperado {fmt})."
                )
            )

    # Validación de longitud máxima.
    if rule.max_length is not None and len(text_value) > rule.max_length:
        if _is_codigo_field(rule.column_name) and _to_number(value) is None:
            issues.append(
                Issue(
                    f"El código supera la longitud máxima de "
                    f"{rule.max_length} caracteres y no parece ser "
                    f"un código válido."
                )
            )
        else:
            issues.append(
                Issue(
                    f"La longitud es de {len(text_value)} caracteres; "
                    f"máximo permitido: {rule.max_length}."
                )
            )

    # Validación de longitud mínima.
    if rule.min_length is not None and len(text_value) < rule.min_length:
        issues.append(
            Issue(
                f"La longitud es de {len(text_value)} caracteres; "
                f"mínimo permitido: {rule.min_length}."
            )
        )

    # Validación de longitud exacta.
    if rule.exact_length is not None and len(text_value) != rule.exact_length:
        issues.append(
            Issue(
                f"La longitud debe ser exactamente "
                f"{rule.exact_length} caracteres."
            )
        )

    # Validación de valores permitidos.
    # Validación de valores permitidos.
    if rule.allowed_values:
        allowed_codes = {
            str(item.code).strip()
            for item in rule.allowed_values
        }
        allowed_displays = {
            str(item.display).strip()
            for item in rule.allowed_values
        }
        value_text = str(value).strip()

        if (
            value_text not in allowed_codes
            and value_text not in allowed_displays
        ):
            issues.append(
                Issue("El valor no está dentro de los valores permitidos.")
            )

    return issues


def validate_business_rule(
    kind: str,
    params: dict,
    value: Any,
    row_values: dict[str, Any],
) -> list[Issue]:
    """Valida reglas que dependen de la propia celda (no de otras filas)."""
    issues: list[Issue] = []

    if _is_blank(value):
        return issues

    if kind == "date_within_past_years":
        d = _to_date(value, [])

        if d:
            years = params.get("years", 80)
            today = datetime.date.today()
            earliest = today.replace(year=today.year - years)

            if not (earliest <= d <= today):
                issues.append(
                    Issue(params.get("message", "Fecha fuera de rango."))
                )

    elif kind == "date_after_column":
        d = _to_date(value, [])
        after_col = params.get("after_column")
        other = row_values.get(after_col)
        other_d = _to_date(other, []) if other is not None else None

        if d and other_d:
            strict = params.get("strict", False)

            if strict:
                valid = d > other_d
            else:
                valid = d >= other_d

            if not valid:
                default_message = (
                    "La fecha final debe ser posterior a la fecha de inicio."
                    if strict
                    else "La fecha final debe ser igual o posterior "
                    "a la fecha de inicio."
                )
                issues.append(
                    Issue(params.get("message", default_message))
                )

    elif kind == "non_negative":
        num = _to_number(value)

        if num is not None and num < 0:
            issues.append(
                Issue(params.get("message", "El valor no puede ser negativo."))
            )

    elif kind == "non_negative_with_min_length":
        num = _to_number(value)
        text_value = str(value).strip()
        min_len = params.get("min_length", 1)

        if num is not None and num < 0:
            issues.append(
                Issue(params.get("message", "El valor no puede ser negativo."))
            )

        if len(text_value) < min_len:
            issues.append(
                Issue(
                    f"La longitud es menor que el mínimo permitido "
                    f"de {min_len} caracteres."
                )
            )

    elif kind == "email_format":
        if "@" not in str(value):
            issues.append(
                Issue(
                    params.get(
                        "message",
                        "El correo electrónico no tiene un formato válido.",
                    )
                )
            )

    return issues