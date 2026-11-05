
"""Orquesta la validación post-hoc de un archivo SNIES ya diligenciado.

Reutiliza el motor de reglas de la configuración para mantener alineadas
las validaciones de las plantillas y las validaciones posteriores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openpyxl.workbook.workbook import Workbook

from excel_io.reader import iter_data_sheets, read_headers
from rules.config_loader import (
    load_rule_configuration,
    resolve_business_rule,
    get_global_business_rules,
)
from rules.interpreter import interpret_comment
from rules.models import ValidationRule
from validators.cross_row_validator import (
    check_code_consistency,
    check_uniqueness,
)
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
    """Valida todas las hojas de datos de un libro de Excel."""

    configuration = load_rule_configuration()

    business_rules = configuration.business_rules
    global_business_rules = get_global_business_rules(configuration)

    results: list[SheetValidationResult] = []

    # Recorrer cada hoja de datos del libro.
    for ws in iter_data_sheets(workbook):

        headers = read_headers(ws)

        if not headers:
            continue

        # Interpretar las reglas definidas en los comentarios de los encabezados.
        rules_by_column: dict[str, ValidationRule] = {
            header.column_name: interpret_comment(
                header.column_name,
                header.comment_text,
            )
            for header in headers
        }

        column_letter_by_name = {
            header.column_name: header.column_letter
            for header in headers
        }

        columns_needing_review = [
            column_name
            for column_name, rule in rules_by_column.items()
            if rule.needs_manual_review
        ]

        max_row = ws.max_row

        result = SheetValidationResult(
            sheet_name=ws.title,
            total_rows=max(max_row - HEADER_ROW, 0),
        )

        result.columns_needing_review = columns_needing_review

        # Recopilar las filas como diccionarios.
        # Esto permite consultar otras columnas de la misma fila
        # y comparar información entre diferentes filas.
        row_dicts: list[dict[str, object]] = []
        row_numbers: list[int] = []

        for row_idx in range(HEADER_ROW + 1, max_row + 1):

            row_values: dict[str, object] = {}
            is_empty_row = True

            for header in headers:

                cell = ws[f"{header.column_letter}{row_idx}"]

                row_values[header.column_name] = cell.value

                if (
                    cell.value is not None
                    and str(cell.value).strip() != ""
                ):
                    is_empty_row = False

            # Ignorar filas completamente vacías.
            if is_empty_row:
                continue

            row_dicts.append(row_values)
            row_numbers.append(row_idx)

        # ---------------------------------------------------------
        # 1. Validaciones por celda y reglas de negocio por fila.
        # ---------------------------------------------------------
        for row_values, row_idx in zip(row_dicts, row_numbers):

            for col_name, value in row_values.items():

                # Validaciones interpretadas desde los comentarios.
                rule = rules_by_column[col_name]

                for issue in validate_cell(rule, value):

                    result.issues.append(
                        RowIssue(
                            sheet=ws.title,
                            row=row_idx,
                            column_name=col_name,
                            value=value,
                            message=issue.message,
                            severity=issue.severity,
                        )
                    )

                # Resolver la regla de negocio correspondiente
                # a la hoja y a la columna actual.
                biz = resolve_business_rule(
                    configuration,
                    column_name=col_name,
                    sheet_name=ws.title,
                )

                # Las reglas de consistencia entre filas y unicidad
                # se procesan en secciones independientes.
                if biz and biz.get("kind") not in (
                    None,
                    "cross_row_consistency_note",
                    "unique_in_sheet",
                ):

                    business_issues = validate_business_rule(
                        biz["kind"],
                        biz,
                        value,
                        row_values,
                    )

                    for issue in business_issues:

                        result.issues.append(
                            RowIssue(
                                sheet=ws.title,
                                row=row_idx,
                                column_name=col_name,
                                value=value,
                                message=issue.message,
                                severity=issue.severity,
                            )
                        )

        # ---------------------------------------------------------
        # 2. Consistencia entre filas.
        # ---------------------------------------------------------
        for col_name, biz in global_business_rules.items():

            if biz.get("kind") != "cross_row_consistency_note":
                continue

            check_columns = biz.get("check_columns", [])

            # La regla solo aplica cuando la hoja contiene
            # el código y todas las columnas que deben compararse.
            if col_name not in column_letter_by_name:
                continue

            if (
                not check_columns
                or not all(
                    column in column_letter_by_name
                    for column in check_columns
                )
            ):
                continue

            group_by = biz.get("group_by")

            if group_by and group_by not in column_letter_by_name:
                group_by = None

            consistency_issues = check_code_consistency(
                col_name,
                check_columns,
                row_dicts,
                row_numbers,
                group_by,
            )

            for cross_issue in consistency_issues:

                idx = row_numbers.index(cross_issue.row)

                result.issues.append(
                    RowIssue(
                        sheet=ws.title,
                        row=cross_issue.row,
                        column_name=cross_issue.column_name,
                        value=row_dicts[idx].get(
                            cross_issue.column_name
                        ),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

        # ---------------------------------------------------------
        # 3. Reglas de unicidad específicas de cada hoja.
        # ---------------------------------------------------------
        for col_name in column_letter_by_name:

            cfg = resolve_business_rule(
                configuration,
                column_name=col_name,
                sheet_name=ws.title,
            )

            if not cfg or cfg.get("kind") != "unique_in_sheet":
                continue

            uniqueness_issues = check_uniqueness(
                col_name,
                row_dicts,
                row_numbers,
                severity=cfg.get("severity", "warning"),
                message_template=cfg.get("message"),
            )

            for cross_issue in uniqueness_issues:

                idx = row_numbers.index(cross_issue.row)

                result.issues.append(
                    RowIssue(
                        sheet=ws.title,
                        row=cross_issue.row,
                        column_name=cross_issue.column_name,
                        value=row_dicts[idx].get(
                            cross_issue.column_name
                        ),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

        # Guardar el resultado de esta hoja.
        # Debe ejecutarse dentro del recorrido de las hojas.
        results.append(result)

    return results
