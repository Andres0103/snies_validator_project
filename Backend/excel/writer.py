"""Orquesta la generación de una plantilla con validación nativa aplicada.

Flujo por workbook:
1. Leer encabezados de cada hoja de datos e interpretar sus comentarios.
2. Recolectar (deduplicadas por nombre de columna) las reglas que traen
   lista de valores permitidos, y construir la hoja auxiliar oculta una
   sola vez para todo el workbook.
3. Para cada hoja, para cada columna: construir la(s) DataValidation
   correspondientes (tipo/longitud o lista) + las reglas de negocio
   adicionales del catálogo (rules/patterns/business_rules.yaml), y
   aplicarlas al rango de filas de datos.
4. Guardar el archivo. No se toca ninguna celda de encabezado, ningún
   comentario, ni ningún formato existente: solo se agregan objetos
   DataValidation y (cuando aplica) una hoja auxiliar oculta nueva.
"""

from __future__ import annotations

from dataclasses import dataclass

from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.workbook.workbook import Workbook

from excel.reader import HeaderCell, iter_data_sheets, read_headers
from rules.business_rules import load_business_rules
from rules.interpreter import interpret_comment
from backend.rules.general_model import ValidationRule
from excel.excel_validation_builder import (
    build_business_rule_validation,
    build_date_after_column_validation,
    build_list_validation,
    build_type_validation,
)
from excel.helper_sheets import build_helper_sheet

DATA_ROWS_TO_COVER = 2000  # filas cubiertas por la validación (más que suficiente para cargues manuales)


@dataclass
class ColumnReport:
    sheet_name: str
    column_name: str
    rule: ValidationRule
    validations_applied: list[str]
    needs_review: bool


def _dedup_rules_with_lists(all_headers: list[HeaderCell], rules_by_key: dict) -> list[ValidationRule]:
    seen: dict[str, ValidationRule] = {}
    for h in all_headers:
        rule = rules_by_key[(h.sheet_name, h.column_name)]
        if rule.allowed_values and rule.column_name not in seen:
            seen[rule.column_name] = rule
    return list(seen.values())


def process_workbook(workbook: Workbook) -> list[ColumnReport]:
    """Aplica validaciones a todas las hojas de datos del workbook. Devuelve un reporte."""
    business_rules = load_business_rules()
    reports: list[ColumnReport] = []

    data_sheets = iter_data_sheets(workbook)

    # --- Paso 1: interpretar todos los comentarios primero ---
    all_headers: list[HeaderCell] = []
    rules_by_key: dict[tuple[str, str], ValidationRule] = {}
    for ws in data_sheets:
        headers = read_headers(ws)
        all_headers.extend(headers)
        for h in headers:
            rule = interpret_comment(h.column_name, h.comment_text)
            rules_by_key[(h.sheet_name, h.column_name)] = rule

    # --- Paso 2: hoja auxiliar oculta con TODAS las listas del workbook ---
    unique_list_rules = _dedup_rules_with_lists(all_headers, rules_by_key)
    defined_names = build_helper_sheet(workbook, unique_list_rules)

    # --- Paso 3: letras de columna por hoja (para reglas que referencian otra columna) ---
    column_letters_by_sheet: dict[str, dict[str, str]] = {}
    for ws in data_sheets:
        column_letters_by_sheet[ws.title] = {
            h.column_name: h.column_letter for h in read_headers(ws)
        }

    # --- Paso 4: construir y aplicar validaciones ---
    # IMPORTANTE: Excel no soporta de forma confiable dos DataValidation
    # distintas superpuestas sobre el mismo rango de celdas (comportamiento
    # indefinido / normalmente solo se respeta una). Por eso, para cada
    # columna se elige UNA sola validación "principal" con esta prioridad:
    #   1) Lista desplegable (si el comentario trae valores permitidos)
    #   2) Regla de negocio del manual MEN, si es más específica que el
    #      tipo genérico (ej. "fecha dentro de los últimos 80 años" en vez
    #      de solo "es una fecha")
    #   3) Tipo/longitud genérico derivado del comentario
    # Las reglas que comparan entre FILAS distintas (ej. unicidad de
    # CODIGO_CONSULTORIA) no son expresables como DataValidation nativa;
    # quedan documentadas en el reporte para el validador post-hoc.
    for ws in data_sheets:
        headers = [h for h in all_headers if h.sheet_name == ws.title]
        for h in headers:
            rule = rules_by_key[(h.sheet_name, h.column_name)]
            applied: list[str] = []
            data_range = f"{h.column_letter}2:{h.column_letter}{DATA_ROWS_TO_COVER}"
            biz = business_rules.get(rule.column_name)
            biz_kind = biz.get("kind") if biz else None

            dv = None
            if rule.allowed_values:
                defined_name = defined_names.get(rule.column_name)
                if defined_name:
                    dv = build_list_validation(rule, defined_name)
                    applied.append("lista_desplegable")

            elif biz_kind == "date_after_column":
                after_col_name = biz.get("after_column")
                after_letter = column_letters_by_sheet[ws.title].get(after_col_name)
                if after_letter:
                    dv = build_date_after_column_validation(h.column_letter, after_letter, after_col_name)
                    applied.append("regla_negocio:fecha_posterior_a_" + after_col_name)

            elif biz_kind in ("non_negative", "non_negative_with_min_length", "email_format", "date_within_past_years"):
                dv = build_business_rule_validation(biz_kind, biz, h.column_letter, rule)
                if dv:
                    applied.append(f"regla_negocio:{biz_kind}")

            if dv is None:
                dv = build_type_validation(rule, h.column_letter)
                if dv:
                    applied.append(f"tipo:{rule.datatype.value}")

            if dv:
                ws.add_data_validation(dv)
                dv.add(data_range)

            # Reglas que el catálogo documenta pero que no producen una
            # DataValidation (comparan entre filas/hojas distintas).
            if biz_kind == "cross_row_consistency_note":
                applied.append("nota:consistencia_entre_filas (no enforceable nativamente, ver validador post-hoc)")

            reports.append(
                ColumnReport(
                    sheet_name=ws.title,
                    column_name=rule.column_name,
                    rule=rule,
                    validations_applied=applied,
                    needs_review=rule.needs_manual_review,
                )
            )

    return reports
