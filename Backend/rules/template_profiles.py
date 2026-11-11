
"""
Carga, valida y detecta perfiles de plantillas SNIES.

Los perfiles describen la estructura de cada plantilla:

    - Hoja principal.
    - Hojas que pertenecen a la plantilla.
    - Claves de identificación de registros.
    - Relaciones entre hojas principales y complementarias.

Este módulo no valida datos de las hojas ni comprueba
la integridad de las relaciones. Esa responsabilidad
corresponde a los validadores posteriores.

Su responsabilidad es garantizar que la configuración
estructural sea coherente antes de utilizarla.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROFILE_PATH = (
    Path(__file__).resolve().parent
    / "patterns"
    / "template_profiles.yaml"
)


# ============================================================
# UTILIDADES
# ============================================================

def _normalize_name(value: str) -> str:
    """
    Normaliza nombres de hojas para comparaciones.

    No modifica el nombre original del perfil.

    strip():
        Elimina espacios accidentales al inicio y al final.

    casefold():
        Permite comparar nombres sin distinguir mayúsculas
        y minúsculas.
    """

    return value.strip().casefold()


def _validate_string(
    value: Any,
    context: str,
) -> str:
    """
    Comprueba que un valor sea un texto no vacío.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{context} debe ser un texto no vacío."
        )

    return value.strip()


def _validate_string_list(
    value: Any,
    context: str,
) -> list[str]:
    """
    Valida una lista de textos no vacíos.

    También detecta elementos duplicados ignorando
    diferencias de mayúsculas y espacios exteriores.
    """

    if not isinstance(value, list) or not value:
        raise ValueError(
            f"{context} debe ser una lista no vacía."
        )

    result: list[str] = []
    seen: set[str] = set()

    for index, item in enumerate(value):

        item = _validate_string(
            item,
            f"{context}, elemento {index + 1}",
        )

        normalized = _normalize_name(item)

        if normalized in seen:
            raise ValueError(
                f"{context} contiene el elemento "
                f"duplicado '{item}'."
            )

        seen.add(normalized)
        result.append(item)

    return result


# ============================================================
# VALIDACIÓN DE RELACIONES
# ============================================================

def _validate_references(
    references: Any,
    sheets: list[str],
    template_name: str,
) -> None:
    """
    Valida las relaciones entre hojas de una plantilla.

    Cada relación debe contener:

        child_sheet:
            Hoja que contiene los registros dependientes.

        parent_sheet:
            Hoja principal a la que hacen referencia.

        key:
            Columnas que identifican la relación.

    Tanto la hoja hija como la hoja padre deben estar
    declaradas dentro del perfil.
    """

    if references is None:
        return

    if not isinstance(references, list):
        raise ValueError(
            f"Las referencias de '{template_name}' "
            "deben estar definidas como una lista."
        )

    normalized_sheets = {
        _normalize_name(sheet)
        for sheet in sheets
    }

    seen_relations: set[tuple] = set()

    for index, reference in enumerate(references, start=1):

        context = (
            f"Referencia {index} de '{template_name}'"
        )

        if not isinstance(reference, dict):
            raise ValueError(
                f"{context} debe ser un diccionario."
            )

        child_sheet = _validate_string(
            reference.get("child_sheet"),
            f"{context}: child_sheet",
        )

        parent_sheet = _validate_string(
            reference.get("parent_sheet"),
            f"{context}: parent_sheet",
        )

        key = _validate_string_list(
            reference.get("key"),
            f"{context}: key",
        )

        # Comprobar que ambas hojas estén declaradas.
        if _normalize_name(child_sheet) not in normalized_sheets:
            raise ValueError(
                f"La hoja hija '{child_sheet}' de {context} "
                "no está declarada en 'sheets'."
            )

        if _normalize_name(parent_sheet) not in normalized_sheets:
            raise ValueError(
                f"La hoja padre '{parent_sheet}' de {context} "
                "no está declarada en 'sheets'."
            )

        # Una hoja no debe referenciarse a sí misma mediante
        # una relación padre-hijo de este tipo.
        if (
            _normalize_name(child_sheet)
            == _normalize_name(parent_sheet)
        ):
            raise ValueError(
                f"{context} no puede relacionar una hoja "
                "consigo misma."
            )

        # Detectar relaciones duplicadas.
        relation_key = (
            _normalize_name(child_sheet),
            _normalize_name(parent_sheet),
            tuple(
                _normalize_name(column)
                for column in key
            ),
        )

        if relation_key in seen_relations:
            raise ValueError(
                f"{context} está duplicada."
            )

        seen_relations.add(relation_key)


# ============================================================
# VALIDACIÓN DE PERFILES
# ============================================================

def _validate_profile(
    template_name: str,
    profile: Any,
) -> None:
    """
    Valida la estructura de un perfil individual.
    """

    if not isinstance(profile, dict):
        raise ValueError(
            f"El perfil '{template_name}' debe ser "
            "un diccionario."
        )

    # --------------------------------------------------------
    # 1. HOJA PRINCIPAL
    # --------------------------------------------------------

    main_sheet = _validate_string(
        profile.get("main_sheet"),
        f"El perfil '{template_name}': main_sheet",
    )

    # --------------------------------------------------------
    # 2. HOJAS DE LA PLANTILLA
    # --------------------------------------------------------

    sheets = _validate_string_list(
        profile.get("sheets"),
        f"El perfil '{template_name}': sheets",
    )

    normalized_sheets = {
        _normalize_name(sheet)
        for sheet in sheets
    }

    if _normalize_name(main_sheet) not in normalized_sheets:
        raise ValueError(
            f"La hoja principal '{main_sheet}' no está "
            f"incluida en las hojas del perfil '{template_name}'."
        )

    # --------------------------------------------------------
    # 3. CLAVE DE IDENTIFICACIÓN
    # --------------------------------------------------------

    _validate_string_list(
        profile.get("record_key"),
        f"El perfil '{template_name}': record_key",
    )

    # --------------------------------------------------------
    # 4. RELACIONES ENTRE HOJAS
    # --------------------------------------------------------

    _validate_references(
        references=profile.get("references", []),
        sheets=sheets,
        template_name=template_name,
    )


def _validate_profiles(
    profiles: dict[str, Any],
) -> None:
    """
    Valida todos los perfiles y detecta hojas principales
    duplicadas entre plantillas.

    Una misma hoja principal no puede identificar
    dos plantillas diferentes porque la detección
    resultaría ambigua.
    """

    templates = profiles.get("templates")

    if not isinstance(templates, dict) or not templates:
        raise ValueError(
            "El archivo debe contener una sección "
            "'templates' con al menos un perfil."
        )

    seen_main_sheets: dict[str, str] = {}

    for template_name, profile in templates.items():

        template_name = _validate_string(
            template_name,
            "El nombre de una plantilla",
        )

        _validate_profile(
            template_name,
            profile,
        )

        normalized_main = _normalize_name(
            profile["main_sheet"]
        )

        previous_template = seen_main_sheets.get(
            normalized_main
        )

        if previous_template is not None:
            raise ValueError(
                f"La hoja principal '{profile['main_sheet']}' "
                f"está asignada a las plantillas "
                f"'{previous_template}' y '{template_name}'."
            )

        seen_main_sheets[normalized_main] = template_name


# ============================================================
# CARGA DE PERFILES
# ============================================================

def load_template_profiles() -> dict[str, Any]:
    """
    Carga y valida los perfiles desde template_profiles.yaml.

    Retorna:
        Diccionario completo de perfiles.

    Genera:
        FileNotFoundError si el archivo no existe.
        ValueError si el YAML o su estructura son inválidos.
    """

    if not PROFILE_PATH.exists() or not PROFILE_PATH.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de perfiles: "
            f"{PROFILE_PATH}"
        )

    try:
        with PROFILE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:

            profiles = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ValueError(
            f"El archivo '{PROFILE_PATH.name}' "
            "contiene YAML inválido."
        ) from exc

    if not isinstance(profiles, dict):
        raise ValueError(
            "La configuración de perfiles debe ser "
            "un diccionario YAML."
        )

    _validate_profiles(profiles)

    return profiles


# ============================================================
# DETECCIÓN DE PLANTILLAS
# ============================================================

def detect_templates(
    sheet_names: list[str],
) -> list[str]:
    """
    Detecta las plantillas presentes en un libro Excel.

    La identificación se realiza mediante la hoja principal.

    No exige que estén presentes todas las hojas
    complementarias.

    La comparación ignora mayúsculas y espacios exteriores,
    pero conserva el nombre original del perfil en el resultado.

    Parámetros:
        sheet_names:
            Nombres de las hojas existentes en el libro.

    Retorna:
        Lista de nombres de plantillas detectadas.

    Importante:
        Esta función puede devolver varias plantillas.
        El orquestador decide si esa combinación está permitida.
    """

    if not isinstance(sheet_names, list):
        raise TypeError(
            "'sheet_names' debe ser una lista de nombres de hojas."
        )

    normalized_workbook_sheets = set()

    for sheet_name in sheet_names:

        if not isinstance(sheet_name, str):
            raise ValueError(
                "Todos los nombres de hojas deben ser textos."
            )

        normalized_workbook_sheets.add(
            _normalize_name(sheet_name)
        )

    profiles = load_template_profiles()

    detected_templates: list[str] = []

    for template_name, profile in profiles["templates"].items():

        main_sheet = profile["main_sheet"]

        if (
            _normalize_name(main_sheet)
            in normalized_workbook_sheets
        ):

            detected_templates.append(
                template_name
            )

    return detected_templates
