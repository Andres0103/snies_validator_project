
"""
Orquesta la generación de plantillas SNIES con validaciones nativas.

Flujo por workbook:
    1. Identificar la plantilla y cargar su configuración.
    2. Leer encabezados e interpretar sus comentarios.
    3. Completar las reglas con known_fields y los catálogos YAML.
    4. Construir la hoja auxiliar con las listas desplegables.
    5. Construir y aplicar las validaciones nativas de Excel.
    6. Generar un reporte de las validaciones aplicadas y pendientes.

Se conserva el contenido original de las celdas, encabezados,
comentarios y formatos existentes.

IMPORTANTE:
Excel no permite combinar libremente distintos tipos de
DataValidation sobre una misma celda.

Por eso este módulo aplica una sola validación nativa por columna
y registra las restricciones que deben verificarse mediante
el validador post-hoc.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from excel.reader import (
    HeaderCell,
    iter_data_sheets,
    read_headers,
)

from excel.helper_sheets import build_helper_sheet

from excel.excel_validation_builder import (
    build_business_rule_validation,
    build_date_after_column_validation,
    build_list_validation,
    build_type_validation,
)

from rules.config_loader import (
    load_rule_configuration,
    resolve_business_rule,
)

from rules.template_profiles import detect_templates
from rules.catalog_loader import load_catalog
from rules.interpreter import interpret_comment

from backend.rules.general_model import DataType, ValidationRule


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

# Número de filas que cubrirán las validaciones nativas.
#
# La fila 1 contiene encabezados y los datos comienzan en la 2.
# Por tanto, este valor representa la última fila cubierta,
# no la cantidad de registros.
DATA_ROWS_TO_COVER = 2000


# Archivos reconocidos como parte de la nueva arquitectura.
CONFIG_FILES = (
    "rules.yaml",
    "validations.yaml",
    "catalogs.yaml",
    "business_rules.yaml",
)


# Reglas de negocio que tienen constructor de validación nativa.
SUPPORTED_BUSINESS_RULES = {
    "date_within_past_years",
    "non_negative",
    "non_negative_with_min_length",
    "email_format",
    "date_after_column",
}


# ============================================================
# MODELO DEL REPORTE
# ============================================================

@dataclass
class ColumnReport:
    """
    Resultado de la generación de validaciones para una columna.

    Attributes:
        sheet_name:
            Nombre de la hoja.

        column_name:
            Nombre del campo.

        rule:
            Regla interpretada para la columna.

        validations_applied:
            Validaciones nativas aplicadas y restricciones
            que quedan pendientes para el post-hoc.

        needs_review:
            Indica si la columna requiere revisión adicional
            mediante el validador post-hoc.
    """

    sheet_name: str
    column_name: str
    rule: ValidationRule
    validations_applied: list[str]
    needs_review: bool


# ============================================================
# DETECCIÓN DE ARQUITECTURA DE CONFIGURACIÓN
# ============================================================

def _has_new_configuration(template_name: str) -> bool:
    """
    Comprueba si una plantilla utiliza la nueva arquitectura.

    Se verifica que exista el directorio específico de la plantilla
    y al menos un archivo de configuración reconocido en el
    directorio común o en el directorio de la plantilla.

    Esta comprobación detecta la presencia de configuración,
    pero no garantiza que todos los archivos requeridos estén
    completos. Esa responsabilidad corresponde al cargador.
    """

    patterns_dir = (
        Path(__file__).resolve().parents[1]
        / "rules"
        / "patterns"
    )

    template_dir = (
        patterns_dir
        / "templates"
        / template_name.lower()
    )

    common_dir = patterns_dir / "common"

    # La nueva arquitectura necesita el directorio de plantilla.
    if not template_dir.is_dir():
        return False

    # Revisar configuración común y configuración específica.
    for directory in (common_dir, template_dir):

        if not directory.is_dir():
            continue

        if any(
            (directory / filename).is_file()
            for filename in CONFIG_FILES
        ):
            return True

    return False


# ============================================================
# CONFIGURACIÓN POR HOJA
# ============================================================

def _get_sheet_configuration(
    configuration: Any,
    sheet_name: str,
) -> dict[str, Any]:
    """
    Obtiene las reglas, validaciones y catálogos de una hoja.

    Prioridad:
        1. Nueva arquitectura: sheet_configurations.
        2. Arquitectura anterior: validation_config.

    Esto permite mantener compatibilidad durante la migración.
    """

    sheet_configurations = getattr(
        configuration,
        "sheet_configurations",
        {},
    ) or {}

    normalized_sheet_name = sheet_name.strip().casefold()

    for configured_name, sheet_config in sheet_configurations.items():

        if configured_name.strip().casefold() == normalized_sheet_name:
            return sheet_config

    # Compatibilidad con la configuración anterior.
    validation_config = getattr(
        configuration,
        "validation_config",
        {},
    ) or {}

    return {
        "rules": getattr(
            configuration,
            "known_fields",
            {},
        ),
        "validations": validation_config.get(
            "column_rules",
            {},
        ),
        "catalogs": validation_config.get(
            "master_tables",
            {},
        ),
    }


# ============================================================
# APLICACIÓN DE CATÁLOGOS CONFIGURADOS
# ============================================================

def _apply_configured_catalog(
    rule: ValidationRule,
    sheet_name: str,
    validations: dict[str, Any],
    catalogs: dict[str, Any],
) -> None:
    """
    Carga el catálogo configurado para una columna.

    Cuando validations.yaml declara explícitamente un catálogo,
    este tiene prioridad sobre los valores interpretados desde
    el comentario de Excel.

    La función modifica rule.allowed_values.
    """

    validation = validations.get(
        rule.column_name,
        {},
    )

    if not isinstance(validation, dict):
        raise ValueError(
            f"La configuración de validación de la columna "
            f"'{rule.column_name}' en la hoja '{sheet_name}' "
            "debe ser un diccionario."
        )

    catalog_name = validation.get("catalog")

    # Si no hay catálogo configurado, se conservan los valores
    # interpretados desde el comentario de Excel.
    if rule.allowed_values:
        return

    if not catalog_name:
        return

    catalog_config = catalogs.get(catalog_name)

    if catalog_config is None:
        raise ValueError(
            f"La columna '{rule.column_name}' de la hoja "
            f"'{sheet_name}' referencia el catálogo "
            f"'{catalog_name}', pero no está definido "
            "en catalogs.yaml."
        )

    # El catálogo YAML reemplaza los valores del comentario.
    rule.allowed_values = load_catalog(
        catalog_config,
        catalog_name,
    )


# ============================================================
# DEDUPLICACIÓN DE LISTAS DESPLEGABLES
# ============================================================

def _dedup_rules_with_lists(
    all_headers: list[HeaderCell],
    rules_by_key: dict[tuple[str, str], ValidationRule],
) -> list[ValidationRule]:
    """
    Reúne las reglas que contienen listas de valores permitidos.

    La hoja auxiliar identifica sus rangos por nombre de columna.
    Por eso, si una misma columna aparece en varias hojas,
    sus catálogos deben ser iguales.

    Si existen catálogos diferentes para una misma columna,
    se genera un error en lugar de reutilizar silenciosamente
    un catálogo incorrecto.
    """

    unique_rules: dict[str, ValidationRule] = {}

    for header in all_headers:

        key = (
            header.sheet_name,
            header.column_name,
        )

        rule = rules_by_key[key]

        if not rule.allowed_values:
            continue

        column_name = rule.column_name

        if column_name not in unique_rules:
            unique_rules[column_name] = rule
            continue

        existing_rule = unique_rules[column_name]

        existing_values = [
            (
                str(value.code),
                str(value.label),
            )
            for value in existing_rule.allowed_values
        ]

        current_values = [
            (
                str(value.code),
                str(value.label),
            )
            for value in rule.allowed_values
        ]

        if existing_values != current_values:
            raise ValueError(
                f"La columna '{column_name}' tiene catálogos "
                "diferentes en varias hojas del workbook. "
                "La hoja auxiliar actual no permite distinguir "
                "listas diferentes para columnas con el mismo nombre."
            )

    return list(unique_rules.values())


# ============================================================
# IDENTIFICACIÓN DE RESTRICCIONES
# ============================================================

def _has_type_validation(rule: ValidationRule) -> bool:
    """
    Determina si la regla general tiene alguna restricción
    que pueda convertirse en validación nativa de Excel.
    """

    if rule.datatype in {
        DataType.INTEGER,
        DataType.DECIMAL,
        DataType.DATE,
    }:
        return True

    if rule.datatype in {
        DataType.ALPHANUMERIC,
        DataType.ALPHABETIC,
        DataType.TEXT,
    }:
        return any(
            value is not None
            for value in (
                rule.exact_length,
                rule.min_length,
                rule.max_length,
            )
        )

    return False


def _get_type_validation_description(
    rule: ValidationRule,
) -> str:
    """
    Construye una descripción para el reporte de las restricciones
    de tipo y longitud que requieren validación post-hoc.
    """

    if rule.datatype == DataType.INTEGER:
        return "tipo:INTEGER"

    if rule.datatype == DataType.DECIMAL:
        return "tipo:DECIMAL"

    if rule.datatype == DataType.DATE:
        return "tipo:DATE"

    if rule.exact_length is not None:
        return f"longitud:exacta_{rule.exact_length}"

    if (
        rule.min_length is not None
        and rule.max_length is not None
    ):
        return (
            f"longitud:entre_{rule.min_length}"
            f"_y_{rule.max_length}"
        )

    if rule.min_length is not None:
        return f"longitud:minima_{rule.min_length}"

    if rule.max_length is not None:
        return f"longitud:maxima_{rule.max_length}"

    return f"tipo:{rule.datatype.value}"


# Restricciones de validations.yaml que el motor post-hoc debe ejecutar.
POST_HOC_VALIDATION_KEYS = {
    "pattern",
    "min_value",
    "max_value",
    "format",
    "date_within_past_years",
}


def _get_configured_post_hoc_constraints(
    validation: dict[str, Any],
) -> list[str]:
    """
    Identifica las restricciones de validations.yaml que deben
    comprobarse mediante el validador post-hoc.

    El catálogo se excluye porque se representa mediante
    la lista desplegable nativa de Excel.

    No significa que las restricciones se ejecuten aquí:
    únicamente se identifican para el reporte del writer.
    """

    if not isinstance(validation, dict):
        raise ValueError(
            "La configuración de validación de una columna "
            "debe ser un diccionario."
        )

    pending_constraints = []

    for key in POST_HOC_VALIDATION_KEYS:

        if key in validation:
            pending_constraints.append(
                f"post_hoc:validacion_configurada:{key}"
            )

    return pending_constraints

# ============================================================
# CONSTRUCCIÓN DE VALIDACIÓN DE NEGOCIO
# ============================================================

def _build_business_validation(
    business_rule: dict[str, Any],
    rule: ValidationRule,
    column_letter: str,
    column_letters_by_sheet: dict[str, dict[str, str]],
    sheet_name: str,
) -> DataValidation | None:
    """
    Construye la validación nativa correspondiente a una regla
    de negocio.

    Las reglas que comparan dos columnas se resuelven mediante
    build_date_after_column_validation().
    """

    business_kind = business_rule.get("kind")

    if business_kind == "date_after_column":

        after_column_name = business_rule.get(
            "after_column"
        )

        if not after_column_name:
            raise ValueError(
                f"La regla de negocio de '{rule.column_name}' "
                f"en la hoja '{sheet_name}' no define "
                "after_column."
            )

        after_column_letter = column_letters_by_sheet.get(
            sheet_name,
            {},
        ).get(after_column_name)

        if not after_column_letter:
            raise ValueError(
                f"La regla de negocio de '{rule.column_name}' "
                f"en la hoja '{sheet_name}' referencia la columna "
                f"'{after_column_name}', pero esta no existe "
                "en la hoja."
            )

        return build_date_after_column_validation(
            own_column_letter=column_letter,
            after_column_letter=after_column_letter,
            after_column_name=after_column_name,
            strict=business_rule.get("strict", False),
        )

    if business_kind in SUPPORTED_BUSINESS_RULES:

        return build_business_rule_validation(
            kind=business_kind,
            params=business_rule,
            column_letter=column_letter,
            rule=rule,
        )

    return None


# ============================================================
# APLICACIÓN DE UNA VALIDACIÓN NATIVA
# ============================================================

def _apply_validation(
    worksheet: Any,
    validation: DataValidation,
    data_range: str,
) -> None:
    """
    Agrega una validación al worksheet y la aplica al rango.

    Centralizar esta operación evita repetir el mismo código
    en cada tipo de validación.
    """

    worksheet.add_data_validation(validation)
    validation.add(data_range)


# ============================================================
# PROCESAMIENTO PRINCIPAL
# ============================================================

def process_workbook(
    workbook: Workbook,
) -> list[ColumnReport]:
    """
    Aplica validaciones nativas a todas las hojas de datos
    del workbook y devuelve un reporte de generación.

    Prioridad de validación nativa por columna:

        1. Lista desplegable.
        2. Regla de negocio.
        3. Tipo y longitud.

    Las restricciones no aplicadas nativamente se registran
    como pendientes para el validador post-hoc.

    Returns:
        Lista de reportes, uno por cada columna procesada.
    """

    reports: list[ColumnReport] = []

    # --------------------------------------------------------
    # 1. IDENTIFICAR LA PLANTILLA DEL LIBRO
    # --------------------------------------------------------

    detected_templates = detect_templates(
        workbook.sheetnames
    )

    if len(detected_templates) > 1:
        raise ValueError(
            "El archivo contiene hojas principales de varias "
            "plantillas SNIES: "
            f"{', '.join(detected_templates)}. "
            "Cada archivo debe corresponder a una sola plantilla."
        )

    template_name = (
        detected_templates[0]
        if detected_templates
        else None
    )

    # --------------------------------------------------------
    # 2. CARGAR LA CONFIGURACIÓN CORRESPONDIENTE
    # --------------------------------------------------------

    if (
        template_name
        and _has_new_configuration(template_name)
    ):

        # Plantilla migrada a la nueva arquitectura.
        configuration = load_rule_configuration(
            template_name=template_name
        )

    else:

        # Plantilla todavía no migrada.
        # Se conserva la configuración anterior.
        configuration = load_rule_configuration()

    # Convertir a lista para garantizar que podamos recorrer
    # las hojas varias veces, incluso si iter_data_sheets
    # devuelve un iterador.
    data_sheets = list(
        iter_data_sheets(workbook)
    )

    # --------------------------------------------------------
    # 3. INTERPRETAR ENCABEZADOS Y CONSTRUIR REGLAS
    # --------------------------------------------------------

    all_headers: list[HeaderCell] = []

    rules_by_key: dict[
        tuple[str, str],
        ValidationRule,
    ] = {}
    
    validations_by_key: dict[
    tuple[str, str],
    dict[str, Any],
] = {}

    
    for ws in data_sheets:
        headers = read_headers(ws)
        all_headers.extend(headers)

        # Obtener la configuración particular de la hoja.
        sheet_configuration = _get_sheet_configuration(
            configuration,
            ws.title,
        )

        validations = sheet_configuration.get("validations", {})
        catalogs = sheet_configuration.get("catalogs", {})

        for header in headers:
            # Interpretar el comentario del encabezado.
            rule = interpret_comment(
                header.column_name,
                header.comment_text,
                known_fields=configuration.known_fields,
                sheet_name=ws.title,
            )

            # Incorporar el catálogo YAML explícito.
            _apply_configured_catalog(
                rule,
                ws.title,
                validations,
                catalogs,
            )

            key = (
                header.sheet_name,
                header.column_name,
            )

            if key in rules_by_key:
                raise ValueError(
                    f"La hoja '{header.sheet_name}' contiene "
                    f"más de un encabezado llamado "
                    f"'{header.column_name}'."
                )

            validation = validations.get(
                header.column_name,
                {},
            )

            if not isinstance(validation, dict):
                raise ValueError(
                    f"La validación de '{header.column_name}' "
                    f"en la hoja '{ws.title}' debe ser un diccionario."
                )

            rules_by_key[key] = rule
            validations_by_key[key] = validation


    # --------------------------------------------------------
    # 4. CONSTRUIR LA HOJA AUXILIAR DE LISTAS DESPLEGABLES
    # --------------------------------------------------------

    unique_list_rules = _dedup_rules_with_lists(
        all_headers,
        rules_by_key,
    )

    defined_names = build_helper_sheet(
        workbook,
        unique_list_rules,
    )

    # --------------------------------------------------------
    # 5. OBTENER LAS LETRAS DE COLUMNA DE CADA HOJA
    # --------------------------------------------------------

    column_letters_by_sheet: dict[
        str,
        dict[str, str],
    ] = {}

    for ws in data_sheets:

        column_letters_by_sheet[ws.title] = {
            header.column_name: header.column_letter
            for header in read_headers(ws)
        }

    # --------------------------------------------------------
    # 6. CONSTRUIR Y APLICAR LAS VALIDACIONES
    # --------------------------------------------------------

    for ws in data_sheets:

        headers = [
            header
            for header in all_headers
            if header.sheet_name == ws.title
        ]

        for header in headers:

            key = (
                header.sheet_name,
                header.column_name,
            )

            rule = rules_by_key[key]

            validation_config = validations_by_key.get(
                key,
                {},
            )

            applied: list[str] = []

            # Las validaciones se aplican desde la fila 2,
            # porque la fila 1 contiene los encabezados.
            data_range = (
                f"{header.column_letter}2:"
                f"{header.column_letter}{DATA_ROWS_TO_COVER}"
            )

            # Resolver la regla de negocio considerando
            # tanto la hoja como el nombre de la columna.
            business_rule = resolve_business_rule(
                configuration,
                column_name=rule.column_name,
                sheet_name=ws.title,
            )

            business_kind = (
                business_rule.get("kind")
                if business_rule
                else None
            )

            # ------------------------------------------------
            # A. IDENTIFICAR LAS RESTRICCIONES DE LA COLUMNA
            # ------------------------------------------------

            has_list = bool(rule.allowed_values)

            has_business_rule = (
                business_kind in SUPPORTED_BUSINESS_RULES
            )

            has_type_rule = _has_type_validation(rule)

            # ------------------------------------------------
            # B. CONSTRUIR LA VALIDACIÓN NATIVA PRIORITARIA
            # ------------------------------------------------

            validation: DataValidation | None = None

            # Prioridad 1: lista desplegable.
            #
            # Se conserva el desplegable porque permite al usuario
            # seleccionar directamente un código del catálogo.
            if has_list:

                defined_name = defined_names.get(
                    rule.column_name
                )

                if not defined_name:
                    raise ValueError(
                        f"No se encontró el rango definido "
                        f"para la lista de la columna "
                        f"'{rule.column_name}' en la hoja "
                        f"'{ws.title}'."
                    )

                validation = build_list_validation(
                    rule,
                    defined_name,
                )

                applied.append(
                    "lista_desplegable"
                )

            # Prioridad 2: regla de negocio.
            #
            # Si no existe lista, se aplica la regla de negocio
            # cuando tiene un constructor nativo disponible.
            elif has_business_rule:

                validation = _build_business_validation(
                    business_rule=business_rule,
                    rule=rule,
                    column_letter=header.column_letter,
                    column_letters_by_sheet=column_letters_by_sheet,
                    sheet_name=ws.title,
                )

                if validation is not None:
                    applied.append(
                        f"regla_negocio:{business_kind}"
                    )

            # Prioridad 3: tipo y longitud.
            #
            # Se aplica cuando no existe lista ni regla de negocio
            # que tenga prioridad.
            # que tenga prioridad.
            elif has_type_rule:

                validation = build_type_validation(
                    rule,
                    header.column_letter,
                )

                if validation is not None:
                    applied.append(
                        f"tipo:{rule.datatype.value}"
                    )

            # Las reglas de consistencia entre filas son
            # responsabilidad exclusiva del validador post-hoc.
            if business_kind == "cross_row_consistency_note":

                applied.append(
                    "post_hoc:consistencia_entre_filas"
                )

            elif (
                business_kind
                and business_kind not in SUPPORTED_BUSINESS_RULES
            ):

                applied.append(
                    f"post_hoc:regla_negocio:{business_kind}"
                )
            # ------------------------------------------------
            # C. APLICAR LA VALIDACIÓN NATIVA
            # ------------------------------------------------

            if validation is not None:

                _apply_validation(
                    ws,
                    validation,
                    data_range,
                )

            # ------------------------------------------------
            # D. REGISTRAR RESTRICCIONES PENDIENTES
            # ------------------------------------------------

            # Si se aplicó una lista, la validación de tipo
            # y las reglas de negocio adicionales no quedan
            # combinadas en Excel.
            #
            # El post-hoc debe comprobarlas.
            if has_list:

                if has_type_rule:
                    applied.append(
                        "post_hoc:"
                        + _get_type_validation_description(rule)
                    )

                if has_business_rule:
                    applied.append(
                        f"post_hoc:regla_negocio:{business_kind}"
                    )

            # Si se aplicó una regla de negocio, la validación
            # general de tipo o longitud no se combinó con ella.
            elif has_business_rule:

                if has_type_rule:
                    applied.append(
                        "post_hoc:"
                        + _get_type_validation_description(rule)
                    )

            # Las reglas de consistencia entre filas son
            # responsabilidad exclusiva del validador post-hoc.
            if business_kind == "cross_row_consistency_note":

                applied.append(
                    "post_hoc:consistencia_entre_filas"
                )
                
            # ------------------------------------------------
            # E. RESTRICCIONES DE validations.yaml
            # ------------------------------------------------

            configured_constraints = (
                _get_configured_post_hoc_constraints(
                    validation_config
                )
            )

            applied.extend(configured_constraints)

            # ------------------------------------------------
            # E. DETERMINAR SI REQUIERE REVISIÓN POST-HOC
            # ------------------------------------------------

            # Requiere revisión cuando:
            #   - La regla original indica revisión manual.
            #   - Hay restricciones que no se combinaron
            #     en la validación nativa.
            #   - Existe una regla de negocio no soportada.
            #   - Hay una regla de consistencia entre filas.
            #
            # El post-hoc sigue siendo obligatorio para validar
            # completamente el contenido del workbook.
            needs_review = (
                rule.needs_manual_review
                or any(
                    item.startswith("post_hoc:")
                    for item in applied
                )
            )

            # ------------------------------------------------
            # F. REGISTRAR EL RESULTADO DE LA COLUMNA
            # ------------------------------------------------

            reports.append(
                ColumnReport(
                    sheet_name=ws.title,
                    column_name=rule.column_name,
                    rule=rule,
                    validations_applied=applied.copy(),
                    needs_review=needs_review,
                )
            )

    return reports
