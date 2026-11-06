"""Carga `rules/patterns/business_rules.yaml` (reglas del manual MEN que no
vienen en los comentarios de Excel)."""

from __future__ import annotations

from pathlib import Path

import yaml

_CATALOG_PATH = Path(__file__).parent / "patterns" / "business_rules.yaml"


def load_business_rules() -> dict:
    if not _CATALOG_PATH.exists():
        return {}
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
