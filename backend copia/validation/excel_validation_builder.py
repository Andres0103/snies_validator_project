"""Convierte una `ValidationRule` (+ reglas de negocio opcionales) en
objetos `openpyxl.worksheet.datavalidation.DataValidation` listos para
aplicar a un rango de celdas.

Ningún otro módulo construye `DataValidation` a mano; todos pasan por
aquí, así que agregar un tipo de validación nuevo es un solo lugar de
cambio.
"""

from __future__ import annotations

from openpyxl.worksheet.datavalidation import DataValidation

from rules.models import DataType, ValidationRule

MAX_EXCEL_MESSAGE_LEN = 255  # límite práctico de Excel para mensajes de entrada/error


def _truncate(text: str, limit: int = MAX_EXCEL_MESSAGE_LEN) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_input_message(rule: ValidationRule) -> tuple[str, str]:
    """Construye (título, cuerpo) del mensaje de ayuda al seleccionar la celda."""
    title = rule.column_name[:32]  # Excel limita el título a 32 caracteres

    parts = []
    if rule.description:
        parts.append(rule.description)
    if rule.required:
        parts.append("Campo obligatorio.")
    elif rule.conditional_requirement:
        parts.append(f"Obligatorio {rule.conditional_requirement.raw_text.split(' ', 1)[-1]}.")
    if rule.max_length:
        parts.append(f"Máximo {rule.max_length} caracteres.")
    if rule.date_formats:
        parts.append(f"Formato de fecha: {' o '.join(rule.date_formats)}.")
    if rule.allowed_values:
        # Solo se listan valores si caben con margen; si no, se remite a la
        # hoja auxiliar en vez de truncar la lista de forma engañosa.
        legend = "; ".join(v.display for v in rule.allowed_values)
        if len(legend) <= 180:
            parts.append(f"Valores válidos: {legend}.")
        else:
            parts.append(
                f"Seleccione un código del listado desplegable "
                f"(ver hoja '_Listas_Auxiliares' para el detalle)."
            )

    body = _truncate(" ".join(parts))
    return title, body


def build_list_validation(rule: ValidationRule, defined_name: str) -> DataValidation:
    """Desplegable respaldado por un rango con nombre en la hoja auxiliar."""
    dv = DataValidation(
        type="list",
        formula1=f"={defined_name}",
        allow_blank=not rule.required,
        showDropDown=False,  # False = sí muestra la flecha (comportamiento histórico de openpyxl)
    )
    dv.showErrorMessage = True
    dv.errorTitle = "Valor no permitido"
    dv.error = _truncate(
        f"'{rule.column_name}' debe ser uno de los códigos de la lista desplegable."
    )
    title, body = _build_input_message(rule)
    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body
    return dv


def build_type_validation(rule: ValidationRule, column_letter: str = "A") -> DataValidation | None:
    """Restricción de tipo/longitud cuando NO hay lista de valores permitidos."""
    dv: DataValidation | None = None

    if rule.datatype == DataType.INTEGER:
        dv = DataValidation(type="whole", operator="between", formula1="-999999999999", formula2="999999999999")
    elif rule.datatype == DataType.DECIMAL:
        dv = DataValidation(type="decimal", operator="between", formula1="-999999999999", formula2="999999999999")
    elif rule.datatype == DataType.DATE:
        dv = DataValidation(type="date", operator="between", formula1="1900-01-01", formula2="2100-12-31")
    elif rule.datatype in (DataType.ALPHANUMERIC, DataType.ALPHABETIC, DataType.TEXT):
        if rule.max_length and _is_codigo_field(rule.column_name):
            return build_code_length_or_numeric_validation(rule, column_letter)
        if rule.max_length:
            dv = DataValidation(type="textLength", operator="lessThanOrEqual", formula1=str(rule.max_length))
    elif rule.exact_length:
        dv = DataValidation(type="textLength", operator="equal", formula1=str(rule.exact_length))

    if dv is None:
        return None

    dv.allow_blank = not rule.required
    dv.showErrorMessage = True
    dv.errorTitle = "Dato inválido"
    dv.error = _truncate(_build_error_text(rule))
    title, body = _build_input_message(rule)
    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body
    return dv


def _is_codigo_field(column_name: str) -> bool:
    return column_name.strip().upper().startswith("CODIGO")


def build_code_length_or_numeric_validation(rule: ValidationRule, column_letter: str = "A") -> DataValidation:
    """Para columnas CODIGO_* con longitud máxima declarada.

    En la práctica, cuando alguien excede la longitud máxima de un campo
    CODIGO_* casi siempre es porque escribió una descripción/referencia
    larga en vez del código interno corto (ej. "ACTA DE COMPROMISO No.
    ..." en vez de un id numérico). En ese caso, en lugar de solo avisar
    "muy largo", se acepta igual si el valor es puramente numérico (un id
    numérico largo es válido, no está acotado por este límite de texto);
    si no es numérico, el mensaje de error orienta específicamente a que
    seguramente se escribió texto descriptivo en vez del código.
    """
    row_cell = f"{column_letter}2"  # Excel ajusta la referencia de forma relativa al resto del rango
    dv = DataValidation(
        type="custom",
        formula1=f"=OR(LEN({row_cell})<={rule.max_length},IFERROR(ISNUMBER(--{row_cell}),FALSE))",
    )
    dv.allow_blank = not rule.required
    dv.showErrorMessage = True
    dv.errorTitle = "Dato inválido"
    dv.error = _truncate(
        f"'{rule.column_name}' supera {rule.max_length} caracteres y no es un valor numérico. "
        f"¿Escribió una descripción en vez del código?"
    )
    title, body = _build_input_message(rule)
    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body
    return dv


def _build_error_text(rule: ValidationRule) -> str:
    if rule.datatype == DataType.INTEGER:
        return f"'{rule.column_name}' debe ser un número entero."
    if rule.datatype == DataType.DECIMAL:
        return f"'{rule.column_name}' debe ser un valor numérico."
    if rule.datatype == DataType.DATE:
        fmt = rule.date_formats[0] if rule.date_formats else "DD-MM-AAAA"
        return f"'{rule.column_name}' debe ser una fecha válida (formato {fmt})."
    if rule.max_length:
        return f"'{rule.column_name}' no debe superar {rule.max_length} caracteres."
    return f"Valor inválido para '{rule.column_name}'."


# --- Reglas de negocio adicionales (ver rules/patterns/business_rules.yaml) ---

def build_business_rule_validation(kind: str, params: dict, column_letter: str, rule: ValidationRule | None = None) -> DataValidation | None:
    """Construye validaciones para los `kind` definidos en business_rules.yaml.

    `column_letter` es la columna donde vive el propio campo (necesaria
    para fórmulas que se comparan contra una celda de la misma fila, ej.
    FECHA_FINAL > FECHA_INICIO).
    """
    if kind == "date_within_past_years":
        years = params.get("years", 80)
        dv = DataValidation(
            type="date",
            operator="between",
            formula1=f"=EDATE(TODAY(),-{years}*12)",
            formula2="=TODAY()",
        )
    elif kind == "non_negative":
        dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0")
    elif kind == "non_negative_with_min_length":
        min_len = params.get("min_length", 1)
        # Fórmula personalizada: valor >= 0 en apariencia numérica Y longitud
        # de texto mínima. Se usa `custom` combinando ambas condiciones.
        row_cell = f"{column_letter}2"
        dv = DataValidation(
            type="custom",
            formula1=f"=AND(LEN({row_cell})>={min_len},ISNUMBER(VALUE({row_cell})),VALUE({row_cell})>=0)",
        )
    elif kind == "email_format":
        row_cell = f"{column_letter}2"
        dv = DataValidation(type="custom", formula1=f'=ISNUMBER(SEARCH("@",{row_cell}))')
    elif kind == "date_after_column":
        # Se resuelve en el llamador porque necesita la letra de la OTRA
        # columna (after_column), no solo la propia.
        return None
    else:
        return None

    dv.allow_blank = True
    dv.showErrorMessage = True
    dv.errorTitle = "Regla de negocio"
    dv.error = _truncate(params.get("message", "Valor no cumple la regla de negocio."))

    title = rule.column_name[:32] if rule else "Regla de negocio"
    body_parts = [params.get("message", "")]
    if rule and rule.description:
        body_parts.insert(0, rule.description)
    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = _truncate(" ".join(p for p in body_parts if p))
    return dv


def build_date_after_column_validation(
    own_column_letter: str,
    after_column_letter: str,
    after_column_name: str = "",
    strict: bool = False,
) -> DataValidation:
    """Valida la fecha contra otra columna de la misma fila."""

    operator = ">" if strict else ">="

    dv = DataValidation(
        type="custom",
        formula1=(
            f"=OR(ISBLANK({own_column_letter}2),"
            f"{own_column_letter}2{operator}{after_column_letter}2)"
        ),
    )

    dv.allow_blank = True
    dv.showErrorMessage = True
    dv.errorTitle = "Regla de negocio"

    if strict:
        dv.error = "La fecha final debe ser posterior a la fecha de inicio."
        comparison_text = "posterior"
    else:
        dv.error = "La fecha final debe ser igual o posterior a la fecha de inicio."
        comparison_text = "igual o posterior"

    dv.showInputMessage = True
    dv.promptTitle = "Fecha final"
    dv.prompt = (
        f"Debe ser {comparison_text} a la fecha en "
        f"'{after_column_name}' de la misma fila."
        if after_column_name
        else f"Debe ser {comparison_text} a la fecha de inicio de la misma fila."
    )

    return dv
