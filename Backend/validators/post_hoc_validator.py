"""

Orquesta la validación post-hoc de un archivo SNIES.



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

from rules.general_model import AllowedValue, DataType, ValidationRule

from rules.template_profiles import detect_templates


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

    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_decimal(value: Any) -> Decimal | None:
    """

    Convierte un valor numérico a Decimal.



    Rechaza booleanos, valores no numéricos e infinitos.

    """

    if isinstance(value, bool):

        return None

    if isinstance(value, (int, float, Decimal)):

        try:

            number = Decimal(str(value))

            if number.is_finite():

                return number

        except (InvalidOperation, ValueError, TypeError):

            return None

    if isinstance(value, str):

        try:

            number = Decimal(value.strip())

            if number.is_finite():

                return number

        except (InvalidOperation, ValueError, TypeError):

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

        date_formats = formats or [
            "%d-%m-%Y",
            "%d/%m/%Y",
        ]

        for date_format in date_formats:

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
    """

    Normaliza los formatos de fecha configurados en YAML.



    No descarta silenciosamente elementos inválidos.

    La validación de su contenido se realiza en el punto

    donde se consume la configuración.

    """

    if isinstance(configured_format, str):

        return [configured_format]

    if isinstance(configured_format, list):

        return configured_format

    if configured_format is None:

        return []

    return []


# ============================================================

# CONDICIONES DE OBLIGATORIEDAD

# ============================================================


def _condition_matches(
    condition: dict[str, Any],
    row_values: dict[str, object],
) -> bool:
    """

    Evalúa una condición configurada en business_rules.yaml.



    Operadores simples:

        not_blank

        blank

        gt

        eq

        in



    Operadores compuestos:

        any

        all



    Las condiciones mal configuradas generan ValueError.

    No se interpretan silenciosamente como condiciones falsas.

    """

    if not isinstance(condition, dict) or not condition:

        raise ValueError("Cada condición debe ser un diccionario no vacío.")

    # --------------------------------------------------------

    # CONDICIONES COMPUESTAS

    # --------------------------------------------------------

    has_any = "any" in condition

    has_all = "all" in condition

    if has_any and has_all:

        raise ValueError(
            "Una condición no puede definir simultáneamente " "'any' y 'all'."
        )

    if has_any or has_all:

        if len(condition) != 1:

            raise ValueError(
                "Una condición compuesta no puede combinarse "
                "con operadores simples en el mismo nivel."
            )

        if has_any:

            conditions = condition["any"]

            if not isinstance(conditions, list) or not conditions:

                raise ValueError(
                    "La condición 'any' debe contener " "una lista no vacía."
                )

            return any(_condition_matches(item, row_values) for item in conditions)

        conditions = condition["all"]

        if not isinstance(conditions, list) or not conditions:

            raise ValueError("La condición 'all' debe contener " "una lista no vacía.")

        return all(_condition_matches(item, row_values) for item in conditions)

    # --------------------------------------------------------

    # CONDICIONES SIMPLES

    # --------------------------------------------------------

    column = condition.get("column")

    operator = condition.get("operator", "not_blank")

    if not isinstance(column, str) or not column.strip():

        raise ValueError("Una condición simple debe indicar una columna válida.")

    if not isinstance(operator, str):

        raise ValueError(f"El operador de la columna '{column}' debe ser texto.")

    operator = operator.strip().lower()

    value = row_values.get(column)

    blank = _is_blank(value)

    if operator == "not_blank":

        return not blank

    if operator == "blank":

        return blank

    if operator == "gt":

        if blank:

            return False

        number = _to_decimal(value)

        if number is None:

            return False

        if "value" not in condition:

            raise ValueError(
                f"La condición 'gt' de '{column}' " "debe definir la propiedad 'value'."
            )

        expected = _to_decimal(condition["value"])

        if expected is None:

            raise ValueError(
                f"El valor esperado para 'gt' en '{column}' " "debe ser numérico."
            )

        return number > expected

    if operator == "eq":

        if blank:

            return False

        if "value" not in condition:

            raise ValueError(
                f"La condición 'eq' de '{column}' " "debe definir la propiedad 'value'."
            )

        expected = condition["value"]

        return str(value).strip() == str(expected).strip()

    if operator == "in":

        if blank:

            return False

        allowed_values = condition.get("values")

        if not isinstance(allowed_values, list):

            raise ValueError(
                f"La condición 'in' de '{column}' "
                "debe contener una lista en 'values'."
            )

        normalized_values = {str(item).strip() for item in allowed_values}

        return str(value).strip() in normalized_values

    raise ValueError(f"Operador de condición no soportado: '{operator}'.")


def _conditional_requirement_applies(
    rules: dict[str, Any],
    sheet_name: str,
    column_name: str,
    row_values: dict[str, object],
) -> bool | None:
    """

    Determina si un campo es obligatorio condicionalmente.



    Retorna:

        True: la condición se cumple.

        False: la condición no se cumple.

        None: no existe condición configurada para el campo.

    """

    conditional_rules = rules.get(
        "conditional_required_fields",
        {},
    )

    if not isinstance(conditional_rules, dict):

        raise ValueError("'conditional_required_fields' debe ser un diccionario.")

    normalized_sheet = sheet_name.strip().casefold()

    sheet_rules = None

    for configured_sheet, configured_rules in conditional_rules.items():

        if (
            isinstance(configured_sheet, str)
            and configured_sheet.strip().casefold() == normalized_sheet
        ):

            sheet_rules = configured_rules

            break

    if sheet_rules is None:

        return None

    if not isinstance(sheet_rules, dict):

        raise ValueError(
            f"Las condiciones de la hoja '{sheet_name}' "
            "deben estar definidas como un diccionario."
        )

    config = sheet_rules.get(column_name)

    if config is None:

        return None

    if not isinstance(config, dict):

        raise ValueError(
            f"La configuración de obligatoriedad de "
            f"'{column_name}' debe ser un diccionario."
        )

    condition = config.get("when")

    if condition is None:

        raise ValueError(
            f"La condición de '{column_name}' en '{sheet_name}' "
            "no contiene la propiedad 'when'."
        )

    return _condition_matches(
        condition,
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



    Restricciones soportadas:

        pattern

        min_value

        max_value

        date_within_past_years



    El formato de fecha se procesa en _build_column_rules()

    y se valida mediante validate_cell().



    Retorna una lista de tuplas:

        (mensaje, severidad)

    """

    if not isinstance(validation, dict):

        raise ValueError(
            f"La validación de '{column_name}' debe ser " "un diccionario."
        )

    issues: list[tuple[str, str]] = []

    if _is_blank(value):

        return issues

    # --------------------------------------------------------

    # 1. EXPRESIONES REGULARES

    # --------------------------------------------------------

    if "pattern" in validation:

        pattern = validation["pattern"]

        if not isinstance(pattern, str) or not pattern:

            raise ValueError(
                f"El patrón de '{column_name}' debe ser " "un texto no vacío."
            )

        try:

            compiled_pattern = re.compile(pattern)

        except re.error as exc:

            raise ValueError(
                f"Expresión regular inválida para " f"'{column_name}': {exc}"
            ) from exc

        if not compiled_pattern.fullmatch(str(value).strip()):

            issues.append(
                (
                    "El valor no cumple con el patrón " f"permitido: {pattern}.",
                    "error",
                )
            )

    # --------------------------------------------------------

    # 2. LÍMITES NUMÉRICOS

    # --------------------------------------------------------

    minimum = validation.get("min_value")

    maximum = validation.get("max_value")

    min_number = None

    max_number = None

    if minimum is not None:

        min_number = _to_decimal(minimum)

        if min_number is None:

            raise ValueError(
                f"'min_value' de '{column_name}' " "debe ser un número válido."
            )

    if maximum is not None:

        max_number = _to_decimal(maximum)

        if max_number is None:

            raise ValueError(
                f"'max_value' de '{column_name}' " "debe ser un número válido."
            )

    if min_number is not None and max_number is not None and min_number > max_number:

        raise ValueError(
            f"'min_value' no puede ser mayor que 'max_value' "
            f"en la configuración de '{column_name}'."
        )

    if min_number is not None or max_number is not None:

        number = _to_decimal(value)

        if number is None:

            issues.append(
                (
                    "El valor debe ser numérico para cumplir "
                    "los límites configurados.",
                    "error",
                )
            )

        else:

            if min_number is not None and number < min_number:

                issues.append(
                    (
                        f"El valor debe ser mayor o igual " f"a {minimum}.",
                        "error",
                    )
                )

            if max_number is not None and number > max_number:

                issues.append(
                    (
                        f"El valor debe ser menor o igual " f"a {maximum}.",
                        "error",
                    )
                )

    # --------------------------------------------------------

    # 3. ANTIGÜEDAD PERMITIDA DE UNA FECHA

    # --------------------------------------------------------

    years = validation.get("date_within_past_years")

    if years is not None:

        if isinstance(years, bool) or not isinstance(years, int) or years < 0:

            raise ValueError(
                f"'date_within_past_years' de '{column_name}' "
                "debe ser un entero mayor o igual que cero."
            )

        # El formato ya fue validado por validate_cell().

        # Aquí únicamente se comprueba la antigüedad.

        parsed_date = _to_date(
            value,
            _normalize_date_formats(validation.get("format")) or None,
        )

        if parsed_date is not None:

            today = datetime.date.today()

            try:

                earliest_date = today.replace(
                    year=today.year - years,
                )

            except ValueError:

                # Ajuste para fechas como el 29 de febrero.

                earliest_date = today.replace(
                    year=today.year - years,
                    day=28,
                )

            if not earliest_date <= parsed_date <= today:

                issues.append(
                    (
                        "La fecha debe estar comprendida "
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



    La búsqueda de hojas ignora mayúsculas y espacios exteriores.

    """

    sheet_configurations = getattr(
        configuration,
        "sheet_configurations",
        {},
    )

    if not isinstance(sheet_configurations, dict):

        raise ValueError("sheet_configurations debe ser un diccionario.")

    normalized_name = sheet_name.strip().casefold()

    for configured_name, sheet_configuration in sheet_configurations.items():

        if (
            isinstance(configured_name, str)
            and configured_name.strip().casefold() == normalized_name
        ):

            if not isinstance(sheet_configuration, dict):

                raise ValueError(
                    f"La configuración de '{configured_name}' "
                    "debe ser un diccionario."
                )

            return sheet_configuration

    # Compatibilidad con la configuración anterior.

    validation_config = getattr(
        configuration,
        "validation_config",
        {},
    )

    if not isinstance(validation_config, dict):

        raise ValueError("validation_config debe ser un diccionario.")

    return {
        "rules": configuration.known_fields,
        "validations": validation_config.get(
            "column_rules",
            {},
        ),
        "catalogs": validation_config.get(
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



    Integra comentarios de Excel, reglas conocidas,

    validations.yaml y catálogos de catalogs.yaml.

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

    if not isinstance(validations_by_column, dict):

        raise ValueError(
            f"Las validaciones de la hoja '{sheet_name}' " "deben ser un diccionario."
        )

    if not isinstance(catalogs, dict):

        raise ValueError(
            f"Los catálogos de la hoja '{sheet_name}' " "deben ser un diccionario."
        )

    # --------------------------------------------------------

    # PROCESAR CADA COLUMNA

    # --------------------------------------------------------

    for header in headers:

        column_name = header.column_name

        # 1. Interpretar el comentario de Excel.

    
        rule = interpret_comment(
            column_name,
            header.comment_text,
            known_fields=configuration.known_fields,
            sheet_name=sheet_name,
        )

        # Las reglas explícitas de rules.yaml prevalecen
        # sobre el tipo inferido desde el comentario de Excel.
        configured_rules = sheet_configuration.get("rules", {})
        configured_rule = configured_rules.get(column_name, {})

        if isinstance(configured_rule, dict):
            configured_datatype = configured_rule.get("datatype")

            if isinstance(configured_datatype, str):
                configured_datatype = configured_datatype.strip().lower()

                datatype_map = {
                    "alphabetic": DataType.ALPHABETIC,
                    "alphanumeric": DataType.ALPHANUMERIC,
                    "integer": DataType.INTEGER,
                    "decimal": DataType.DECIMAL,
                    "date": DataType.DATE,
                    "text": DataType.TEXT,
                }

                if configured_datatype in datatype_map:
                    rule.datatype = datatype_map[configured_datatype]



        # 2. Obtener las validaciones configuradas.

        validation = validations_by_column.get(
            column_name,
            {},
        )

        if not isinstance(validation, dict):

            raise ValueError(
                f"La validación de '{column_name}' "
                f"en la hoja '{sheet_name}' debe ser "
                "un diccionario."
            )

        # ----------------------------------------------------

        # 3. Cargar valores expresamente excluidos.

        # ----------------------------------------------------

        configured_excluded_values = validation.get(
            "excluded_values",
            [],
        )

        if not isinstance(configured_excluded_values, list):

            raise ValueError(
                f"'excluded_values' de '{column_name}' "
                f"en la hoja '{sheet_name}' debe ser una lista."
            )

        parsed_excluded_values: list[str] = []

        for index, item in enumerate(configured_excluded_values):

            if isinstance(item, bool) or not isinstance(item, (str, int, float)):

                raise ValueError(
                    f"El elemento {index + 1} de 'excluded_values' "
                    f"en '{column_name}' debe ser texto o numérico."
                )

            excluded_value = str(item).strip()

            if not excluded_value:

                raise ValueError(
                    f"El elemento {index + 1} de 'excluded_values' "
                    f"en '{column_name}' no puede estar vacío."
                )

            if excluded_value in parsed_excluded_values:

                raise ValueError(
                    f"El valor '{excluded_value}' está duplicado "
                    f"en 'excluded_values' de '{column_name}'."
                )

            parsed_excluded_values.append(excluded_value)

        rule.excluded_values = parsed_excluded_values

        # ----------------------------------------------------

        # 4. Complementar el tipo y los formatos de fecha.

        # ----------------------------------------------------

        if "format" in validation:

            configured_formats = _normalize_date_formats(validation["format"])

            if not configured_formats or any(
                not isinstance(item, str) or not item.strip()
                for item in configured_formats
            ):

                raise ValueError(
                    f"'format' de '{column_name}' debe contener "
                    "uno o varios formatos de fecha válidos."
                )

            if rule.datatype == DataType.UNKNOWN:

                rule.datatype = DataType.DATE

            elif rule.datatype != DataType.DATE:

                message = (
                    "La configuración de formato de fecha entra "
                    "en conflicto con el tipo de dato interpretado."
                )

                if message not in rule.unparsed_fragments:

                    rule.unparsed_fragments.append(message)

            if rule.datatype == DataType.DATE:

                if not rule.date_formats:

                    rule.date_formats = configured_formats

                elif set(rule.date_formats) != set(configured_formats):

                    message = (
                        "Los formatos de fecha del comentario "
                        "no coinciden con los configurados "
                        "en validations.yaml."
                    )

                    if message not in rule.unparsed_fragments:

                        rule.unparsed_fragments.append(message)

        # ----------------------------------------------------

        # 5. Cargar valores permitidos definidos directamente.

        # ----------------------------------------------------

        configured_allowed_values = validation.get("allowed_values")

        if configured_allowed_values is not None:

            if not isinstance(configured_allowed_values, list):

                raise ValueError(
                    f"'allowed_values' de '{column_name}' "
                    f"en la hoja '{sheet_name}' debe ser una lista."
                )

            parsed_allowed_values: list[AllowedValue] = []

            seen_codes: set[str] = set()

            for index, item in enumerate(configured_allowed_values):

                if not isinstance(item, dict):

                    raise ValueError(
                        f"El elemento {index + 1} de 'allowed_values' "
                        f"en '{column_name}' debe ser un diccionario."
                    )

                code = item.get("code")

                label = item.get("label")

                if code is None or not isinstance(label, str) or not label.strip():

                    raise ValueError(
                        f"El elemento {index + 1} de 'allowed_values' "
                        f"en '{column_name}' debe contener "
                        "'code' y un 'label' no vacío."
                    )

                code = str(code).strip()

                if not code:

                    raise ValueError(
                        f"El código del elemento {index + 1} "
                        f"de 'allowed_values' en '{column_name}' "
                        "no puede estar vacío."
                    )

                if code in seen_codes:

                    raise ValueError(
                        f"El código '{code}' está duplicado en "
                        f"'allowed_values' de '{column_name}'."
                    )

                seen_codes.add(code)

                parsed_allowed_values.append(
                    AllowedValue(
                        code=code,
                        label=label.strip(),
                    )
                )

            if not rule.allowed_values:

                rule.allowed_values = parsed_allowed_values

        # ----------------------------------------------------

        # 6. Cargar el catálogo configurado para la columna.

        # ----------------------------------------------------

        catalog_name = validation.get("catalog")

        if catalog_name is not None:

            if not isinstance(catalog_name, str) or not catalog_name.strip():

                raise ValueError(
                    f"El catálogo de '{column_name}' "
                    f"en la hoja '{sheet_name}' debe tener "
                    "un nombre válido."
                )

            catalog_name = catalog_name.strip()

            if catalog_name not in catalogs:

                raise ValueError(
                    f"No existe la configuración del catálogo "
                    f"'{catalog_name}' para la hoja '{sheet_name}'."
                )

            rule.allowed_values = load_catalog(
                catalogs[catalog_name],
                catalog_name,
            )

        # ----------------------------------------------------

        # 7. Guardar la regla de esta columna.

        # ----------------------------------------------------

        rules_by_column[column_name] = rule

    # --------------------------------------------------------

    # RETORNAR LAS REGLAS DE TODAS LAS COLUMNAS

    # --------------------------------------------------------

    return rules_by_column, validations_by_column


# VALIDACIONES ESTRUCTURALES AUXILIARES

# ============================================================


def _build_structure_result(
    ws: Any,
) -> SheetValidationResult:
    """

    Construye el resultado de una hoja sin encabezados reconocibles.

    """

    result = SheetValidationResult(
        sheet_name=ws.title,
        total_rows=max(ws.max_row - HEADER_ROW, 0),
    )

    header_issues = validate_sheet_headers(ws)

    for issue in header_issues:

        result.issues.append(
            RowIssue(
                sheet=ws.title,
                row=issue["row"],
                column_name=issue["column_name"],
                value=issue.get("value"),
                message=issue["message"],
                severity=issue.get("severity", "error"),
            )
        )

    if not result.issues:

        result.issues.append(
            RowIssue(
                sheet=ws.title,
                row=HEADER_ROW,
                column_name="__ENCABEZADO_VACIO__",
                value=None,
                message=(
                    "La hoja no contiene encabezados reconocibles "
                    "en la primera fila."
                ),
                severity="error",
            )
        )

    return result


def _has_invalid_headers(
    header_issues: list[dict[str, Any]],
) -> bool:
    """

    Determina si existen encabezados que impiden validar las filas.



    No depende exclusivamente del texto del mensaje.

    """

    return any(
        issue.get("severity") == "error"
        and (
            "duplicado" in issue.get("message", "").lower()
            or issue.get("column_name") == "__ENCABEZADO_VACIO__"
        )
        for issue in header_issues
    )


# ============================================================

# VALIDACIÓN PRINCIPAL

# ============================================================


def validate_workbook(
    workbook: Workbook,
    template_name: str | None = None,
) -> list[SheetValidationResult]:
    """Valida todas las hojas de datos de un libro de Excel."""

    results: list[SheetValidationResult] = []

    # ---------------------------------------------------------

    # 1. IDENTIFICAR Y VALIDAR LA PLANTILLA

    # ---------------------------------------------------------

    detected_templates = detect_templates(workbook.sheetnames)

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

    detected_template = detected_templates[0]

    # ---------------------------------------------------------

    # 2. UTILIZAR LA PLANTILLA SELECCIONADA

    # ---------------------------------------------------------

    if template_name is None:

        # Compatibilidad temporal con scripts y pruebas antiguas.

        template_name = detected_template

    else:

        template_name = template_name.strip().upper()

        if template_name != detected_template:

            raise ValueError(
                f"La plantilla seleccionada '{template_name}' "
                f"no coincide con la plantilla detectada "
                f"en el archivo '{detected_template}'."
            )

    # ---------------------------------------------------------

    # 3. CARGAR EXCLUSIVAMENTE LA CONFIGURACIÓN DE LA PLANTILLA

    # ---------------------------------------------------------

    configuration = load_rule_configuration(template_name=template_name)

    business_rules = configuration.business_rules

    global_business_rules = get_global_business_rules(configuration)

    # ---------------------------------------------------------

    # 3. OBTENER EL PERFIL ESTRUCTURAL

    # ---------------------------------------------------------

    template_profile = configuration.template_profile

    if not template_profile:

        raise ValueError(
            f"No existe un perfil estructural para " f"la plantilla '{template_name}'."
        )

    expected_sheets = template_profile.get(
        "sheets",
        [],
    )

    if not isinstance(expected_sheets, list):

        raise ValueError(
            f"Las hojas esperadas de '{template_name}' "
            "deben estar definidas como una lista."
        )

    expected_sheet_by_normalized = {
        sheet.strip().casefold(): sheet
        for sheet in expected_sheets
        if isinstance(sheet, str)
    }

    # ---------------------------------------------------------

    # 4. DETERMINAR LAS HOJAS DEL LIBRO

    # ---------------------------------------------------------

    data_sheets = list(iter_data_sheets(workbook))

    # ---------------------------------------------------------

    # 4.1. DETECTAR HOJAS OBLIGATORIAS AUSENTES

    # ---------------------------------------------------------

    workbook_sheet_names = {ws.title.strip().casefold() for ws in data_sheets}

    missing_sheets = [
        sheet
        for sheet in expected_sheets
        if sheet.strip().casefold() not in workbook_sheet_names
    ]

    if missing_sheets:

        missing_sheet_issues = []

        for sheet_name in missing_sheets:

            missing_sheet_issues.append(
                RowIssue(
                    sheet="ESTRUCTURA_LIBRO",
                    row=1,
                    column_name="HOJAS",
                    value=sheet_name,
                    message=(
                        f"Falta la hoja obligatoria '{sheet_name}' "
                        f"de la plantilla {template_name}. "
                        "El archivo debe contener todas las hojas "
                        "definidas para esta plantilla."
                    ),
                    severity="error",
                )
            )

        results.append(
            SheetValidationResult(
                sheet_name="ESTRUCTURA_LIBRO",
                total_rows=0,
                issues=missing_sheet_issues,
            )
        )

    unexpected_sheets = {
        ws.title
        for ws in data_sheets
        if ws.title.strip().casefold() not in expected_sheet_by_normalized
    }

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

    sheets_to_validate = [
        ws
        for ws in data_sheets
        if ws.title.strip().casefold() in expected_sheet_by_normalized
    ]

    # ---------------------------------------------------------

    # 5. VALIDAR CADA HOJA

    # ---------------------------------------------------------

    # Conservamos el tipo de dato de cada columna por hoja.

    # El validador entre hojas necesita esta información para

    # comparar correctamente claves numéricas y textuales.

    column_types_by_sheet: dict[
        str,
        dict[str, DataType],
    ] = {}

    for ws in sheets_to_validate:

        headers = read_headers(ws)

        # -----------------------------------------------------

        # 5.0. HOJAS SIN ENCABEZADOS

        # -----------------------------------------------------

        if not headers:

            results.append(_build_structure_result(ws))

            continue

        sheet_configuration = _get_sheet_configuration(
            configuration,
            ws.title,
        )

        # -----------------------------------------------------

        # 5.1. CONSTRUIR LAS REGLAS DE LAS COLUMNAS

        # -----------------------------------------------------

        rules_by_column, validations_by_column = _build_column_rules(
            headers,
            ws.title,
            sheet_configuration,
            configuration,
        )
        


        column_types_by_sheet[ws.title] = {
            column_name: rule.datatype for column_name, rule in rules_by_column.items()
        }

        column_types_by_sheet[ws.title] = {
            column_name: rule.datatype for column_name, rule in rules_by_column.items()
        }

        column_letter_by_name = {
            header.column_name: header.column_letter for header in headers
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

        # -----------------------------------------------------

        # 5.1. VALIDAR PRESENCIA DE COLUMNAS DE LA PLANTILLA

        # -----------------------------------------------------

        configured_rules = sheet_configuration.get(
            "rules",
            {},
        )

        if not isinstance(configured_rules, dict):

            raise ValueError(
                f"Las reglas de la hoja '{ws.title}' " "deben ser un diccionario."
            )

        # Normalizar los nombres para evitar diferencias

        # por mayúsculas o espacios exteriores.

        actual_headers = {
            header.column_name.strip().casefold()
            for header in headers
            if header.column_name.strip()
        }

        missing_columns = [
            column_name
            for column_name in configured_rules
            if column_name.strip().casefold() not in actual_headers
        ]

        for column_name in missing_columns:

            result.issues.append(
                RowIssue(
                    sheet=ws.title,
                    row=HEADER_ROW,
                    column_name=column_name,
                    value=None,
                    message=(
                        f"Falta la columna obligatoria de estructura "
                        f"'{column_name}' en la hoja '{ws.title}'. "
                        "La columna debe conservarse aunque sus "
                        "valores puedan ser opcionales."
                    ),
                    severity="error",
                )
            )

        # -----------------------------------------------------

        # 5.2. VALIDACIONES ESTRUCTURALES DE ENCABEZADOS

        # -----------------------------------------------------

        header_issues = validate_sheet_headers(ws)

        for issue in header_issues:

            result.issues.append(
                RowIssue(
                    sheet=ws.title,
                    row=issue["row"],
                    column_name=issue["column_name"],
                    value=issue.get("value"),
                    message=issue["message"],
                    severity=issue.get("severity", "error"),
                )
            )

        if _has_invalid_headers(header_issues):

            results.append(result)

            continue

        # -----------------------------------------------------

        # 5.3. RECOPILAR LAS FILAS COMO DICCIONARIOS

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

                cell = ws[f"{header.column_letter}{row_idx}"]

                row_values[header.column_name] = cell.value

                if not _is_blank(cell.value):

                    is_empty_row = False

            if is_empty_row:

                continue

            row_dicts.append(row_values)

            row_numbers.append(row_idx)

        # -----------------------------------------------------

        # 5.4. VALIDACIONES POR CELDA Y REGLAS DE NEGOCIO

        # -----------------------------------------------------

        for row_values, row_idx in zip(
            row_dicts,
            row_numbers,
        ):

            for col_name, value in row_values.items():

                validation = validations_by_column.get(
                    col_name,
                    {},
                )

                # ---------------------------------------------

                # A. OBLIGATORIEDAD CONDICIONAL

                # ---------------------------------------------

                conditional_applies = _conditional_requirement_applies(
                    business_rules,
                    ws.title,
                    col_name,
                    row_values,
                )

                # ---------------------------------------------

                # B. TIPO DE DATO, LONGITUD Y CATÁLOGO

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

                # C. RESTRICCIONES DE validations.yaml

                # ---------------------------------------------

                configured_issues = _validate_configured_constraints(
                    col_name,
                    value,
                    validation,
                    row_values,
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

                # D. REGLAS DE NEGOCIO POR CAMPO

                # ---------------------------------------------

                business_rule = resolve_business_rule(
                    configuration,
                    column_name=col_name,
                    sheet_name=ws.title,
                )

                if business_rule and business_rule.get("kind") not in (
                    None,
                    "cross_row_consistency_note",
                    "unique_in_sheet",
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

        # 5.5. CONSISTENCIA ENTRE FILAS

        # -----------------------------------------------------

        column_types = {
            column_name: rule.datatype for column_name, rule in rules_by_column.items()
        }

        row_values_by_number = {
            number: values for number, values in zip(row_numbers, row_dicts)
        }

        for col_name, business_rule in global_business_rules.items():

            if business_rule.get("kind") != "cross_row_consistency_note":

                continue

            check_columns = business_rule.get(
                "check_columns",
                [],
            )

            if col_name not in column_letter_by_name:

                continue

            if not check_columns or not all(
                column in column_letter_by_name for column in check_columns
            ):

                continue

            group_by = business_rule.get("group_by")

            if group_by and group_by not in column_letter_by_name:

                group_by = None

            consistency_issues = check_code_consistency(
                col_name,
                check_columns,
                row_dicts,
                row_numbers,
                column_types,
                group_by,
            )

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
                        value=row_values.get(cross_issue.column_name),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

        # -----------------------------------------------------

        # 5.6. REGLAS DE UNICIDAD DE CADA HOJA

        # -----------------------------------------------------

        for col_name in column_letter_by_name:

            business_rule = resolve_business_rule(
                configuration,
                column_name=col_name,
                sheet_name=ws.title,
            )

            if not business_rule or business_rule.get("kind") != "unique_in_sheet":

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
                        value=row_values.get(cross_issue.column_name),
                        message=cross_issue.message,
                        severity=cross_issue.severity,
                    )
                )

        # -----------------------------------------------------

        # 5.7. GUARDAR EL RESULTADO DE LA HOJA

        # -----------------------------------------------------

        # Todas las hojas procesadas deben quedar en results,

        # incluso cuando no presenten incidencias.

        results.append(result)

    # ---------------------------------------------------------

    # 6. VALIDACIONES REFERENCIALES ENTRE HOJAS

    # ---------------------------------------------------------

    reference_issues = validate_sheet_references(
        workbook,
        template_name=template_name,
        column_types_by_sheet=column_types_by_sheet,
    )

    # Crear un índice para localizar rápidamente el resultado

    # de la hoja a la que pertenece cada incidencia.

    results_by_sheet = {result.sheet_name: result for result in results}

    for issue in reference_issues:

        target = results_by_sheet.get(issue["sheet"])

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
