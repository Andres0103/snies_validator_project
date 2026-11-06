"""Detecta referencias a catálogos y carga sus valores."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from rules.models import AllowedValue, ValidationRule


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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


def _load_paises() -> list[AllowedValue]:
    """Carga el catálogo de países desde el CSV."""
    path = _DATA_DIR / "paises.csv"

    if not path.exists():
        return []

    values = [
        AllowedValue(
            code="0",
            label="No Aplica (Organismo Multilateral)",
        )
    ]

    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            if row.get("FECHA_FINAL", "").strip():
                continue

            code = row.get("ID_PAIS", "").strip()
            label = row.get("DESC_PAIS", "").strip()

            if code and label:
                values.append(
                    AllowedValue(
                        code=code,
                        label=label,
                    )
                )

    return values


def _load_cine_campo_detallado() -> list[AllowedValue]:
    """Carga la clasificación CINE desde el CSV."""
    path = _DATA_DIR / "cine_campo_detallado.csv"

    if not path.exists():
        return []

    values: list[AllowedValue] = []

    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            if row.get("FECHA_FINAL", "").strip():
                continue

            code = row.get("ID_CINE_CAMPO_DETALLADO", "").strip()
            label = row.get("DESC_CINE_CAMPO_DETALLADO", "").strip()

            if code and label:
                values.append(
                    AllowedValue(
                        code=code,
                        label=label,
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