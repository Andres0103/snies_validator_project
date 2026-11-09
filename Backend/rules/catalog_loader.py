
"""Carga catálogos de referencia definidos en archivos YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.rules.general_model import AllowedValue


PROJECT_DIR = Path(__file__).resolve().parent.parent


def _read_yaml(path: Path) -> Any:
    """Lee un archivo YAML."""

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _resolve_records(
    catalog_data: Any,
    records_path: str | None,
) -> list[dict[str, Any]]:
    """
    Resuelve la lista de registros usando una ruta de claves YAML.

    Ejemplos:
        records
        master_tables.paises.records
    """

    if isinstance(catalog_data, list):
        records = catalog_data

    elif isinstance(catalog_data, dict):
        if records_path:
            records = catalog_data

            for key in records_path.split("."):
                if not isinstance(records, dict):
                    raise ValueError(
                        f"No se puede resolver la ruta '{records_path}'."
                    )

                if key not in records:
                    raise ValueError(
                        f"No existe la clave '{key}' en "
                        f"la ruta '{records_path}'."
                    )

                records = records[key]

        else:
            records = catalog_data.get(
                "records",
                catalog_data.get(
                    "values",
                    catalog_data.get("data"),
                ),
            )

    else:
        records = None

    if not isinstance(records, list):
        raise ValueError(
            "La ubicación configurada no contiene una lista de registros."
        )

    return records


@lru_cache(maxsize=32)
def _load_catalog_cached(
    catalog_path: str,
    records_path: str | None,
    key_column: str,
    description_column: str,
    active_date_column: str | None,
) -> tuple[AllowedValue, ...]:
    """
    Carga y transforma un catálogo.

    La caché evita leer repetidamente el mismo archivo YAML.
    """

    path = Path(catalog_path)

    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el catálogo: {path}"
        )

    catalog_data = _read_yaml(path)

    records = _resolve_records(
        catalog_data,
        records_path,
    )

    values: list[AllowedValue] = []

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"Registro inválido en el catálogo '{path.name}', "
                f"posición {index}."
            )


        code = record.get(key_column)
        label = record.get(description_column)

        if code is None or label is None:
            continue

        code_text = str(code).strip()
        label_text = str(label).strip()

        if not code_text or not label_text:
            continue

        values.append(
            AllowedValue(
                code=code_text,
                label=label_text,
            )
        )

    if not values:
        raise ValueError(
            f"El catálogo '{path.name}' no contiene códigos válidos "
            "con la configuración indicada."
        )

    return tuple(values)


def load_catalog(
    catalog_config: dict[str, Any],
    catalog_name: str,
) -> list[AllowedValue]:
    """
    Carga un catálogo según su configuración YAML.

    Parámetros esperados:
        file
        records_path
        key_column
        description_column
        active_date_column (opcional)
        additional_values (opcional)
    """

    relative_path = catalog_config.get("file")
    records_path = catalog_config.get("records_path")
    key_column = catalog_config.get("key_column")
    description_column = catalog_config.get("description_column")
    active_date_column = catalog_config.get("active_date_column")

    if not all((relative_path, key_column, description_column)):
        raise ValueError(
            f"La configuración del catálogo '{catalog_name}' "
            "debe incluir file, key_column y description_column."
        )

    catalog_path = (PROJECT_DIR / relative_path).resolve()

    try:
        catalog_path.relative_to(PROJECT_DIR.resolve())
    except ValueError as exc:
        raise ValueError(
            f"La ruta del catálogo '{catalog_name}' "
            "debe permanecer dentro del proyecto."
        ) from exc

    # Cargar los registros originales.
    values = list(
        _load_catalog_cached(
            str(catalog_path),
            records_path,
            key_column,
            description_column,
            active_date_column
        )
    )

    # Incorporar valores adicionales definidos en el YAML.
    additional_values = catalog_config.get("additional_values", [])

    if not isinstance(additional_values, list):
        raise ValueError(
            f"'additional_values' debe ser una lista en "
            f"el catálogo '{catalog_name}'."
        )

    existing_codes = {value.code for value in values}

    for item in additional_values:
        if not isinstance(item, dict):
            raise ValueError(
                f"Valor adicional inválido en el catálogo '{catalog_name}'."
            )

        code = item.get("code")
        label = item.get("label")

        if code is None or label is None:
            raise ValueError(
                f"Cada valor adicional de '{catalog_name}' "
                "debe tener code y label."
            )

        code = str(code).strip()
        label = str(label).strip()

        if not code or not label:
            continue

        if code not in existing_codes:
            values.append(
                AllowedValue(
                    code=code,
                    label=label,
                )
            )
            existing_codes.add(code)

    return values
