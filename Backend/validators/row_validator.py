
"""
Validador de celdas y reglas de negocio.

Este módulo contiene las funciones encargadas de validar valores
individuales utilizando las reglas definidas en ValidationRule.

No debe contener condiciones particulares de una plantilla.
Las restricciones específicas se reciben mediante la configuración.
"""

from __future__ import annotations

# ============================================================
# 1. IMPORTACIONES
# ============================================================

from cmath import isfinite
import datetime
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from rules.general_model import DataType, ValidationRule

import re


# ============================================================
# 2. ESTRUCTURA PARA REPORTAR ERRORES
# ============================================================

@dataclass
class Issue:
    """Representa un problema encontrado durante una validación."""

    message: str
    severity: str = "error"


# ============================================================
# 3. FUNCIONES AUXILIARES
# ============================================================

def _is_blank(value: Any) -> bool:
    """Determina si un valor está vacío."""

    return value is None or (
        isinstance(value, str) and value.strip() == ""
    )


def _is_alphabetic_text(value: str) -> bool:
    """
    Comprueba que el texto contenga letras Unicode,
    marcas diacríticas, espacios, apóstrofos o guiones.
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
    Comprueba que el texto contenga letras, números,
    espacios y signos de puntuación.
    """

    for char in value:
        category = unicodedata.category(char)

        if category.startswith(("L", "M", "N", "P")):
            continue

        if char.isspace():
            continue

        return False

    return True


def _to_number(value: Any) -> Decimal | None:
    """
    Convierte un valor a Decimal sin introducir imprecisiones
    propias de la conversión a float.
    """

    #evitamos convertir valores booleanos a números poruqe un bool no debe considerarse un número en este contexto  
    if isinstance(value, bool):
        return None

    #validamos que el valor sea finito
    if isinstance(value, Decimal):
        if value.is_finite(): 
            return value
        return None

    #convertimos a Decimal desde int o float, evitando problemas de precisión
    if isinstance(value, (int, float)):
        try:
            num = Decimal(str(value))
            if num.is_finite():
                return num
            
            return None
        except InvalidOperation:
            return None

    if isinstance(value, str):
        try:
            num = Decimal(value.strip())
            if num.is_finite():
                return num
            return None
        
        except InvalidOperation:
            return None

    return None

def _to_date(value: Any, formats: list[str]) -> datetime.date | None:

    # 1. Comprobar si está vacío.
    if _is_blank(value):
        return None

    # 2. Si es datetime, obtener únicamente la fecha.
    if isinstance(value, datetime.datetime):
        return value.date()

    # 3. Si ya es date, devolverlo directamente.
    if isinstance(value, datetime.date):
        return value

    # 4. Si no es string, retornar None.
    if not isinstance(value, str):
        return None

    # 5. Definir los formatos predeterminados.
    if not formats:
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y"
        ]

    # 6. Intentar convertir utilizando cada formato.
    for formato in formats:
        try:
            fecha = datetime.datetime.strptime(value.strip(), formato)

            # Retornar únicamente la fecha.
            return fecha.date()

        except ValueError:
            # Intentar con el siguiente formato.
            continue

    # 7. Ningún formato consiguió convertir el valor.
    return None

# ============================================================
# 4. VALIDACIÓN GENERAL DE CELDAS
# ============================================================

def validate_cell(
    rule: ValidationRule,
    value: Any,
    conditional_applies: bool | None = None,
) -> list[Issue]:
    """
    Valida una celda utilizando las propiedades de ValidationRule.

    Comprueba:
    - Obligatoriedad.
    - Tipo de dato.
    - Longitud mínima.
    - Longitud máxima.
    - Longitud exacta.
    - Valores permitidos.
    """

    issues: list[Issue] = []

    # --------------------------------------------------------
    # 4.1. Validación de obligatoriedad
    # --------------------------------------------------------

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

        # No se deben ejecutar las demás validaciones
        # cuando el valor está vacío.
        return issues

    # --------------------------------------------------------
    # 4.2. Preparación del valor
    # --------------------------------------------------------

    text_value = str(value).strip()

    # --------------------------------------------------------
    # 4.3. Validación del tipo de dato
    # --------------------------------------------------------

    if rule.datatype == DataType.ALPHANUMERIC:

        if not _is_descriptive_alphanumeric(text_value):
            issues.append(
                Issue(
                    "El campo debe contener letras, números "
                    "y signos de puntuación válidos."
                )
            )

    elif rule.datatype == DataType.ALPHABETIC:

        if not _is_alphabetic_text(text_value):
            issues.append(
                Issue(
                    "El campo debe contener únicamente letras."
                )
            )

    elif rule.datatype == DataType.INTEGER:

        num = _to_number(value)

        if num is None or num != num.to_integral_value():
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

    # TEXT y UNKNOWN no tienen una validación de caracteres
    # específica en este módulo.

    # --------------------------------------------------------
    # 4.4. Validación de longitud máxima
    # --------------------------------------------------------

    if (
        rule.max_length is not None
        and len(text_value) > rule.max_length
    ):
        issues.append(
            Issue(
                f"La longitud es de {len(text_value)} caracteres; "
                f"máximo permitido: {rule.max_length}."
            )
        )

    # --------------------------------------------------------
    # 4.5. Validación de longitud mínima
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 4.6. Validación de longitud exacta
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 4.7. Validación de valores permitidos
    # --------------------------------------------------------

    if rule.allowed_values:

        value_text = str(value).strip()

        # Se obtienen los códigos y sus representaciones completas.
        allowed_codes = {
            str(item.code).strip()
            for item in rule.allowed_values
        }

        allowed_displays = {
            str(item.display).strip()
            for item in rule.allowed_values
        }

        # Primero se comprueba la coincidencia textual exacta.
        is_valid = (
            value_text in allowed_codes
            or value_text in allowed_displays
        )

        # Para campos numéricos se permite comparar
        # representaciones numéricas equivalentes.
        if not is_valid and rule.datatype in {
            DataType.INTEGER,
            DataType.DECIMAL,
        }:

           if not isinstance(value, bool):
                
                allowed_numeric_codes = set()
                #convierte el valor de la celda y lo guarda en numeric_value
                numeric_value = _to_number(value)

                for code in allowed_codes:
                    numeric_code = _to_number(code)

                    if numeric_code is not None:
                        allowed_numeric_codes.add(numeric_code)
                    
                is_valid = numeric_value is not None and numeric_value in allowed_numeric_codes
                                    

        if not is_valid:
            issues.append(
                Issue(
                    "El valor no está dentro de los valores permitidos."
                )
            )
        
    return issues


# ============================================================
# 5. VALIDACIÓN DE REGLAS DE NEGOCIO INDIVIDUALES
# ============================================================

def validate_business_rule(
    kind: str,
    params: dict,
    value: Any,
    row_values: dict[str, Any],
) -> list[Issue]:
    """
    Ejecuta reglas de negocio que requieren evaluar un valor
    junto con otros datos de la misma fila.
    """

    issues: list[Issue] = []

    # --------------------------------------------------------
    # 5.1. Comprobación de valores vacíos
    # --------------------------------------------------------

    if _is_blank(value):
        return issues

    # --------------------------------------------------------
    # 5.2. Fecha dentro de un rango de años anteriores
    # --------------------------------------------------------

    if kind == "date_within_past_years":

        date_value = _to_date(value, [])

        if date_value:
            years = params.get("years", 80)
            today = datetime.date.today()

            try:
                earliest = today.replace(year=today.year - years)
            except ValueError:
                # Maneja el caso del 29 de febrero
                # cuando el año de destino no es bisiesto.
                earliest = today.replace(
                    year=today.year - years,
                    day=28,
                )

            if not (earliest <= date_value <= today):
                issues.append(
                    Issue(
                        params.get(
                            "message",
                            "Fecha fuera de rango.",
                        )
                    )
                )

    # --------------------------------------------------------
    # 5.3. Comparación entre dos fechas
    # --------------------------------------------------------

    elif kind == "date_after_column":

        date_value = _to_date(value, [])
        after_column = params.get("after_column")
        other_value = row_values.get(after_column)

        other_date = (
            _to_date(other_value, [])
            if other_value is not None
            else None
        )

        if date_value and other_date:

            strict = params.get("strict", False)

            if strict:
                valid = date_value > other_date
            else:
                valid = date_value >= other_date

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

    # --------------------------------------------------------
    # 5.4. Validación de valores no negativos
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 5.5. Validación de valor no negativo y longitud mínima
    # --------------------------------------------------------

    elif kind == "non_negative_with_min_length":

        num = _to_number(value)
        text_value = str(value).strip()
        min_length = params.get("min_length", 1)

        if num is not None and num < 0:
            issues.append(
                Issue(
                    params.get(
                        "message",
                        "El valor no puede ser negativo.",
                    )
                )
            )

        if len(text_value) < min_length:
            issues.append(
                Issue(
                    f"La longitud es menor que el mínimo permitido "
                    f"de {min_length} caracteres."
                )
            )

    # --------------------------------------------------------
    # 5.6. Validación básica de formato de correo electrónico
    # --------------------------------------------------------

    elif kind == "email_format":

        email = str(value).strip()

        if not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email
        ):
            issues.append(
                Issue(
                    params.get(
                        "message",
                        "El correo electrónico no tiene un formato válido.",
                    )
                )
            )

    return issues
