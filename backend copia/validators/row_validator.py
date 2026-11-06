
"""Validación de una celda individual contra su ValidationRule."""

from __future__ import annotations

import datetime
import unicodedata
from dataclasses import dataclass
from typing import Any

from rules.models import DataType, ValidationRule


@dataclass
class Issue:
    message: str
    severity: str = "error"


def _is_blank(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and value.strip() == ""
    )


def _is_codigo_field(column_name: str) -> bool:
    return column_name.strip().upper().startswith("CODIGO")


def _is_identifier_field(column_name: str) -> bool:
    """Identificadores que no deben admitir espacios ni puntuación."""
    name = column_name.strip().upper()

    return (
        name.startswith("CODIGO")
        or name in {
            "NUM_DOCUMENTO",
            "ID_TIPO_DOCUMENTO",
        }
    )


def _is_alphabetic_text(value: str) -> bool:
    """
    Acepta letras Unicode, marcas diacríticas, espacios,
    apóstrofos y guiones.
    """
    allowed_separators = {"'", "’", "-", " "}

    for char in value:
        category = unicodedata.category(char)

        if category.startswith(("L", "M")):
            continue

        if char in allowed_separators:
            continue

        return False

    return True


def _is_descriptive_alphanumeric(value: str) -> bool:
    """
    Acepta letras, números, espacios y signos de puntuación
    en campos descriptivos.
    """
    for char in value:
        category = unicodedata.category(char)

        if category.startswith(("L", "M", "N", "P")):
            continue

        if char.isspace():
            continue

        return False

    return True


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


def _to_date(
    value: Any,
    formats: list[str],
) -> datetime.date | None:

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    if isinstance(value, str):
        for fmt in formats or ["%d-%m-%Y", "%d/%m/%Y"]:
            try:
                return datetime.datetime.strptime(
                    value.strip(), fmt
                ).date()
            except ValueError:
                continue

    return None


def validate_cell(
    rule: ValidationRule,
    value: Any,
    conditional_applies: bool | None = None,
) -> list[Issue]:
    """Valida obligatoriedad, tipo, longitud y valores permitidos."""

    issues: list[Issue] = []

    column_name = rule.column_name.strip().upper()

    # 1. Validación de obligatoriedad
    if _is_blank(value):

        if rule.required:
            issues.append(
                Issue(
                    f"Campo obligatorio vacío ('{rule.column_name}')."
                )
            )

        elif conditional_applies is True:
            if rule.conditional_requirement:
                condition_description = (
                    rule.conditional_requirement.raw_text
                )
            else:
                condition_description = (
                    "se cumple la condición definida para el campo"
                )

            issues.append(
                Issue(
                    f"Campo obligatorio por condición: "
                    f"{condition_description}.",
                    severity="error",
                )
            )

        elif (
            rule.conditional_requirement
            and conditional_applies is None
        ):
            issues.append(
                Issue(
                    f"Campo vacío; verificar si aplica: "
                    f"{rule.conditional_requirement.raw_text}.",
                    severity="warning",
                )
            )

        return issues

    # 2. Preparación del valor
    text_value = str(value).strip()

    # 3. Validación del tipo de dato

    if rule.datatype == DataType.ALPHANUMERIC:

        # Los identificadores tienen restricciones más estrictas.
        if _is_identifier_field(column_name):

            # CODIGO_CONSULTORIA admite separadores según
            # la excepción implementada previamente.
            if column_name != "CODIGO_CONSULTORIA":
                if not text_value.isalnum():
                    issues.append(
                        Issue(
                            "El campo debe contener únicamente "
                            "letras y números."
                        )
                    )

        else:
            if not _is_descriptive_alphanumeric(text_value):
                issues.append(
                    Issue(
                        "El campo debe contener letras, números "
                        "y signos de puntuación válidos."
                    )
                )

    elif rule.datatype == DataType.ALPHABETIC:

        descriptive_fields = {
            "DESCRIPCION_CONSULTORIA",
            "NOMBRE_ENTIDAD",
            "NOMBRE_INSTITUCION",
        }

        # SEMESTRE se controla mediante los valores permitidos
        # definidos en su regla, no mediante una expresión alfabética.
        if column_name == "SEMESTRE":
            pass

        elif column_name in descriptive_fields:
            if not _is_descriptive_alphanumeric(text_value):
                issues.append(
                    Issue(
                        "El campo debe contener letras, números "
                        "y signos de puntuación válidos."
                    )
                )

        elif not _is_alphabetic_text(text_value):
            issues.append(
                Issue(
                    "El campo debe contener únicamente letras."
                )
            )

    elif rule.datatype == DataType.INTEGER:

        num = _to_number(value)

        if num is None or not num.is_integer():
            issues.append(
                Issue(
                    "El campo debe contener un número entero válido."
                )
            )

    elif rule.datatype == DataType.DECIMAL:

        if _to_number(value) is None:
            issues.append(
                Issue(
                    "El campo debe contener un valor numérico válido."
                )
            )

    elif rule.datatype == DataType.DATE:

        if _to_date(value, rule.date_formats) is None:
            fmt = (
                rule.date_formats[0]
                if rule.date_formats
                else "DD-MM-AAAA"
            )

            issues.append(
                Issue(
                    f"El campo debe contener una fecha válida "
                    f"(formato esperado {fmt})."
                )
            )

    # 4. Validación de longitud máxima
    if (
        rule.max_length is not None
        and len(text_value) > rule.max_length
    ):
        if (
            _is_codigo_field(column_name)
            and _to_number(value) is None
        ):
            issues.append(
                Issue(
                    f"El código supera la longitud máxima de "
                    f"{rule.max_length} caracteres."
                )
            )
        else:
            issues.append(
                Issue(
                    f"La longitud es de {len(text_value)} caracteres; "
                    f"máximo permitido: {rule.max_length}."
                )
            )

    # 5. Validación de longitud mínima
    if (
        rule.min_length is not None
        and len(text_value) < rule.min_length
    ):
        issues.append(
            Issue(
                f"La longitud es de {len(text_value)} caracteres; "
                f"mínimo permitido: {rule.min_length}."
            )
        )

    # 6. Validación de longitud exacta
    if (
        rule.exact_length is not None
        and len(text_value) != rule.exact_length
    ):
        issues.append(
            Issue(
                f"La longitud debe ser exactamente "
                f"{rule.exact_length} caracteres."
            )
        )

    # 7. Validación de valores permitidos
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
                Issue(
                    "El valor no está dentro de los valores permitidos."
                )
            )

    return issues


def validate_business_rule(
    kind: str,
    params: dict,
    value: Any,
    row_values: dict[str, Any],
) -> list[Issue]:
    """Valida reglas que dependen de la propia celda."""

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
                    Issue(
                        params.get("message", "Fecha fuera de rango.")
                    )
                )

    elif kind == "date_after_column":
        d = _to_date(value, [])
        after_col = params.get("after_column")
        other = row_values.get(after_col)

        other_d = (
            _to_date(other, [])
            if other is not None
            else None
        )

        if d and other_d:
            strict = params.get("strict", False)

            if strict:
                valid = d > other_d
            else:
                valid = d >= other_d

            if not valid:
                default_message = (
                    "La fecha final debe ser posterior "
                    "a la fecha de inicio."
                    if strict
                    else "La fecha final debe ser igual o posterior "
                    "a la fecha de inicio."
                )

                issues.append(
                    Issue(
                        params.get("message", default_message)
                    )
                )

    elif kind == "non_negative":
        num = _to_number(value)

        if num is not None and num < 0:
            issues.append(
                Issue(
                    params.get(
                        "message",
                        "El valor no puede ser negativo.",
                    )
                )
            )

    elif kind == "non_negative_with_min_length":
        num = _to_number(value)
        text_value = str(value).strip()
        min_len = params.get("min_length", 1)

        if num is not None and num < 0:
            issues.append(
                Issue(
                    params.get(
                        "message",
                        "El valor no puede ser negativo.",
                    )
                )
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
