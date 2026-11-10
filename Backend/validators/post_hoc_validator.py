"""Orquesta la validación post-hoc de un archivo SNIES.

Integra:
- Reglas de campos definidas en rules.yaml.
- Restricciones ejecutables definidas en validations.yaml.
- Reglas de negocio definidas en business_rules.yaml.
- Catálogos definidos en catalogs.yaml.
- Perfiles estructurales de las plantillas.
- Validaciones entre filas y entre hojas.

Mantiene compatibilidad con las plantillas que todavía utilizan
la configuración YAML anterior.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl.workbook.workbook import Workbook

from excel.reader import iter_data_sheets, read_headers

from rules.config_loader import (
    load_rule_configuration,
    resolve_business_rule,
    get_global_business_rules,
)
from rules.catalog_loader import load_catalog
from rules.interpreter import interpret_comment
from backend.rules.general_model import DataType, ValidationRule
from rules.template_profiles import (
    detect_templates,
    load_template_profiles,
)

from validators.cross_row_validator import (
    check_code_consistency,
    check_uniqueness,
)
from validators.cross_sheet_validator import validate_sheet_references
from validators.row_validator import (
    validate_business_rule,
    validate_cell,
)
from validators.structure_validator import validate_sheet_headers


HEADER_ROW = 1


@dataclass
class RowIssue:
    """Representa una incidencia encontrada en una fila."""

    sheet: str
    row: int
    column_name: str
    value: object
    message: str
    severity: str = "error"


@dataclass
class SheetValidationResult:
    """Resultado de validación de una hoja."""

    sheet_name: str
    total_rows: int
    columns_needing_review: list[str] = field(default_factory=list)
    issues: list[RowIssue] = field(default_factory=list)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _is_blank(value: Any) -> bool:
    """Determina si un valor está vacío."""

    return value is None or (
        isinstance(value, str) and value.strip() == ""
    )


def _to_decimal(value: Any) -> Decimal | None:
    """Convierte un valor numérico a Decimal."""

    if isinstance(value, bool):
        return None


    if isinstance(value, (int, float, Decimal)):
        try:
            num = Decimal(str(value))
            
            if num.is_finite(): 
                return num
            else:
                return None
        
        except InvalidOperation:
            return None

    if isinstance(value, str):
        try:
            num = Decimal(value.strip())

            if num.is_finite():
                return num
            else:
                return None
            
        except InvalidOperation:
            return None

    return None


def _to_date(
    value: Any,
    formats: list[str] | None = None,
) -> datetime.date | None:
    """Convierte fechas de Excel o texto a datetime.date."""

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    if isinstance(value, str):
        for date_format in formats or [
            "%d-%m-%Y",
            "%d/%m/%Y",
        ]:
            try:
                return datetime.datetime.strptime(
                    value.strip(),
                    date_format,
                ).date()
            except ValueError:
                continue

    return None


def _normalize_date_formats(
    configured_format: Any,
) -> list[str]:
    """Normaliza el formato de fecha definido en validations.yaml."""

    if isinstance(configured_format, str):
        return [configured_format]

    if isinstance(configured_format, list):
        return [
            item
            for item in configured_format
            if isinstance(item, str)
        ]

    return []


# ============================================================
# CONDICIONES DE OBLIGATORIEDAD
# ============================================================

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

    blank = _is_blank(value)

    if operator == "not_blank":
        return not blank

    if operator == "blank":
        return blank

    if operator == "gt":
        number = _to_decimal(value)

        if number is None:
            return False

        expected = _to_decimal(condition.get("value", 0))

        return (
            expected is not None
            and number > expected
        )

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
            in {
                str(item)
                for item in condition.get("values", [])
            }
        )

    return False


def _conditional_requirement_applies(
    rules: dict,
    sheet_name: str,
    column_name: str,
    row_values: dict[str, object],
) -> bool | None:
    """Retorna True/False si hay condición configurada; None si no existe."""

    conditional_rules = rules.get(
        "conditional_required_fields",
        {},
    )

    sheet_rules = conditional_rules.get(sheet_name, {})
    config = sheet_rules.get(column_name)

    if not config:
        return None

    return _condition_matches(
        config.get("when", {}),
        row_values,
    )


# ============================================================
# RESTRICCIONES DE validations.yaml
# ============================================================

def _validate_configured_constraints(
    column_name: str,
    value: Any,
    validation: dict[str, Any],
    row_values: dict[str, Any],
) -> list[tuple[str, str]]:
    """
    Ejecuta las restricciones configuradas en validations.yaml.

    Retorna una lista de tuplas:
        (mensaje, severidad)
    """

    issues: list[tuple[str, str]] = []

    if _is_blank(value):
        return issues

    # --------------------------------------------------------
    # 1. Expresiones regulares.
    # --------------------------------------------------------

    pattern = validation.get("pattern")

    if pattern:
        try:
            if not re.fullmatch(
                pattern,
                str(value).strip(),
            ):
                issues.append(
                    (
                        "El valor no cumple con el patrón "
                        f"permitido: {pattern}.",
                        "error",
                    )
                )
        except re.error as exc:
            raise ValueError(
                f"Expresión regular inválida para "
                f"'{column_name}': {exc}"
            ) from exc

    # --------------------------------------------------------
    # 2. Límites numéricos.
    # --------------------------------------------------------

    minimum = validation.get("min_value")
    maximum = validation.get("max_value")

    if minimum is not None or maximum is not None:
        number = _to_decimal(value)

        if number is not None:

            if minimum is not None:
                min_number = _to_decimal(minimum)

                if (
                    min_number is not None
                    and number < min_number
                ):
                    issues.append(
                        (
                            f"El valor debe ser mayor o igual "
                            f"a {minimum}.",
                            "error",
                        )
                    )

            if maximum is not None:
                max_number = _to_decimal(maximum)

                if (
                    max_number is not None
                    and number > max_number
                ):
                    issues.append(
                        (
                            f"El valor debe ser menor o igual "
                            f"a {maximum}.",
                            "error",
                        )
                    )

    # --------------------------------------------------------
    # 3. Antigüedad permitida de una fecha.
    # --------------------------------------------------------

    years = validation.get("date_within_past_years")

    if years is not None:
        parsed_date = _to_date(
            value,
            _normalize_date_formats(
                validation.get("format")
            ),
        )

        if parsed_date is not None:
            today = datetime.date.today()

            try:
                earliest_date = today.replace(
                    year=today.year - int(years)
                )
            except ValueError:
                # Maneja el caso del 29 de febrero.
                earliest_date = today.replace(
                    year=today.year - int(years),
                    day=28,
                )

            if not earliest_date <= parsed_date <= today:
                issues.append(
                    (
                        f"La fecha debe estar comprendida "
                        f"entre {earliest_date.strftime('%d-%m-%Y')} "
                        f"y {today.strftime('%d-%m-%Y')}.",
                        "error",
                    )
                )

    return issues


# ============================================================
# CONFIGURACIÓN DE CADA HOJA
# ============================================================

def _get_sheet_configuration(
    configuration: Any,
    sheet_name: str,
) -> dict[str, Any]:
    """
    Obtiene reglas, validaciones y catálogos de una hoja.

    Para configuraciones nuevas utiliza sheet_configurations.
    Para configuraciones antiguas utiliza validation_config.
    """

    sheet_configurations = getattr(
        configuration,
        "sheet_configurations",
        {},
    )

    if sheet_name in sheet_configurations:
        return sheet_configurations[sheet_name]

    # Compatibilidad con la configuración antigua.
    return {
        "rules": configuration.known_fields,
        "validations": configuration.validation_config.get(
            "column_rules",
            {},
        ),
        "catalogs": configuration.validation_config.get(
            "master_tables",
            {},
        ),
    }


def _build_column_rules(
    headers: list,
    sheet_name: str,
    sheet_configuration: dict[str, Any],
    configuration: Any,
) -> tuple[
    dict[str, ValidationRule],
    dict[str, dict[str, Any]],
]:
    """
    Construye las reglas interpretadas de las columnas.

    Integra comentarios de Excel, rules.yaml, validations.yaml
    y los catálogos correspondientes.
    """

    rules_by_column: dict[str, ValidationRule] = {}

    validations_by_column = sheet_configuration.get(
        "validations",
        {},
    )

    catalogs = sheet_configuration.get(
        "catalogs",
        {},
    )

    for header in headers:

        column_name = header.column_name

        # ----------------------------------------------------
        # 1. Interpretar el comentario y completar reglas.
        # ----------------------------------------------------

        rule = interpret_comment(
            column_name,
            header.comment_text,
            known_fields=configuration.known_fields,
            sheet_name=sheet_name,
        )

        # ----------------------------------------------------
        # 2. Obtener restricciones de validations.yaml.
        # ----------------------------------------------------

        validation = validations_by_column.get(
            column_name,
            {},
        )

        # El formato configurado complementa el tipo DATE.
        configured_formats = _normalize_date_formats(
            validation.get("format")
        )

        if configured_formats:
            rule.date_formats = configured_formats

        # ----------------------------------------------------
        # 3. Cargar el catálogo asociado al campo.
        # ----------------------------------------------------

        catalog_name = validation.get("catalog")

        if catalog_name:
            catalog_config = catalogs.get(catalog_name)

            if catalog_config is None:
                raise ValueError(
                    f"La columna '{column_name}' de la hoja "
                    f"'{sheet_name}' referencia el catálogo "
                    f"'{catalog_name}', pero no está definido "
                    "en catalogs.yaml."
                )

            rule.allowed_values = load_catalog(
                catalog_config,
                catalog_name,
            )

        rules_by_column[column_name] = rule

    return rules_by_column, validations_by_column


# ============================================================
# VALIDACIÓN PRINCIPAL
# ============================================================

def validate_workbook(
    workbook: Workbook,
) -> list[SheetValidationResult]:
    """Valida todas las hojas de datos de un libro de Excel."""

    results: list[SheetValidationResult] = []

    # ---------------------------------------------------------
    # 1. Identificar la plantilla del libro.
    # ---------------------------------------------------------

    detected_templates = detect_templates(
        workbook.sheetnames
    )

    if len(detected_templates) == 0:
        return [
            SheetValidationResult(
                sheet_name="ESTRUCTURA_LIBRO",
                total_rows=0,
                issues=[
                    RowIssue(
                        sheet="ESTRUCTURA_LIBRO",
                        row=1,
                        column_name="PLANTILLA",
                        value=None,
                        message=(
                            "No fue posible identificar la plantilla "
                            "SNIES. Verifica que el archivo contenga "
                            "la hoja principal de una plantilla "
                            "soportada."
                        ),
                    )
                ],
            )
        ]

    if len(detected_templates) > 1:
        return [
            SheetValidationResult(
                sheet_name="ESTRUCTURA_LIBRO",
                total_rows=0,
                issues=[
                    RowIssue(
                        sheet="ESTRUCTURA_LIBRO",
                        row=1,
                        column_name="PLANTILLA",
                        value=", ".join(detected_templates),
                        message=(
                            "El archivo contiene hojas principales "
                            "de más de una plantilla SNIES: "
                            f"{', '.join(detected_templates)}. "
                            "Cada archivo debe corresponder a una "
                            "sola plantilla."
                        ),
                    )
                ],
            )
        ]

    template_name = detected_templates[0]

    # ---------------------------------------------------------
    # 2. Cargar la configuración correspondiente.
    # ---------------------------------------------------------

    # Las plantillas migradas utilizan la nueva arquitectura.
    # Las que todavía no tienen directorio propio conservan
    # temporalmente la configuración anterior.

    template_directory = (
        Path(__file__).resolve().parents[1]
        / "rules"
        / "patterns"
        / "templates"
        / template_name.lower()
    )

    if template_directory.exists():
        configuration = load_rule_configuration(
            template_name=template_name
        )
    else:
        configuration = load_rule_configuration()

    business_rules = configuration.business_rules

    global_business_rules = get_global_business_rules(
        configuration
    )

    # ---------------------------------------------------------
    # 3. Obtener el perfil estructural.
    # ---------------------------------------------------------

    profiles = load_template_profiles()

    template_profile = profiles["templates"].get(
        template_name
    )

    if template_profile is None:
        raise ValueError(
            f"No existe un perfil estructural para "
            f"la plantilla '{template_name}'."
        )

    expected_sheets = template_profile.get(
        "sheets",
        [],
    )

    expected_sheet_set = set(expected_sheets)

    data_sheets = iter_data_sheets(workbook)

    present_sheet_names = {
        ws.title
        for ws in data_sheets
    }

    unexpected_sheets = (
        present_sheet_names - expected_sheet_set
    )

    if unexpected_sheets:
        results.append(
            SheetValidationResult(
                sheet_name="ESTRUCTURA_LIBRO",
                total_rows=0,
                issues=[
                    RowIssue(
                        sheet="ESTRUCTURA_LIBRO",
                        row=1,
                        column_name="HOJAS",
                        value=", ".join(sorted(unexpected_sheets)),
                        message=(
                            "El archivo contiene hojas de datos "
                            "que no pertenecen a la plantilla "
                            f"{template_name}: "
                            f"{', '.join(sorted(unexpected_sheets))}."
                        ),
                    )
                ],
            )
        )

    # ---------------------------------------------------------
    # 4. Determinar las hojas que deben validarse.
    # ---------------------------------------------------------

    sheets_to_validate = [
        ws
        for ws in data_sheets
        if ws.title in expected_sheet_set
    ]

    # ---------------------------------------------------------
    # 5. Validar cada hoja.
    # ---------------------------------------------------------

    for ws in sheets_to_validate:

        headers = read_headers(ws)

        if not headers:
            continue

        sheet_configuration = _get_sheet_configuration(
            configuration,
            ws.title,
        )

        # -----------------------------------------------------
        # 5.1. Construir reglas de las columnas.
        # -----------------------------------------------------

        rules_by_column, validations_by_column = (
            _build_column_rules(
                headers,
                ws.title,
                sheet_configuration,
                configuration,
            )
        )

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

        result.columns_needing_review = (
            columns_needing_review
        )

        # -----------------------------------------------------
        # 5.2. Validaciones estructurales de encabezados.
        # -----------------------------------------------------

        header_issues = validate_sheet_headers(ws)

        for issue in header_issues:
            result.issues.append(
                RowIssue(
                    sheet=ws.title,
                    row=issue["row"],
                    column_name=issue["column_name"],
                    value=issue["value"],
                    message=issue["message"],
                    severity=issue["severity"],
                )
            )

        has_invalid_headers = any(
            "duplicado" in issue["message"].lower()
            or "encabezado vacío" in issue["message"].lower()
            for issue in header_issues
        )

        if has_invalid_headers:
            results.append(result)
            continue

        # -----------------------------------------------------
        # 5.3. Recopilar las filas como diccionarios.
        # -----------------------------------------------------

        row_dicts: list[dict[str, object]] = []
        row_numbers: list[int] = []

        for row_idx in range(
            HEADER_ROW + 1,
            max_row + 1,
        ):

            row_values: dict[str, object] = {}
            is_empty_row = True

            for header in headers:

                cell = ws[
                    f"{header.column_letter}{row_idx}"
                ]

                row_values[header.column_name] = cell.value

                if not _is_blank(cell.value):
                    is_empty_row = False

            if is_empty_row:
                continue

            row_dicts.append(row_values)
            row_numbers.append(row_idx)

        # -----------------------------------------------------
        # 5.4. Validaciones por celda y reglas de negocio.
        # -----------------------------------------------------

        for row_values, row_idx in zip(
            row_dicts,
            row_numbers,
        ):

            for col_name, value in row_values.items():

                rule = rules_by_column[col_name]

                validation = validations_by_column.get(
                    col_name,
                    {},
                )

                # ---------------------------------------------
                # A. Obligatoriedad condicional.
                # ---------------------------------------------

                conditional_applies = (
                    _conditional_requirement_applies(
                        business_rules,
                        ws.title,
                        col_name,
                        row_values,
                    )
                )

                # ---------------------------------------------
                # B. Tipo de dato, longitud y catálogo.
                # ---------------------------------------------

                cell_issues = validate_cell(
                    rule,
                    value,
                    conditional_applies=conditional_applies,
                )

                for issue in cell_issues:
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

                # ---------------------------------------------
                # C. Restricciones de validations.yaml.
                # ---------------------------------------------

                configured_issues = (
                    _validate_configured_constraints(
                        col_name,
                        value,
                        validation,
                        row_values,
                    )
                )

                for message, severity in configured_issues:
                    result.issues.append(
                        RowIssue(
                            sheet=ws.title,
                            row=row_idx,
                            column_name=col_name,
                            value=value,
                            message=message,
                            severity=severity,
                        )
                    )

                # ---------------------------------------------
                # D. Reglas de negocio por campo.
                # ---------------------------------------------

                business_rule = resolve_business_rule(
                    configuration,
                    column_name=col_name,
                    sheet_name=ws.title,
                )

                if (
                    business_rule
                    and business_rule.get("kind") not in (
                        None,
                        "cross_row_consistency_note",
                        "unique_in_sheet",
                    )
                ):
                    business_issues = validate_business_rule(
                        business_rule["kind"],
                        business_rule,
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

        # -----------------------------------------------------
        # 5.5. Consistencia entre filas.
        # -----------------------------------------------------

        # Construir el diccionario con el tipo de dato de cada columna.
        # Se calcula una sola vez porque sirve para todas las reglas
        # de consistencia y unicidad de esta hoja.
        column_types = {
            column_name: rule.datatype
            for column_name, rule in rules_by_column.items()
        }

        # Relacionar cada número real de fila de Excel con sus valores.
        # Esto permite recuperar los datos originales cuando se genera
        # una incidencia entre filas.
        row_values_by_number = {
            number: values
            for number, values in zip(row_numbers, row_dicts)
        }

        for col_name, business_rule in global_business_rules.items():

            if business_rule.get("kind") != "cross_row_consistency_note":
                continue

            check_columns = business_rule.get("check_columns", [])

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

            group_by = business_rule.get("group_by")

            if group_by and group_by not in column_letter_by_name:
                group_by = None

            # Ejecutar la validación entre filas.
            consistency_issues = check_code_consistency(
                col_name,
                check_columns,
                row_dicts,
                row_numbers,
                column_types,
                group_by,
            )

            # Incorporar las incidencias al resultado de la hoja.
            for cross_issue in consistency_issues:

                row_values = row_values_by_number.get(
                    cross_issue.row,
                    {},
                )

                result.issues.append(
                    RowIssue(
                        sheet=ws.title,
                        row=cross_issue.row,
                        column_name=cross_issue.column_name,
                        value=row_values.get(
                            cross_issue.column_name
                        ),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

        # -----------------------------------------------------
        # 5.6. Reglas de unicidad de cada hoja.
        # -----------------------------------------------------

        for col_name in column_letter_by_name:

            business_rule = resolve_business_rule(
                configuration,
                column_name=col_name,
                sheet_name=ws.title,
            )

            if (
                not business_rule
                or business_rule.get("kind") != "unique_in_sheet"
            ):
                continue

            uniqueness_issues = check_uniqueness(
                col_name,
                row_dicts,
                row_numbers,
                column_types=column_types,
                severity=business_rule.get(
                    "severity",
                    "warning",
                ),
                message_template=business_rule.get("message"),
            )

            for cross_issue in uniqueness_issues:

                row_values = row_values_by_number.get(
                    cross_issue.row,
                    {},
                )

                result.issues.append(
                    RowIssue(
                        sheet=ws.title,
                        row=cross_issue.row,
                        column_name=cross_issue.column_name,
                        value=row_values.get(
                            cross_issue.column_name
                        ),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

    # ---------------------------------------------------------
    # 6. Validaciones referenciales entre hojas.
    # ---------------------------------------------------------

    reference_issues = validate_sheet_references(
        workbook,
        template_name=template_name,
    )

    for issue in reference_issues:

        target = next(
            (
                result
                for result in results
                if result.sheet_name == issue["sheet"]
            ),
            None,
        )

        if target is None:
            continue

        target.issues.append(
            RowIssue(
                sheet=issue["sheet"],
                row=issue["row"],
                column_name=issue["column_name"],
                value=issue["value"],
                message=issue["message"],
                severity=issue["severity"],
            )
        )

    return results