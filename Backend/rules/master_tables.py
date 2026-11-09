"""Detecta referencias a catálogos y carga sus valores desde YAML."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from backend.rules.general_model import AllowedValue, ValidationRule


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOGS_DIR = PROJECT_ROOT / "catalogs"


_TRIGGER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"lista de pa[ií]ses|iso\s*3166", re.IGNORECASE),
        "paises",
    ),
    (
        re.compile(r"clasificaci[oó]n\s+cine", re.IGNORECASE),
        "cine_campo_detallado",
    ),
]


def _read_yaml(path: Path) -> Any:
    """Lee el contenido de un archivo YAML."""

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _load_paises() -> list[AllowedValue]:
    """Carga los países vigentes desde su catálogo YAML."""

    path = CATALOGS_DIR / "Tabla_paises_SNIES.yaml"
    catalog_data = _read_yaml(path)

    if not isinstance(catalog_data, dict):
        return []

    master_tables = catalog_data.get("master_tables", {})

    if not isinstance(master_tables, dict):
        return []

    paises = master_tables.get("paises", {})

    if not isinstance(paises, dict):
        return []

    records = paises.get("records", [])

    if not isinstance(records, list):
        return []

    values = [
        AllowedValue(
            code="0",
            label="No Aplica (Organismo Multilateral)",
        )
    ]

    for record in records:
        if not isinstance(record, dict):
            continue


        code = record.get("ID_PAIS")
        label = record.get("DESC_PAIS")

        if code is None or label is None:
            continue

        code_text = str(code).strip()
        label_text = str(label).strip()

        if code_text and label_text:
            values.append(
                AllowedValue(
                    code=code_text,
                    label=label_text,
                )
            )

    return values


def _load_cine_campo_detallado() -> list[AllowedValue]:
    """Carga la clasificación CINE desde su catálogo YAML."""

    path = CATALOGS_DIR / "cine_campo_detallado.yaml"
    catalog_data = _read_yaml(path)

    if not isinstance(catalog_data, dict):
        return []

    records = catalog_data.get("records", [])

    if not isinstance(records, list):
        return []

    values: list[AllowedValue] = []

    for record in records:
        if not isinstance(record, dict):
            continue

        code = record.get("codigo")
        label = record.get("descripcion")

        if code is None or label is None:
            continue

        code_text = str(code).strip()
        label_text = str(label).strip()

        if code_text and label_text:
            values.append(
                AllowedValue(
                    code=code_text,
                    label=label_text,
                )
            )

    return values


_LOADERS = {
    "paises": _load_paises,
    "cine_campo_detallado": _load_cine_campo_detallado,
}


def apply_master_table_reference(
    rule: ValidationRule,
    raw_comment: str,
) -> ValidationRule:
    """Carga el catálogo correspondiente según el comentario."""

    if rule.allowed_values:
        return rule

    for pattern, table_name in _TRIGGER_PATTERNS:
        if pattern.search(raw_comment or ""):
            loader = _LOADERS.get(table_name)

            if loader:
                values = loader()

                if values:
                    rule.allowed_values = values

            break

    return rule