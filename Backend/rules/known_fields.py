
"""Aplica el catálogo de known_fields.yaml como complemento de reglas.

Este módulo completa los atributos que no pudieron interpretarse
desde los comentarios de Excel.

La configuración específica de cada plantilla y hoja tiene prioridad
como fuente de configuración. El catálogo global anterior se conserva
únicamente para mantener compatibilidad con las plantillas no migradas.
"""

from __future__ import annotations

from pathlib import Path
import re

import yaml

from backend.rules.general_model import AllowedValue, DataType, ValidationRule


# ============================================================
# CONFIGURACIÓN
# ============================================================

_CATALOG_PATH = (
    Path(__file__).parent
    / "patterns"
    / "known_fields.yaml"
)


# Traducción de los tipos definidos en YAML a DataType.
_DATATYPE_MAP = {
    "integer": DataType.INTEGER,
    "decimal": DataType.DECIMAL,
    "alphanumeric": DataType.ALPHANUMERIC,
    "alphabetic": DataType.ALPHABETIC,
    "text": DataType.TEXT,
    "date": DataType.DATE,
}


# ============================================================
# CARGA DEL CATÁLOGO LEGACY
# ============================================================

def _load_catalog() -> dict:
    """Carga el catálogo global anterior de campos conocidos."""

    if not _CATALOG_PATH.exists():
        return {}

    with open(
        _CATALOG_PATH,
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file) or {}


_CATALOG = _load_catalog()


# ============================================================
# COMPLEMENTO DE REGLAS
# ============================================================

def apply_known_field_fallback(
    rule: ValidationRule,
    known_fields: dict | None = None,
    sheet_name: str | None = None,
) -> ValidationRule:
    """
    Completa los atributos que no pudieron interpretarse
    desde el comentario del Excel.

    Puede recibir reglas específicas de una hoja. Si no recibe
    configuración externa, utiliza el catálogo global anterior.

    No sobrescribe atributos que ya fueron interpretados.
    """

    catalog = (
        known_fields
        if known_fields is not None
        else _CATALOG
    )

    # --------------------------------------------------------
    # 1. Localizar la definición del campo.
    # --------------------------------------------------------

    if "sheets" in catalog:

        sheets = catalog.get(
            "sheets",
            {},
        )

        sheet_rules = sheets.get(
            sheet_name,
            {},
        )

        entry = sheet_rules.get(
            rule.column_name,
            {},
        )

    else:
        # Compatibilidad con el formato global anterior.
        entry = catalog.get(
            rule.column_name,
            {},
        )

    if not isinstance(entry, dict) or not entry:
        return rule

    # --------------------------------------------------------
    # 2. Completar el tipo de dato.
    # --------------------------------------------------------

    if (
        rule.datatype == DataType.UNKNOWN
        and "datatype" in entry
    ):
        datatype_name = str(
            entry["datatype"]
        ).lower()

        rule.datatype = _DATATYPE_MAP.get(
            datatype_name,
            DataType.UNKNOWN,
        )

    # --------------------------------------------------------
    # 3. Completar restricciones de longitud.
    # --------------------------------------------------------

    if (
        rule.max_length is None
        and "max_length" in entry
    ):
        rule.max_length = entry["max_length"]

    if (
        rule.min_length is None
        and "min_length" in entry
    ):
        rule.min_length = entry["min_length"]

    if (
        rule.exact_length is None
        and "exact_length" in entry
    ):
        rule.exact_length = entry["exact_length"]

    # --------------------------------------------------------
    # 4. Completar obligatoriedad.
    # --------------------------------------------------------
    
    
    es_obligatorio = re.search(
        r"\bobligatorio\b",
        rule.raw_comment or "",
        re.IGNORECASE,
    )
    es_opcional = re.search(
        r"\bopcional\b",
        rule.raw_comment or "",
        re.IGNORECASE,
    )

    if (
        not es_obligatorio
        and not es_opcional
        and not rule.conditional_requirement
        and "required" in entry
    ):
        rule.required = entry["required"]

    # --------------------------------------------------------
    # 5. Completar valores permitidos.
    # --------------------------------------------------------

    if (
        not rule.allowed_values
        and "allowed_values" in entry
    ):
        rule.allowed_values = [
            AllowedValue(
                code=str(value["code"]),
                label=value["label"],
            )
            for value in entry["allowed_values"]
        ]

    # --------------------------------------------------------
    # 6. Completar descripción.
    # --------------------------------------------------------

    if (
        not rule.description
        and "description" in entry
    ):
        rule.description = entry["description"]

    # --------------------------------------------------------
    # 7. Actualizar estado de revisión manual.
    # --------------------------------------------------------

    if rule.datatype != DataType.UNKNOWN:
        rule.unparsed_fragments = [
            fragment
            for fragment in rule.unparsed_fragments
            if fragment != "(sin comentario)"
        ]

    return rule
