
"""
Carga catálogos de referencia definidos en archivos YAML.

Responsabilidades:
    - Resolver archivos YAML de catálogos.
    - Ubicar los registros mediante records_path.
    - Convertir los registros en AllowedValue.
    - Filtrar registros según su fecha de vigencia.
    - Incorporar valores adicionales.
    - Detectar registros incompletos y códigos duplicados.
    - Evitar lecturas repetidas mediante caché.

La vigencia se determina mediante active_date_column,
que representa la fecha hasta la cual un registro es válido.

Un registro se considera vigente cuando:
    - No tiene fecha final.
    - Su fecha final es igual o posterior a la fecha de consulta.

La fecha de consulta es hoy, salvo que se proporcione
explícitamente otra fecha.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from rules.general_model import AllowedValue


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

DATE_FORMATS = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
)


# ============================================================
# LECTURA YAML
# ============================================================

def _read_yaml(path: Path) -> Any:
    """
    Lee un archivo YAML y devuelve su contenido.

    La validación de la estructura se realiza posteriormente,
    dependiendo de la configuración del catálogo.
    """

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"No se encontró el catálogo: {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ValueError(
            f"El archivo '{path.name}' contiene YAML inválido."
        ) from exc


# ============================================================
# RESOLUCIÓN DE REGISTROS
# ============================================================

def _resolve_records(
    catalog_data: Any,
    records_path: str | None,
) -> list[dict[str, Any]]:
    """
    Resuelve la lista de registros mediante una ruta de claves YAML.

    Ejemplos:

        records

        master_tables.paises.records
    """

    if isinstance(catalog_data, list):
        records = catalog_data

    elif isinstance(catalog_data, dict):

        if records_path:

            if not isinstance(records_path, str):
                raise ValueError(
                    "'records_path' debe ser un texto."
                )

            records = catalog_data

            for key in records_path.split("."):

                if not isinstance(records, dict):
                    raise ValueError(
                        f"No se puede resolver la ruta "
                        f"'{records_path}'."
                    )

                if key not in records:
                    raise ValueError(
                        f"No existe la clave '{key}' "
                        f"en la ruta '{records_path}'."
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
            "La ubicación configurada no contiene "
            "una lista de registros."
        )

    return records


# ============================================================
# CONVERSIÓN DE FECHAS
# ============================================================

def _parse_date(
    value: Any,
    catalog_name: str,
    record_index: int,
) -> date | None:
    """
    Convierte un valor en date.

    Acepta:
        - datetime
        - date
        - Texto en formatos DATE_FORMATS

    Retorna None cuando el valor está vacío.

    Si contiene una fecha inválida, genera un error.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValueError(
            f"Fecha inválida en el registro {record_index} "
            f"del catálogo '{catalog_name}'."
        )

    value = value.strip()

    if not value:
        return None

    for date_format in DATE_FORMATS:

        try:
            return datetime.strptime(
                value,
                date_format,
            ).date()

        except ValueError:
            continue

    raise ValueError(
        f"La fecha '{value}' del registro {record_index} "
        f"del catálogo '{catalog_name}' no tiene "
        "un formato reconocido."
    )


# ============================================================
# VIGENCIA DE REGISTROS
# ============================================================

def _is_active(
    record: dict[str, Any],
    active_date_column: str | None,
    as_of_date: date,
    catalog_name: str,
    record_index: int,
) -> bool:
    """
    Determina si un registro está vigente.

    Si no se configura active_date_column, todos los registros
    se consideran vigentes.

    Si la fecha final es None, el registro no tiene fecha
    de vencimiento.

    Si la fecha final es anterior a as_of_date, el registro
    se considera inactivo.
    """

    if not active_date_column:
        return True

    end_date = _parse_date(
        record.get(active_date_column),
        catalog_name,
        record_index,
    )

    if end_date is None:
        return True

    return end_date >= as_of_date


# ============================================================
# CARGA Y TRANSFORMACIÓN DE REGISTROS
# ============================================================

@lru_cache(maxsize=32)
def _load_catalog_cached(
    catalog_path: str,
    records_path: str | None,
    key_column: str,
    description_column: str,
    active_date_column: str | None,
    as_of_date: date,
) -> tuple[AllowedValue, ...]:
    """
    Carga y transforma los registros de un catálogo.

    La caché evita leer repetidamente el mismo archivo YAML
    con la misma configuración y fecha de consulta.

    La fecha de consulta forma parte de la clave de caché
    porque puede cambiar qué registros están vigentes.
    """

    path = Path(catalog_path)

    catalog_data = _read_yaml(path)

    records = _resolve_records(
        catalog_data,
        records_path,
    )

    values: list[AllowedValue] = []

    seen_codes: set[str] = set()

    for index, record in enumerate(records, start=1):

        if not isinstance(record, dict):
            raise ValueError(
                f"Registro {index} inválido en el catálogo "
                f"'{path.name}': debe ser un diccionario."
            )

        # Primero verificamos la vigencia.
        # Un registro inactivo no necesita incorporarse
        # a la lista de valores permitidos.
        if not _is_active(
            record=record,
            active_date_column=active_date_column,
            as_of_date=as_of_date,
            catalog_name=path.name,
            record_index=index,
        ):
            continue

        code = record.get(key_column)
        label = record.get(description_column)

        if code is None or label is None:
            raise ValueError(
                f"El registro {index} del catálogo "
                f"'{path.name}' no contiene "
                f"'{key_column}' o '{description_column}'."
            )

        code_text = str(code).strip()
        label_text = str(label).strip()

        if not code_text or not label_text:
            raise ValueError(
                f"El registro {index} del catálogo "
                f"'{path.name}' contiene código "
                "o descripción vacíos."
            )

        if code_text in seen_codes:
            raise ValueError(
                f"El código '{code_text}' está duplicado "
                f"en el catálogo '{path.name}'."
            )

        seen_codes.add(code_text)

        values.append(
            AllowedValue(
                code=code_text,
                label=label_text,
            )
        )

    if not values:
        raise ValueError(
            f"El catálogo '{path.name}' no contiene "
            "registros válidos y vigentes."
        )

    return tuple(values)


# ============================================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================================

def _validate_catalog_config(
    catalog_config: dict[str, Any],
    catalog_name: str,
) -> None:
    """
    Valida la configuración mínima necesaria para cargar
    un catálogo.
    """

    if not isinstance(catalog_config, dict):
        raise ValueError(
            f"La configuración del catálogo "
            f"'{catalog_name}' debe ser un diccionario."
        )

    required_keys = (
        "file",
        "key_column",
        "description_column",
    )

    for key in required_keys:

        value = catalog_config.get(key)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"La configuración del catálogo "
                f"'{catalog_name}' debe incluir "
                f"'{key}' como texto no vacío."
            )

    records_path = catalog_config.get("records_path")

    if records_path is not None and (
        not isinstance(records_path, str)
        or not records_path.strip()
    ):
        raise ValueError(
            f"'records_path' del catálogo "
            f"'{catalog_name}' debe ser un texto válido."
        )

    active_date_column = catalog_config.get(
        "active_date_column"
    )

    if active_date_column is not None and (
        not isinstance(active_date_column, str)
        or not active_date_column.strip()
    ):
        raise ValueError(
            f"'active_date_column' del catálogo "
            f"'{catalog_name}' debe ser un texto válido."
        )


# ============================================================
# VALORES ADICIONALES
# ============================================================

def _append_additional_values(
    values: list[AllowedValue],
    additional_values: Any,
    catalog_name: str,
) -> None:
    """
    Incorpora valores adicionales al catálogo.

    Los códigos adicionales no pueden duplicar códigos
    existentes ni otros valores adicionales.
    """

    if additional_values is None:
        return

    if not isinstance(additional_values, list):
        raise ValueError(
            f"'additional_values' debe ser una lista "
            f"en el catálogo '{catalog_name}'."
        )

    existing_codes = {
        value.code
        for value in values
    }

    for index, item in enumerate(additional_values, start=1):

        if not isinstance(item, dict):
            raise ValueError(
                f"El valor adicional {index} del catálogo "
                f"'{catalog_name}' debe ser un diccionario."
            )

        code = item.get("code")
        label = item.get("label")

        if code is None or label is None:
            raise ValueError(
                f"El valor adicional {index} de "
                f"'{catalog_name}' debe contener "
                "'code' y 'label'."
            )

        code = str(code).strip()
        label = str(label).strip()

        if not code or not label:
            raise ValueError(
                f"El valor adicional {index} de "
                f"'{catalog_name}' contiene campos vacíos."
            )

        if code in existing_codes:
            raise ValueError(
                f"El código adicional '{code}' está duplicado "
                f"en el catálogo '{catalog_name}'."
            )

        values.append(
            AllowedValue(
                code=code,
                label=label,
            )
        )

        existing_codes.add(code)


# ============================================================
# FUNCIÓN PÚBLICA
# ============================================================

def load_catalog(
    catalog_config: dict[str, Any],
    catalog_name: str,
    as_of_date: date | None = None,
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

    as_of_date:
        Fecha contra la cual se determina la vigencia.

        Si no se proporciona, se utiliza la fecha actual.

    Retorna:
        Lista de AllowedValue.
    """

    _validate_catalog_config(
        catalog_config,
        catalog_name,
    )

    relative_path = catalog_config["file"]
    records_path = catalog_config.get("records_path")
    key_column = catalog_config["key_column"]
    description_column = catalog_config["description_column"]
    active_date_column = catalog_config.get("active_date_column")

    if as_of_date is None:
        as_of_date = date.today()

    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()

    if not isinstance(as_of_date, date):
        raise ValueError(
            "'as_of_date' debe ser un objeto date."
        )

    # Resolver la ruta absoluta del catálogo.
    catalog_path = (
        PROJECT_DIR / relative_path
    ).resolve()

    # Evitar que la configuración permita leer archivos
    # ubicados fuera del directorio del proyecto.
    try:
        catalog_path.relative_to(
            PROJECT_DIR.resolve()
        )

    except ValueError as exc:
        raise ValueError(
            f"La ruta del catálogo '{catalog_name}' "
            "debe permanecer dentro del proyecto."
        ) from exc

    # Cargar los registros originales.
    cached_values = _load_catalog_cached(
        str(catalog_path),
        records_path,
        key_column,
        description_column,
        active_date_column,
        as_of_date,
    )

    # Convertir la tupla cacheada a lista para que el consumidor
    # pueda utilizarla sin modificar el contenido de la caché.
    values = list(cached_values)

    # Incorporar valores adicionales definidos en YAML.
    _append_additional_values(
        values=values,
        additional_values=catalog_config.get(
            "additional_values",
            [],
        ),
        catalog_name=catalog_name,
    )

    return values
