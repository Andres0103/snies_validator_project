"""Orquesta la validación post-hoc de un archivo SNIES ya diligenciado.

Reutiliza exactamente el mismo motor de reglas que genera las plantillas
(`rules/interpreter.py`, `rules/known_fields.py`, `rules/business_rules.py`),
así que las reglas nunca se desalinean entre "lo que se previene al
escribir" y "lo que se detecta después de escrito".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openpyxl.workbook.workbook import Workbook

from excel_io.reader import iter_data_sheets, read_headers
from rules import business_rules
from rules.business_rules import load_business_rules
from rules.interpreter import interpret_comment
from rules.models import ValidationRule
from validators.cross_row_validator import check_code_consistency, check_uniqueness
from validators.row_validator import validate_business_rule, validate_cell

HEADER_ROW = 1


@dataclass
class RowIssue:
    sheet: str
    row: int
    column_name: str
    value: object
    message: str
    severity: str = "error"


@dataclass
class SheetValidationResult:
    sheet_name: str
    total_rows: int
    columns_needing_review: list[str] = field(default_factory=list)
    issues: list[RowIssue] = field(default_factory=list)

def _condition_matches(
    condition: dict,
    row_values: dict[str, object],
) -> bool:
    """Evalúa una condición configurada en business_rules.yaml."""

    if "any" in condition:
        return any(
            _condition_matches(item, row_values)
            for item in condition["any"]
        )

    if "all" in condition:
        return all(
            _condition_matches(item, row_values)
            for item in condition["all"]
        )

    column = condition.get("column")
    operator = condition.get("operator", "not_blank")
    value = row_values.get(column)

    blank = value is None or (
        isinstance(value, str) and value.strip() == ""
    )

    if operator == "not_blank":
        return not blank

    if operator == "blank":
        return blank

    if operator == "gt":
        try:
            return (
                not blank
                and float(str(value).replace(",", ""))
                > float(condition.get("value", 0))
            )
        except (TypeError, ValueError):
            return False

    if operator == "eq":
        return (
            not blank
            and str(value).strip()
            == str(condition.get("value", ""))
        )

    if operator == "in":
        return (
            not blank
            and str(value).strip()
            in {str(v) for v in condition.get("values", [])}
        )

    return False


def _conditional_requirement_applies(
    rules: dict,
    sheet_name: str,
    column_name: str,
    row_values: dict[str, object],
) -> bool | None:
    """Retorna True/False si hay condición configurada; None si no existe."""

    sheet_rules = rules.get(
        "conditional_required_fields", {}
    ).get(sheet_name, {})

    config = sheet_rules.get(column_name)

    if not config:
        return None

    return _condition_matches(
        config.get("when", {}),
        row_values,
    )

def validate_workbook(workbook: Workbook) -> list[SheetValidationResult]:
    business_rules = load_business_rules()
    results: list[SheetValidationResult] = []

    for ws in iter_data_sheets(workbook):
        headers = read_headers(ws)
        if not headers:
            continue

        rules_by_column: dict[str, ValidationRule] = {
            h.column_name: interpret_comment(h.column_name, h.comment_text) for h in headers
        }
        column_letter_by_name = {h.column_name: h.column_letter for h in headers}
        columns_needing_review = [c for c, r in rules_by_column.items() if r.needs_manual_review]

        max_row = ws.max_row
        result = SheetValidationResult(sheet_name=ws.title, total_rows=max(max_row - HEADER_ROW, 0))
        result.columns_needing_review = columns_needing_review

        # Recolectar filas de datos como diccionarios {columna: valor} para
        # poder validar reglas que dependen de OTRA celda de la misma fila
        # (ej. FECHA_FINAL > FECHA_INICIO) y para el chequeo de
        # consistencia entre filas.
        row_dicts: list[dict[str, object]] = []
        row_numbers: list[int] = []
        for row_idx in range(HEADER_ROW + 1, max_row + 1):
            row_values = {}
            is_empty_row = True
            for h in headers:
                cell = ws[f"{h.column_letter}{row_idx}"]
                row_values[h.column_name] = cell.value
                if cell.value is not None and str(cell.value).strip() != "":
                    is_empty_row = False
            if is_empty_row:
                continue
            row_dicts.append(row_values)
            row_numbers.append(row_idx)

        # --- Validación por celda ---
        for row_values, row_idx in zip(row_dicts, row_numbers):
            for col_name, value in row_values.items():
                rule = rules_by_column[col_name]

                condition_applies = _conditional_requirement_applies(
                    business_rules,
                    ws.title,
                    col_name,
                    row_values,
                )

                for issue in validate_cell(
                    rule,
                    value,
                    condition_applies,
                ):
                    result.issues.append(
                        RowIssue(
                            ws.title,
                            row_idx,
                            col_name,
                            value,
                            issue.message,
                            issue.severity,
                        )
                    )

                biz = business_rules.get(col_name)

                if biz and biz.get("kind") not in (
                    None,
                    "cross_row_consistency_note",
                ):
                    for issue in validate_business_rule(
                        biz["kind"],
                        biz,
                        value,
                        row_values,
                    ):
                        result.issues.append(
                            RowIssue(
                                ws.title,
                                row_idx,
                                col_name,
                                value,
                                issue.message,
                                issue.severity,
                            )
                        )

        # --- Consistencia entre filas (unicidad de un código) ---
        for col_name, biz in business_rules.items():
            if biz.get("kind") != "cross_row_consistency_note":
                continue
            check_columns = biz.get("check_columns", [])
            # Solo aplica en la hoja que realmente tiene el código Y todas
            # las columnas que se van a comparar (esto excluye de forma
            # natural a hojas hijas/detalle que no las tienen, ej. la
            # hoja de recurso humano no tiene DESCRIPCION_CONSULTORIA).
            if col_name not in column_letter_by_name:
                continue
            if not check_columns or not all(c in column_letter_by_name for c in check_columns):
                continue
            group_by = biz.get("group_by")
            if group_by and group_by not in column_letter_by_name:
                group_by = None
            for cri in check_code_consistency(col_name, check_columns, row_dicts, row_numbers, group_by):
                idx = row_numbers.index(cri.row)
                result.issues.append(
                    RowIssue(
                        ws.title, cri.row, cri.column_name,
                        row_dicts[idx].get(cri.column_name),
                        cri.message, cri.severity,
                    )
                )

        # --- Reglas específicas de hoja+columna (ej. código único) ---
        sheet_scoped = business_rules.get("sheet_scoped_rules", {}).get(ws.title, {})
        for col_name, cfg in sheet_scoped.items():
            if cfg.get("kind") != "unique_in_sheet":
                continue
            if col_name not in column_letter_by_name:
                continue
            for cri in check_uniqueness(
                col_name, row_dicts, row_numbers,
                severity=cfg.get("severity", "warning"),
                message_template=cfg.get("message"),
            ):
                idx = row_numbers.index(cri.row)
                result.issues.append(
                    RowIssue(
                        ws.title, cri.row, cri.column_name,
                        row_dicts[idx].get(cri.column_name),
                        cri.message, cri.severity,
                    )
                )

        results.append(result)

    return results
