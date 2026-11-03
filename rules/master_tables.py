"""Campos cuyo comentario remite a una tabla externa en vez de traer la
lista inline (ej. "Consultar lista de países según ISO 3166-1").

Estos casos NO deben caer en el reconocedor de listas inline (que
buscaría código+etiqueta línea por línea dentro del propio comentario):
no hay tal lista en el comentario, hay una referencia a una tabla que
vive en otro archivo. Este módulo detecta esa referencia por patrones de
texto y, si el sistema tiene la tabla real disponible (`data/*.csv`),
la carga como `allowed_values` — igual que si hubiera venido inline.

Diseñado para ser extensible: agregar una tabla maestra nueva = agregar
una entrada a `_TRIGGER_PATTERNS` + un loader en `_LOADERS`, sin tocar el
resto del motor de reglas.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from rules.models import AllowedValue, ValidationRule

_DATA_DIR = Path(__file__).parent.parent / "data"

# Frases que indican "esto remite a una tabla externa", junto con el
# nombre de la tabla maestra que le corresponde.
_TRIGGER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"lista de pa[ií]ses|iso\s*3166", re.IGNORECASE), "paises"),
    (re.compile(r"clasificaci[oó]n\s+cine", re.IGNORECASE), "cine_campo_detallado"),
]


def _load_paises() -> list[AllowedValue]:
    path = _DATA_DIR / "paises.csv"
    if not path.exists():
        return []
    # Convención documentada en varias plantillas del MEN: cuando la
    # fuente de financiación es "Organismo Multilateral", se registra '0'
    # en el campo de país (no aplica un país específico). No es un país
    # real de la tabla ISO, así que se agrega como valor válido adicional.
    values = [AllowedValue(code="0", label="No Aplica (Organismo Multilateral)")]
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            # Excluir países con fecha de baja (ya no vigentes), si el
            # dato está disponible.
            if row.get("FECHA_FINAL", "").strip():
                continue
            code = row.get("ID_PAIS", "").strip()
            label = row.get("DESC_PAIS", "").strip()
            if code and label:
                values.append(AllowedValue(code=code, label=label))
    return values


def _load_cine_campo_detallado() -> list[AllowedValue]:
    path = _DATA_DIR / "cine_campo_detallado.csv"
    if not path.exists():
        return []
    values = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row.get("FECHA_FINAL", "").strip():
                continue  # código dado de baja
            code = row.get("ID_CINE_CAMPO_DETALLADO", "").strip()
            label = row.get("DESC_CINE_CAMPO_DETALLADO", "").strip()
            if code and label:
                values.append(AllowedValue(code=code, label=label))
    return values


_LOADERS = {"paises": _load_paises, "cine_campo_detallado": _load_cine_campo_detallado}


def apply_master_table_reference(rule: ValidationRule, raw_comment: str) -> ValidationRule:
    """Si el comentario remite a una tabla externa conocida, la carga como allowed_values."""
    if rule.allowed_values:
        return rule  # ya tiene lista propia (inline); no se pisa

    for pattern, table_name in _TRIGGER_PATTERNS:
        if pattern.search(raw_comment or ""):
            loader = _LOADERS.get(table_name)
            if loader:
                values = loader()
                if values:
                    rule.allowed_values = values
            break

    return rule
