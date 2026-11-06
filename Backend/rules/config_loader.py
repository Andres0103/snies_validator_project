from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# CONFIGURACIÓN DE RUTAS
# ============================================================

RULES_DIR = Path(__file__).resolve().parent / "patterns"


# ============================================================
# MODELO DE CONFIGURACIÓN
# ============================================================

@dataclass(frozen=True)
class RuleConfiguration:
    """
    Representa la configuración centralizada del motor SNIES.
    """

    known_fields: dict[str, dict[str, Any]]
    business_rules: dict[str, Any]


# ============================================================
# CARGADOR YAML
# ============================================================

def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    Carga un archivo YAML y devuelve su contenido como diccionario.
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


# ============================================================
# CARGA CENTRALIZADA
# ============================================================

def load_rule_configuration(
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    """
    Carga todos los catálogos YAML del sistema.

    Permite utilizar una ruta alternativa para facilitar pruebas.
    """

    directory = Path(rules_dir) if rules_dir else RULES_DIR

    return RuleConfiguration(
        known_fields=load_yaml_file(
            directory / "known_fields.yaml"
        ),
        business_rules=load_yaml_file(
            directory / "business_rules.yaml"
        ),
    )


# Alias para conservar el nombre que utilizamos en los primeros pasos.
def load_config(
    rules_dir: Path | str | None = None,
) -> RuleConfiguration:
    return load_rule_configuration(rules_dir)


# ============================================================
# RESOLUCIÓN DE REGLAS DE NEGOCIO
# ============================================================

def resolve_business_rule(
    configuration: RuleConfiguration,
    column_name: str,
    sheet_name: str | None = None,
) -> dict[str, Any] | None:
    """
    Busca la regla correspondiente a una columna.

    Prioridad:
        1. Regla específica de hoja.
        2. Regla global de columna.
        3. None si no existe.
    """

    business_rules = configuration.business_rules

    # Primero buscamos la regla específica de la hoja.
    if sheet_name:
        scoped_rules = business_rules.get(
            "sheet_scoped_rules", {}
        )

        if isinstance(scoped_rules, dict):
            sheet_rules = scoped_rules.get(sheet_name, {})

            if isinstance(sheet_rules, dict):
                rule = sheet_rules.get(column_name)

                if isinstance(rule, dict):
                    return rule

    # Después buscamos la regla global.
    global_rule = business_rules.get(column_name)

    if isinstance(global_rule, dict):
        return global_rule

    return None


# ============================================================
# OBTENCIÓN DE REGLAS GLOBALES
# ============================================================

def get_global_business_rules(
    configuration: RuleConfiguration,
) -> dict[str, dict[str, Any]]:
    """
    Devuelve únicamente las reglas globales.

    Excluye sheet_scoped_rules porque estas reglas
    pertenecen exclusivamente a determinadas hojas.
    """

    return {
        column_name: rule
        for column_name, rule in configuration.business_rules.items()
        if column_name != "sheet_scoped_rules"
        and isinstance(rule, dict)
    }