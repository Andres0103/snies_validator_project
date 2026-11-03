"""Validación de una celda individual contra su `ValidationRule`.

Este módulo es el "espejo" de `validation/excel_validation_builder.py`:
mientras ese construye restricciones para prevenir el error mientras se
escribe, este detecta el error después de que los datos ya existen. Ambos
comparten la misma fuente de reglas (`rules/interpreter.py`), así que
nunca pueden desalinearse entre sí.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any

from rules.models import DataType, ValidationRule


@dataclass
class Issue:
    message: str
    severity: str = "error"  # "error" | "warning"


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")



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


def validate_cell(rule: ValidationRule, value: Any) -> list[Issue]:
    """Valida obligatoriedad, tipo, longitud y valores permitidos de una celda.

    No evalúa reglas de negocio que dependen de OTRAS celdas (eso lo hace
    `validate_business_rule` / `cross_row_validator.py`, que sí tienen
    acceso a la fila o al resto de la columna).
    """
    issues: list[Issue] = []

    if _is_blank(value):
        if rule.required:
            issues.append(Issue(f"Campo obligatorio vacío ('{rule.column_name}')."))
        elif rule.conditional_requirement:
            issues.append(
                Issue(
                    f"Campo vacío; verificar si aplica: {rule.conditional_requirement.raw_text}.",
                    severity="warning",
                )
            )
        return issues  # campo opcional vacío: nada más que revisar

    # --- Tipo de dato ---
    if rule.datatype == DataType.INTEGER:
        num = _to_number(value)
        if num is None or not float(num).is_integer():
            issues.append(Issue(f"'{value}' no es un número entero válido."))
    elif rule.datatype == DataType.DECIMAL:
        if _to_number(value) is None:
            issues.append(Issue(f"'{value}' no es un valor numérico válido."))
    elif rule.datatype == DataType.DATE:
        if _to_date(value, rule.date_formats) is None:
            fmt = rule.date_formats[0] if rule.date_formats else "DD-MM-AAAA"
            issues.append(Issue(f"'{value}' no es una fecha válida (formato esperado {fmt})."))

        # --- Longitud ---
    # Convertimos el valor a texto y eliminamos espacios al inicio y al final.
    # La longitud se mide sobre el dato que realmente se ingresó.
    text_value = str(value).strip()

    # Validar longitud máxima.
    # Esta regla se aplica a todos los campos, incluidos los que comienzan
    # por CODIGO. No se debe permitir que un código numérico supere el límite
    # mientras que uno alfanumérico sí sea evaluado.
    if rule.max_length and len(text_value) > rule.max_length:
        issues.append(
            Issue(
                f"'{value}' tiene {len(text_value)} caracteres; "
                f"máximo {rule.max_length}."
            )
        )

    # Validar longitud mínima, si la regla la define.
    if rule.min_length and len(text_value) < rule.min_length:
        issues.append(
            Issue(
                f"'{value}' tiene {len(text_value)} caracteres; "
                f"mínimo {rule.min_length}."
            )
        )

    # Validar longitud exacta, si la regla la define.
    if rule.exact_length and len(text_value) != rule.exact_length:
        issues.append(
            Issue(
                f"'{value}' debe tener exactamente "
                f"{rule.exact_length} caracteres."
            )
        )

    # --- Valores permitidos ---
    if rule.allowed_values:
        normalized = text_value.upper()
        valid_codes = {v.code.upper() for v in rule.allowed_values}
        # Tolerar "1" vs "1.0" vs 1 (Excel guarda números como float).
        numeric_equivalent = None
        num = _to_number(value)
        if num is not None and float(num).is_integer():
            numeric_equivalent = str(int(num))
        if normalized not in valid_codes and numeric_equivalent not in valid_codes:
            issues.append(
                Issue(
                    f"'{value}' no es un código válido para '{rule.column_name}'. "
                    f"¿Quizás escribió la descripción en vez del código? "
                    f"Valores esperados: {', '.join(sorted(valid_codes))[:120]}."
                )
            )

    return issues


def validate_business_rule(kind: str, params: dict, value: Any, row_values: dict[str, Any]) -> list[Issue]:
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
                issues.append(Issue(params.get("message", "Fecha fuera de rango.")))

    elif kind == "date_after_column":
        d = _to_date(value, [])
        after_col = params.get("after_column")
        other = row_values.get(after_col)
        other_d = _to_date(other, []) if other is not None else None
        if d and other_d and not (d >= other_d):
            issues.append(Issue(params.get("message", "La fecha final debe ser igual o posterior a la fecha de inicio.")))

    elif kind == "non_negative":
        num = _to_number(value)
        if num is not None and num < 0:
            issues.append(Issue(params.get("message", "El valor no puede ser negativo.")))

    elif kind == "non_negative_with_min_length":
        num = _to_number(value)
        text_value = str(value).strip()
        min_len = params.get("min_length", 1)
        if num is not None and num < 0:
            issues.append(Issue(params.get("message", "El valor no puede ser negativo.")))
        if len(text_value) < min_len:
            issues.append(Issue(f"'{value}' tiene menos de {min_len} caracteres."))

    elif kind == "email_format":
        if "@" not in str(value):
            issues.append(Issue(params.get("message", "El email no tiene un formato válido.")))

    return issues
