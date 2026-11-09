
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


RULES_DIR = Path(__file__).resolve().parent / "patterns"

TEMPLATES_DIR = RULES_DIR / "templates"
COMMON_DIR = RULES_DIR / "common"


@dataclass(frozen=True)
class RuleConfiguration:
    """
    Configuración centralizada del motor de validación SNIES.

    Permite trabajar con configuraciones comunes y específicas
    de cada plantilla.
    """

    known_fields: dict[str, dict[str, Any]] = field(default_factory=dict)

    business_rules: dict[str, Any] = field(default_factory=dict)

    validation_config: dict[str, Any] = field(default_factory=dict)

    common_rules: dict[str, Any] = field(default_factory=dict)

    template_rules: dict[str, Any] = field(default_factory=dict)

    common_validations: dict[str, Any] = field(default_factory=dict)

    template_validations: dict[str, Any] = field(default_factory=dict)

    template_profile: dict[str, Any] = field(default_factory=dict)

    template_name: str | None = None
    
    sheet_configurations: dict[str, dict[str, Any]] = field(
    default_factory=dict
)


def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    Carga un archivo YAML.

    Si el archivo no existe o está vacío, devuelve un diccionario vacío.
    Si su estructura no es un diccionario, genera un error.
    """

    if not file_path.exists():
        return {}

    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            f"El YAML debe contener un diccionario: {file_path}"
        )

    return data


def _merge_dicts(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """
    Combina dos diccionarios de configuración.

    La configuración específica tiene prioridad sobre la común.
    Los diccionarios anidados se combinan recursivamente.
    """

    result = dict(base)

    for key, value in override.items():

        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _merge_dicts(
                result[key],
                value,
            )
        else:
            result[key] = value

    return result

def _extract_master_tables(catalogs: dict[str, Any]) -> dict[str, Any]:
    """
    Extrae las definiciones de catálogos.

    Admite tanto:
        master_tables:
            catalogo: ...

    Como un diccionario que contiene directamente los catálogos.
    """

    master_tables = catalogs.get("master_tables", catalogs)

    if not isinstance(master_tables, dict):
        raise ValueError(
            "La configuración de catálogos debe contener "
            "un diccionario de tablas maestras."
        )

    return master_tables


def _build_sheet_configurations(
    merged_rules: dict[str, Any],
    merged_validations: dict[str, Any],
    master_tables: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Construye una configuración independiente para cada hoja.

    Las reglas comunes ya deben haberse combinado con las específicas
    antes de llamar a esta función.
    """

    rules_by_sheet = merged_rules.get("sheets", {})
    validations_by_sheet = merged_validations.get("sheets", {})

    if not isinstance(rules_by_sheet, dict):
        raise ValueError(
            "La sección 'sheets' de rules.yaml debe ser un diccionario."
        )

    if not isinstance(validations_by_sheet, dict):
        raise ValueError(
            "La sección 'sheets' de validations.yaml debe ser un diccionario."
        )

    sheet_names = set(rules_by_sheet) | set(validations_by_sheet)

    sheet_configurations = {}

    for sheet_name in sheet_names:
        sheet_rules = rules_by_sheet.get(sheet_name, {})
        sheet_validations = validations_by_sheet.get(sheet_name, {})

        if not isinstance(sheet_rules, dict):
            raise ValueError(
                f"Las reglas de la hoja '{sheet_name}' deben ser un diccionario."
            )

        if not isinstance(sheet_validations, dict):
            raise ValueError(
                f"Las validaciones de la hoja '{sheet_name}' "
                "deben ser un diccionario."
            )

        # Comprobar que las referencias a catálogos existan.
        for column_name, validation in sheet_validations.items():

            if not isinstance(validation, dict):
                raise ValueError(
                    f"La validación de '{column_name}' en "
                    f"'{sheet_name}' debe ser un diccionario."
                )

            catalog_name = validation.get("catalog")

            if catalog_name and catalog_name not in master_tables:
                raise ValueError(
                    f"El campo '{column_name}' de la hoja '{sheet_name}' "
                    f"referencia el catálogo '{catalog_name}', "
                    "pero no está definido en catalogs.yaml."
                )

        sheet_configurations[sheet_name] = {
            "rules": sheet_rules,
            "validations": sheet_validations,
            "catalogs": master_tables,
        }

    return sheet_configurations

def _load_legacy_configuration(
    directory: Path,
) -> RuleConfiguration:
    """
    Mantiene compatibilidad con la estructura YAML anterior.

    Se utilizará durante la migración progresiva de las plantillas.
    """

    known_fields = load_yaml_file(
        directory / "known_fields.yaml"
    )

    business_rules = load_yaml_file(
        directory / "business_rules.yaml"
    )

    validation_file = load_yaml_file(
        directory / "validation_rules.yaml"
    )

    validation_config = validation_file.get(
        "validation_config",
        {},
    )

    if not isinstance(validation_config, dict):
        raise ValueError(
            "La sección 'validation_config' debe ser un diccionario."
        )

    return RuleConfiguration(
        known_fields=known_fields,
        business_rules=business_rules,
        validation_config=validation_config,
    )


def _load_template_profile(
    template_name: str,
    directory: Path,
) -> dict[str, Any]:
    """
    Obtiene el perfil estructural de una plantilla.
    """

    profiles_file = load_yaml_file(
        directory / "template_profiles.yaml"
    )

    templates = profiles_file.get("templates", {})

    if not isinstance(templates, dict):
        raise ValueError(
            "La sección 'templates' de template_profiles.yaml "
            "debe ser un diccionario."
        )

    profile = templates.get(template_name)

    if profile is None:
        raise ValueError(
            f"No existe un perfil para la plantilla '{template_name}'."
        )

    if not isinstance(profile, dict):
        raise ValueError(
            f"El perfil de '{template_name}' debe ser un diccionario."
        )

    return profile


def _load_template_configuration(
    template_name: str,
    directory: Path,
) -> RuleConfiguration:
    """
    Carga y consolida la configuración común y específica
    de una plantilla SNIES.
    """

    common_dir = directory / "common"
    templates_dir = directory / "templates"
    template_dir = templates_dir / template_name.lower()

    if not template_dir.exists():
        raise ValueError(
            f"No existe el directorio de configuración para "
            f"la plantilla '{template_name}': {template_dir}"
        )

    # -----------------------------------------------------
    # 1. Cargar configuración común.
    # -----------------------------------------------------

    common_rules = load_yaml_file(
        common_dir / "rules.yaml"
    )

    common_validations = load_yaml_file(
        common_dir / "validations.yaml"
    )

    common_catalogs = load_yaml_file(
        common_dir / "catalogs.yaml"
    )

    common_business_rules = load_yaml_file(
        common_dir / "business_rules.yaml"
    )

    # -----------------------------------------------------
    # 2. Cargar configuración específica.
    # -----------------------------------------------------

    template_rules = load_yaml_file(
        template_dir / "rules.yaml"
    )

    template_validations = load_yaml_file(
        template_dir / "validations.yaml"
    )

    template_catalogs = load_yaml_file(
        template_dir / "catalogs.yaml"
    )

    template_business_rules = load_yaml_file(
        template_dir / "business_rules.yaml"
    )

    # -----------------------------------------------------
    # 3. Combinar reglas y validaciones.
    # -----------------------------------------------------

    merged_rules = _merge_dicts(
        common_rules,
        template_rules,
    )

    merged_validations = _merge_dicts(
        common_validations,
        template_validations,
    )

    business_rules = _merge_dicts(
        common_business_rules,
        template_business_rules,
    )

    # -----------------------------------------------------
    # 4. Combinar catálogos.
    # -----------------------------------------------------

    common_master_tables = _extract_master_tables(
        common_catalogs
    )

    template_master_tables = _extract_master_tables(
        template_catalogs
    )

    master_tables = _merge_dicts(
        common_master_tables,
        template_master_tables,
    )

    # -----------------------------------------------------
    # 5. Construir configuraciones independientes por hoja.
    # -----------------------------------------------------

    sheet_configurations = _build_sheet_configurations(
        merged_rules,
        merged_validations,
        master_tables,
    )

    # -----------------------------------------------------
    # 6. Mantener estructura de compatibilidad.
    # -----------------------------------------------------

    validation_config = {
        "column_rules": merged_validations.get(
            "column_rules",
            {},
        ),
        "master_tables": master_tables,
    }

    # -----------------------------------------------------
    # 7. Obtener perfil estructural.
    # -----------------------------------------------------

    template_profile = _load_template_profile(
        template_name,
        directory,
    )

    # -----------------------------------------------------
    # 8. Devolver configuración consolidada.
    # -----------------------------------------------------

    return RuleConfiguration(
        known_fields=merged_rules,
        business_rules=business_rules,
        validation_config=validation_config,
        common_rules=common_rules,
        template_rules=template_rules,
        common_validations=common_validations,
        template_validations=template_validations,
        template_profile=template_profile,
        template_name=template_name,
        sheet_configurations=sheet_configurations,
    )



def load_rule_configuration(
    template_name: str | None = None,
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    """
    Carga la configuración del motor SNIES.

    Sin template_name:
        Utiliza la configuración anterior para mantener compatibilidad.

    Con template_name:
        Utiliza la nueva arquitectura común + plantilla.
    """

    directory = (
        Path(rules_dir)
        if rules_dir
        else RULES_DIR
    )

    if template_name is None:
        return _load_legacy_configuration(directory)

    return _load_template_configuration(
        template_name,
        directory,
    )


def load_config(
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    """
    Alias de compatibilidad con llamadas anteriores.
    """

    return load_rule_configuration(
        rules_dir=rules_dir,
    )


def resolve_business_rule(
    configuration: RuleConfiguration,
    column_name: str,
    sheet_name: str | None = None,
) -> dict[str, Any] | None:
    """
    Busca una regla de negocio.

    Prioridad:
        1. Regla específica de hoja.
        2. Regla global.
    """

    business_rules = configuration.business_rules

    if sheet_name:
        scoped_rules = business_rules.get(
            "sheet_scoped_rules",
            {},
        )

        if isinstance(scoped_rules, dict):
            sheet_rules = scoped_rules.get(
                sheet_name,
                {},
            )

            if isinstance(sheet_rules, dict):
                rule = sheet_rules.get(column_name)

                if isinstance(rule, dict):
                    return rule

    global_rule = business_rules.get(column_name)

    if isinstance(global_rule, dict):
        return global_rule

    return None


def get_global_business_rules(
    configuration: RuleConfiguration,
) -> dict[str, dict[str, Any]]:
    """
    Devuelve las reglas globales y excluye las específicas de hoja.
    """

    return {
        column_name: rule
        for column_name, rule in configuration.business_rules.items()
        if column_name != "sheet_scoped_rules"
        and isinstance(rule, dict)
    }
