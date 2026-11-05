"""Carga catálogos de referencia definidos en archivos YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rules.models import AllowedValue


PROJECT_DIR = Path(__file__).resolve().parent.parent


def _read_yaml(path: Path) -> Any:
    """Lee y devuelve el contenido de un archivo YAML."""
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_catalog(
    catalog_config: dict[str, str],
    catalog_name: str,
) -> list[AllowedValue]:
    """
    Carga un catálogo YAML según su configuración.

    catalog_config debe contener:
      - file
      - key_column
      - description_column
    """
    relative_path = catalog_config.get("file")
    key_column = catalog_config.get("key_column")
    description_column = catalog_config.get("description_column")

    if not relative_path or not key_column or not description_column:
        raise ValueError(
            f"La configuración del catálogo '{catalog_name}' "
            "debe incluir file, key_column y description_column."
        )

    catalog_path = PROJECT_DIR / relative_path

    if not catalog_path.exists():
        raise FileNotFoundError(
            f"No se encontró el catálogo '{catalog_name}': {catalog_path}"
        )

    catalog_data = _read_yaml(catalog_path)

    # Acepta registros en una sección "records", "values" o una lista raíz.
    if isinstance(catalog_data, dict):
        records = catalog_data.get(
            "records",
            catalog_data.get("values", catalog_data.get("data")),
        )
    elif isinstance(catalog_data, list):
        records = catalog_data
    else:
        records = None

    if not isinstance(records, list) or not records:
        raise ValueError(
            f"El catálogo '{catalog_name}' no contiene una lista de registros."
        )

    values: list[AllowedValue] = []

    for record in records:
        if not isinstance(record, dict):
            raise ValueError(
                f"El catálogo '{catalog_name}' contiene un registro inválido."
            )

        code = record.get(key_column)
        label = record.get(description_column)

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

    if not values:
        raise ValueError(
            f"El catálogo '{catalog_name}' no tiene códigos válidos."
        )

    return values