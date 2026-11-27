"""
Carga, valida y consolida las configuraciones del motor SNIES.

Responsabilidades:
    - Cargar archivos YAML.
    - Combinar configuraciones comunes y específicas.
    - Mantener compatibilidad con la arquitectura anterior.
    - Construir configuraciones independientes por hoja.
    - Incorporar los campos conocidos globales.
    - Cargar perfiles estructurales de plantillas.
    - Resolver reglas de negocio.

Prioridad de configuración:
    - La configuración específica de una plantilla prevalece
      sobre la configuración común.
    - Las reglas específicas de una hoja prevalecen sobre
      los campos conocidos globales.
    - Los comentarios de Excel siguen teniendo prioridad
      sobre los valores complementarios de known_fields.

Este módulo no interpreta comentarios ni ejecuta validaciones.
Su responsabilidad es entregar configuraciones consistentes
a los módulos que realizan esas tareas.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ============================================================
# RUTAS DE CONFIGURACIÓN
# ============================================================

RULES_DIR = Path(__file__).resolve().parent / "patterns"

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

COMMON_DIR = RULES_DIR / "common"


# ============================================================
# MODELO DE CONFIGURACIÓN
# ============================================================


@dataclass(frozen=True)
class RuleConfiguration:
    """
    Configuración consolidada del motor de validación SNIES.
    """

    # Campos conocidos globales y específicos por hoja.
    known_fields: dict[str, Any] = field(default_factory=dict)

    # Reglas de negocio globales y específicas.
    business_rules: dict[str, Any] = field(default_factory=dict)

    # Estructura de compatibilidad con la arquitectura anterior.
    validation_config: dict[str, Any] = field(default_factory=dict)

    # Reglas generales.
    common_rules: dict[str, Any] = field(default_factory=dict)

    # Reglas específicas de la plantilla.
    template_rules: dict[str, Any] = field(default_factory=dict)

    # Validaciones generales.
    common_validations: dict[str, Any] = field(default_factory=dict)

    # Validaciones específicas.
    template_validations: dict[str, Any] = field(default_factory=dict)

    # Perfil estructural de la plantilla.
    template_profile: dict[str, Any] = field(default_factory=dict)

    # Nombre de la plantilla cargada.
    template_name: str | None = None

    # Configuración independiente de cada hoja.
    sheet_configurations: dict[str, dict[str, Any]] = field(default_factory=dict)


# ============================================================
# UTILIDADES GENERALES
# ============================================================


def _validate_mapping(
    value: Any,
    context: str,
) -> dict[str, Any]:
    """
    Comprueba que una sección de configuración sea un diccionario.
    """

    if not isinstance(value, dict):
        raise ValueError(f"La sección '{context}' debe ser un diccionario.")

    return value


def _validate_sheet_names(
    sheet_names: Any,
    context: str,
) -> list[str]:
    """
    Valida una lista de nombres de hojas.

    Rechaza nombres vacíos y duplicados, ignorando diferencias
    de mayúsculas y espacios exteriores.
    """

    if not isinstance(sheet_names, list):
        raise ValueError(f"'{context}' debe ser una lista.")

    result: list[str] = []
    seen: set[str] = set()

    for index, sheet_name in enumerate(sheet_names):

        if not isinstance(sheet_name, str) or not sheet_name.strip():
            raise ValueError(
                f"Nombre de hoja inválido en '{context}', " f"posición {index + 1}."
            )

        normalized = sheet_name.strip().casefold()

        if normalized in seen:
            raise ValueError(
                f"El nombre de hoja '{sheet_name}' está duplicado " f"en '{context}'."
            )

        seen.add(normalized)
        result.append(sheet_name.strip())

    return result


def _collect_sheet_names(
    *groups: Any,
) -> list[str]:
    """
    Combina nombres de hojas conservando el orden de aparición.

    Evita utilizar set() para que la construcción de las
    configuraciones sea determinista.
    """

    result: list[str] = []
    seen: set[str] = set()

    for group in groups:

        if not isinstance(group, (list, dict)):
            raise ValueError(
                "La configuración de hojas debe ser una lista " "o un diccionario."
            )

        names = list(group.keys()) if isinstance(group, dict) else group

        for sheet_name in names:

            if not isinstance(sheet_name, str) or not sheet_name.strip():
                raise ValueError(
                    "Se encontró un nombre de hoja inválido " "en la configuración."
                )

            normalized = sheet_name.strip().casefold()

            if normalized not in seen:
                seen.add(normalized)
                result.append(sheet_name.strip())

    return result


# ============================================================
# CARGA DE ARCHIVOS YAML
# ============================================================


def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    Carga un archivo YAML.

    Comportamiento:
        - Si no existe, devuelve un diccionario vacío.
        - Si está vacío, devuelve un diccionario vacío.
        - Si su contenido no es un diccionario, genera un error.
        - Si contiene YAML inválido, informa el archivo afectado.

    La función no decide si un archivo es obligatorio.
    Esa decisión corresponde al proceso que carga cada arquitectura.
    """

    if not file_path.exists():
        return {}

    if not file_path.is_file():
        raise ValueError(f"La ruta de configuración no es un archivo: {file_path}")

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ValueError(f"El archivo '{file_path}' contiene YAML inválido.") from exc

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"El YAML debe contener un diccionario: {file_path}")

    return data


# ============================================================
# COMBINACIÓN DE DICCIONARIOS
# ============================================================


def _merge_dicts(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """
    Combina dos diccionarios de configuración.

    La configuración override tiene prioridad sobre base.

    Los diccionarios anidados se combinan recursivamente.
    Las listas y los demás tipos se reemplazan completamente.

    No modifica los diccionarios originales.
    """

    result = deepcopy(base)

    for key, value in override.items():

        if key in result and isinstance(result[key], dict) and isinstance(value, dict):

            result[key] = _merge_dicts(
                result[key],
                value,
            )

        else:
            result[key] = deepcopy(value)

    return result


# ============================================================
# EXTRACCIÓN DE CATÁLOGOS
# ============================================================


def _extract_master_tables(
    catalogs: dict[str, Any],
) -> dict[str, Any]:
    """
    Extrae las definiciones de catálogos.

    Admite estas dos estructuras:

        master_tables:
            catalogo:
                file: ...

    O un diccionario que contiene directamente los catálogos.
    """

    catalogs = _validate_mapping(
        catalogs,
        "catalogs",
    )

    master_tables = catalogs.get(
        "master_tables",
        catalogs,
    )

    return _validate_mapping(
        master_tables,
        "master_tables",
    )


# ============================================================
# CONSTRUCCIÓN DE CAMPOS CONOCIDOS POR HOJA
# ============================================================


def _build_known_fields(
    legacy_known_fields: dict[str, Any],
    merged_rules: dict[str, Any],
    template_profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Construye el catálogo de campos conocidos por hoja.

    Combina:
        1. Campos conocidos globales de known_fields.yaml.
        2. Reglas comunes de rules.yaml.
        3. Reglas específicas de cada plantilla y hoja.

    Prioridad:
        Los campos específicos de una hoja prevalecen sobre
        los campos conocidos globales.

    Se incluyen las hojas declaradas en el perfil aunque
    no tengan reglas propias.

    La estructura resultante es compatible con
    apply_known_field_fallback().
    """

    legacy_known_fields = _validate_mapping(
        legacy_known_fields,
        "known_fields",
    )

    merged_rules = _validate_mapping(
        merged_rules,
        "merged_rules",
    )

    template_profile = _validate_mapping(
        template_profile,
        "template_profile",
    )

    rules_by_sheet = _validate_mapping(
        merged_rules.get("sheets", {}),
        "rules.sheets",
    )

    profile_sheets = _validate_sheet_names(
        template_profile.get("sheets", []),
        "template_profile.sheets",
    )

    # Combinar las hojas del perfil y las hojas de rules.yaml.
    sheet_names = _collect_sheet_names(
        profile_sheets,
        rules_by_sheet,
    )

    known_fields_by_sheet: dict[str, dict[str, Any]] = {}

    for sheet_name in sheet_names:

        sheet_rules = rules_by_sheet.get(
            sheet_name,
            {},
        )

        sheet_rules = _validate_mapping(
            sheet_rules,
            f"rules.sheets.{sheet_name}",
        )

        # Las reglas específicas prevalecen sobre las globales.
        known_fields_by_sheet[sheet_name] = _merge_dicts(
            legacy_known_fields,
            sheet_rules,
        )

    return {
        "sheets": known_fields_by_sheet,
    }


# ============================================================
# CONSTRUCCIÓN DE CONFIGURACIONES POR HOJA
# ============================================================


def _build_sheet_configurations(
    merged_rules: dict[str, Any],
    merged_validations: dict[str, Any],
    master_tables: dict[str, Any],
    template_profile: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Construye una configuración independiente para cada hoja.

    Las reglas comunes ya deben haberse combinado con las
    específicas antes de llamar a esta función.

    Se incluyen también las hojas del perfil aunque no tengan
    reglas o validaciones particulares.
    """

    rules_by_sheet = _validate_mapping(
        merged_rules.get("sheets", {}),
        "rules.sheets",
    )

    validations_by_sheet = _validate_mapping(
        merged_validations.get("sheets", {}),
        "validations.sheets",
    )

    profile_sheets = _validate_sheet_names(
        template_profile.get("sheets", []),
        "template_profile.sheets",
    )

    sheet_names = _collect_sheet_names(
        profile_sheets,
        rules_by_sheet,
        validations_by_sheet,
    )

    sheet_configurations: dict[str, dict[str, Any]] = {}

    for sheet_name in sheet_names:

        sheet_rules = _validate_mapping(
            rules_by_sheet.get(sheet_name, {}),
            f"rules.sheets.{sheet_name}",
        )

        sheet_validations = _validate_mapping(
            validations_by_sheet.get(sheet_name, {}),
            f"validations.sheets.{sheet_name}",
        )

        # Comprobar que todos los catálogos referenciados
        # estén definidos en catalogs.yaml.
        for column_name, validation in sheet_validations.items():

            validation = _validate_mapping(
                validation,
                f"validations.sheets.{sheet_name}.{column_name}",
            )

            catalog_name = validation.get("catalog")

            if catalog_name is not None:

                if not isinstance(catalog_name, str) or not catalog_name.strip():
                    raise ValueError(
                        f"El catálogo de '{column_name}' en "
                        f"'{sheet_name}' debe ser un nombre válido."
                    )

                if catalog_name not in master_tables:
                    raise ValueError(
                        f"El campo '{column_name}' de la hoja "
                        f"'{sheet_name}' referencia el catálogo "
                        f"'{catalog_name}', pero no está definido "
                        "en catalogs.yaml."
                    )

        sheet_configurations[sheet_name] = {
            "rules": deepcopy(sheet_rules),
            "validations": deepcopy(sheet_validations),
            "catalogs": deepcopy(master_tables),
        }

    return sheet_configurations


# ============================================================
# CARGA DE CONFIGURACIÓN ANTERIOR
# ============================================================


def _load_legacy_configuration(
    directory: Path,
) -> RuleConfiguration:
    """
    Mantiene compatibilidad con la estructura YAML anterior.

    Se utiliza durante la migración progresiva de las plantillas.
    """

    known_fields = load_yaml_file(directory / "known_fields.yaml")

    business_rules = load_yaml_file(directory / "business_rules.yaml")

    validation_file = load_yaml_file(directory / "validation_rules.yaml")

    validation_config = validation_file.get(
        "validation_config",
        {},
    )

    validation_config = _validate_mapping(
        validation_config,
        "validation_config",
    )

    return RuleConfiguration(
        known_fields=known_fields,
        business_rules=business_rules,
        validation_config=validation_config,
    )


# ============================================================
# CARGA DEL PERFIL DE PLANTILLA
# ============================================================


def _load_template_profile(
    template_name: str,
    directory: Path,
) -> dict[str, Any]:
    """
    Carga el perfil estructural individual de una plantilla.
    """

    profile_path = directory /  "template_profile.yaml"

    if not profile_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el perfil estructural "
            f"de '{template_name}': {profile_path}"
        )

    profile = load_yaml_file(profile_path)

    main_sheet = profile.get("main_sheet")

    if not isinstance(main_sheet, str) or not main_sheet.strip():
        raise ValueError(
            f"El perfil de '{template_name}' " "no tiene una hoja principal válida."
        )

    sheets = _validate_sheet_names(
        profile.get("sheets"),
        f"template_profile.{template_name}.sheets",
    )

    normalized_sheets = {sheet.strip().casefold() for sheet in sheets}

    if main_sheet.strip().casefold() not in normalized_sheets:
        raise ValueError(
            f"La hoja principal '{main_sheet}' no está "
            f"incluida en las hojas declaradas del perfil "
            f"de '{template_name}'."
        )

    return profile


# ============================================================
# CARGA DE LA NUEVA ARQUITECTURA
# ============================================================


def _load_template_configuration(
    template_name: str,
    directory: Path,
) -> RuleConfiguration:
    """
    Carga exclusivamente la configuración de una plantilla.

    No hereda reglas, validaciones ni reglas de negocio
    de otras plantillas o archivos globales.
    """

    template_dir = directory / template_name.lower()

    if not template_dir.is_dir():
        raise FileNotFoundError(
            f"No existe la configuración de la plantilla "
            f"'{template_name}': {template_dir}"
        )

    # --------------------------------------------------------
    # 1. COMPROBAR ARCHIVOS OBLIGATORIOS
    # --------------------------------------------------------

    required_files = [
        "rules.yaml",
        "validations.yaml",
        "catalogs.yaml",
        "template_profile.yaml",
    ]

    for file_name in required_files:
        file_path = template_dir / file_name

        if not file_path.is_file():
            raise FileNotFoundError(
                f"La plantilla '{template_name}' no tiene "
                f"el archivo obligatorio '{file_name}'."
            )

    # --------------------------------------------------------
    # 2. CARGAR CONFIGURACIÓN PROPIA DE LA PLANTILLA
    # --------------------------------------------------------

    template_rules = load_yaml_file(
        template_dir / "rules.yaml"
    )

    template_validations = load_yaml_file(
        template_dir / "validations.yaml"
    )

    template_catalogs = load_yaml_file(
        template_dir / "catalogs.yaml"
    )

    # Este archivo es opcional.
    business_rules = load_yaml_file(
        template_dir / "business_rules.yaml"
    )

    # --------------------------------------------------------
    # 3. CARGAR PERFIL ESTRUCTURAL
    # --------------------------------------------------------

    template_profile = _load_template_profile(
        template_name,
        template_dir,
    )

    # --------------------------------------------------------
    # 4. VALIDAR ESTRUCTURA DE CONFIGURACIONES
    # --------------------------------------------------------

    template_rules = _validate_mapping(
        template_rules,
        f"{template_name}.rules",
    )

    template_validations = _validate_mapping(
        template_validations,
        f"{template_name}.validations",
    )

    business_rules = _validate_mapping(
        business_rules,
        f"{template_name}.business_rules",
    )

    master_tables = _extract_master_tables(
        template_catalogs
    )

    # --------------------------------------------------------
    # 5. CONSTRUIR CAMPOS CONOCIDOS
    # --------------------------------------------------------

    # Cada plantilla utiliza exclusivamente sus propias reglas.
    known_fields = _build_known_fields(
        {},
        template_rules,
        template_profile,
    )

    # --------------------------------------------------------
    # 6. CONSTRUIR CONFIGURACIONES POR HOJA
    # --------------------------------------------------------

    sheet_configurations = _build_sheet_configurations(
        template_rules,
        template_validations,
        master_tables,
        template_profile,
    )

    # --------------------------------------------------------
    # 7. ESTRUCTURA DE COMPATIBILIDAD
    # --------------------------------------------------------

    validation_config = {
        "column_rules": template_validations.get(
            "column_rules",
            {},
        ),
        "master_tables": master_tables,
    }

    # --------------------------------------------------------
    # 8. DEVOLVER CONFIGURACIÓN
    # --------------------------------------------------------

    return RuleConfiguration(
        known_fields=known_fields,
        business_rules=business_rules,
        validation_config=validation_config,
        common_rules={},
        template_rules=template_rules,
        common_validations={},
        template_validations=template_validations,
        template_profile=template_profile,
        template_name=template_name,
        sheet_configurations=sheet_configurations,
    )

# ============================================================
# FUNCIÓN PÚBLICA DE CARGA
# ============================================================


def load_rule_configuration(
    template_name: str | None = None,
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    """
    Carga la configuración del motor SNIES.

    Con template_name:
        Carga exclusivamente la configuración de esa plantilla
        desde el directorio de plantillas.

    Sin template_name:
        Mantiene temporalmente la carga legacy.
    """

    # Compatibilidad temporal con la arquitectura anterior.
    if template_name is None:
        directory = Path(rules_dir) if rules_dir is not None else RULES_DIR

        return _load_legacy_configuration(directory.resolve())

    if not isinstance(template_name, str) or not template_name.strip():
        raise ValueError("'template_name' debe ser un texto no vacío.")

    template_name = template_name.strip().upper()

    directory = Path(rules_dir) if rules_dir is not None else TEMPLATES_DIR

    directory = directory.resolve()

    return _load_template_configuration(
        template_name,
        directory,
    )


# ============================================================
# ALIAS DE COMPATIBILIDAD
# ============================================================


def load_config(
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    """
    Alias de compatibilidad con llamadas anteriores.
    """

    return load_rule_configuration(
        rules_dir=rules_dir,
    )


# ============================================================
# RESOLUCIÓN DE REGLAS DE NEGOCIO
# ============================================================


def resolve_business_rule(
    configuration: RuleConfiguration,
    column_name: str,
    sheet_name: str | None = None,
) -> dict[str, Any] | None:
    """
    Busca una regla de negocio para una columna.

    Prioridad:
        1. Regla específica de hoja.
        2. Regla global.

    La comparación de nombres de hojas ignora diferencias
    de mayúsculas y espacios exteriores.
    """

    business_rules = configuration.business_rules

    if sheet_name:

        if not isinstance(sheet_name, str):
            raise ValueError("'sheet_name' debe ser un texto.")

        scoped_rules = business_rules.get(
            "sheet_scoped_rules",
            {},
        )

        scoped_rules = _validate_mapping(
            scoped_rules,
            "business_rules.sheet_scoped_rules",
        )

        normalized_sheet = sheet_name.strip().casefold()

        for configured_sheet, sheet_rules in scoped_rules.items():

            if (
                not isinstance(configured_sheet, str)
                or configured_sheet.strip().casefold() != normalized_sheet
            ):
                continue

            sheet_rules = _validate_mapping(
                sheet_rules,
                f"business_rules.sheet_scoped_rules.{configured_sheet}",
            )

            rule = sheet_rules.get(column_name)

            if isinstance(rule, dict):
                return rule

            break

    global_rule = business_rules.get(column_name)

    if isinstance(global_rule, dict):
        return global_rule

    return None


# ============================================================
# OBTENER REGLAS DE NEGOCIO GLOBALES
# ============================================================


def get_global_business_rules(
    configuration: RuleConfiguration,
) -> dict[str, dict[str, Any]]:
    """
    Devuelve exclusivamente las reglas globales asociadas
    directamente a columnas.

    Excluye:
        - sheet_scoped_rules
        - conditional_required_fields

    Las reglas específicas por hoja se consultan mediante
    resolve_business_rule().

    Las condiciones de obligatoriedad tienen su propio
    mecanismo de evaluación.
    """

    excluded_sections = {
        "sheet_scoped_rules",
        "conditional_required_fields",
    }

    return {
        column_name: rule
        for column_name, rule in configuration.business_rules.items()
        if (column_name not in excluded_sections and isinstance(rule, dict))
    }
