
"""Carga y detección de perfiles de plantillas SNIES."""

from pathlib import Path

import yaml


PROFILE_PATH = (
    Path(__file__).parent
    / "patterns"
    / "template_profiles.yaml"
)


def load_template_profiles() -> dict:
    """Carga los perfiles de plantillas desde YAML."""

    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de perfiles: {PROFILE_PATH}"
        )

    with open(PROFILE_PATH, "r", encoding="utf-8") as file:
        profiles = yaml.safe_load(file) or {}

    if not isinstance(profiles, dict):
        raise ValueError(
            "La configuración de perfiles debe ser un objeto YAML."
        )

    templates = profiles.get("templates")

    if not isinstance(templates, dict):
        raise ValueError(
            "El archivo debe contener una sección 'templates'."
        )

    return profiles


def detect_templates(sheet_names: list[str]) -> list[str]:
    """
    Detecta todas las plantillas presentes en un libro.

    La identificación se realiza mediante la hoja principal.
    No exige que estén presentes todas las hojas complementarias.
    """

    profiles = load_template_profiles()
    workbook_sheets = set(sheet_names)

    detected_templates = []

    for template_name, profile in profiles["templates"].items():

        main_sheet = profile.get("main_sheet")

        if main_sheet and main_sheet in workbook_sheets:
            detected_templates.append(template_name)

    return detected_templates
