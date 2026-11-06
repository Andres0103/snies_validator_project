"""Aplica el catálogo de `known_fields.yaml` como relleno de huecos.

Este módulo NUNCA sobre-escribe lo que el comentario de la celda ya logró
comunicar; solo completa lo que quedó en blanco (datatype UNKNOWN, o sin
`allowed_values`). Esto respeta la regla de que el comentario del Excel es
la fuente de verdad principal: el catálogo es un auxiliar, no un reemplazo.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from rules.models import AllowedValue, DataType, ValidationRule

_CATALOG_PATH = Path(__file__).parent / "patterns" / "known_fields.yaml"

_DATATYPE_MAP = {
    "integer": DataType.INTEGER,
    "decimal": DataType.DECIMAL,
    "alphanumeric": DataType.ALPHANUMERIC,
    "alphabetic": DataType.ALPHABETIC,
    "text": DataType.TEXT,
    "date": DataType.DATE,
}


def _load_catalog() -> dict:
    if not _CATALOG_PATH.exists():
        return {}
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_CATALOG = _load_catalog()


def apply_known_field_fallback(rule: ValidationRule) -> ValidationRule:
    """Completa huecos en `rule` usando el catálogo, si el nombre de columna coincide."""
    entry = _CATALOG.get(rule.column_name)
    if not entry:
        return rule

    if rule.datatype == DataType.UNKNOWN and "datatype" in entry:
        rule.datatype = _DATATYPE_MAP.get(entry["datatype"], DataType.UNKNOWN)

    if rule.max_length is None and "max_length" in entry:
        rule.max_length = entry["max_length"]

    if not rule.required and not rule.conditional_requirement and entry.get("required"):
        rule.required = True

    if not rule.allowed_values and "allowed_values" in entry:
        rule.allowed_values = [
            AllowedValue(code=str(v["code"]), label=v["label"])
            for v in entry["allowed_values"]
        ]

    if not rule.description and "description" in entry:
        rule.description = entry["description"]

    # Ya no necesita revisión manual solo por falta de tipo, si el catálogo
    # lo resolvió.
    if rule.datatype != DataType.UNKNOWN:
        rule.unparsed_fragments = [
            f for f in rule.unparsed_fragments if f != "(sin comentario)"
        ]

    return rule
def apply_known_field_overrides(rule: ValidationRule) -> ValidationRule:
    """Aplica reglas autoritativas del manual que prevalecen sobre el comentario."""
    if rule.column_name == "DESCRIPCION_CONSULTORIA":
        rule.datatype = DataType.ALPHANUMERIC
        rule.max_length = 200
        rule.required = True

    return rule
