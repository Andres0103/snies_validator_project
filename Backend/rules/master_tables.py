
"""
Detecta referencias a catálogos maestros en los comentarios
de los encabezados de Excel y carga sus valores desde YAML.

Este módulo mantiene la compatibilidad con las referencias
que aparecen directamente en los comentarios MEN.

Para catálogos declarados en configuraciones YAML se utiliza
catalog_loader.py. No se debe confundir ambos mecanismos.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml

from rules.general_model import AllowedValue, ValidationRule


# ============================================================
# RUTAS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CATALOGS_DIR = PROJECT_ROOT / "catalogs"


# ============================================================
# REFERENCIAS RECONOCIDAS
# ============================================================

# Cada patrón relaciona una expresión del comentario con
# el identificador del catálogo que debe cargarse.
#
# El orden importa: se evalúan de arriba hacia abajo.

_TRIGGER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"lista de pa[ií]ses|iso\s*3166",
            re.IGNORECASE,
        ),
        "paises",
    ),
    (
        re.compile(
            r"clasificaci[oó]n\s+cine",
            re.IGNORECASE,
        ),
        "cine_campo_detallado",
    ),
]


# ============================================================
# LECTURA DE ARCHIVOS YAML
# ============================================================

def _read_yaml(path: Path) -> dict:
    """
    Lee un archivo YAML y comprueba que su contenido
    sea un diccionario.

    Si el archivo no existe o está mal formado, se genera
    un error explícito para evitar cargar catálogos vacíos
    sin advertencia.
    """

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"No se encontró el catálogo maestro: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        catalog_data = yaml.safe_load(file)

    if not isinstance(catalog_data, dict):
        raise ValueError(
            f"El catálogo '{path.name}' debe contener "
            "un diccionario YAML."
        )

    return catalog_data


# ============================================================
# CONSTRUCCIÓN DE VALORES PERMITIDOS
# ============================================================

def _build_allowed_values(
    records: list[dict],
    code_column: str,
    label_column: str,
    catalog_name: str,
    additional_values: list[AllowedValue] | None = None,
) -> list[AllowedValue]:
    """
    Convierte registros YAML en objetos AllowedValue.

    Responsabilidades:
        - Validar la estructura de los registros.
        - Obtener código y descripción.
        - Rechazar códigos o descripciones vacíos.
        - Detectar códigos duplicados.
        - Incorporar valores adicionales sin duplicarlos.
    """

    values: list[AllowedValue] = []

    seen_codes: set[str] = set()

    # Primero incorporamos los valores adicionales.
    # Se utilizan, por ejemplo, para excepciones del catálogo.
    for value in additional_values or []:

        code = str(value.code).strip()
        label = str(value.label).strip()

        if not code or not label:
            raise ValueError(
                f"Valor adicional inválido en el catálogo "
                f"'{catalog_name}'."
            )

        if code in seen_codes:
            raise ValueError(
                f"El código '{code}' está duplicado en "
                f"el catálogo '{catalog_name}'."
            )

        seen_codes.add(code)
        values.append(
            AllowedValue(
                code=code,
                label=label,
            )
        )

    # Procesamos los registros originales.
    for index, record in enumerate(records):

        if not isinstance(record, dict):
            raise ValueError(
                f"Registro {index + 1} inválido en "
                f"el catálogo '{catalog_name}'."
            )

        code = record.get(code_column)
        label = record.get(label_column)

        if code is None or label is None:
            raise ValueError(
                f"El registro {index + 1} del catálogo "
                f"'{catalog_name}' no contiene "
                f"'{code_column}' o '{label_column}'."
            )

        code_text = str(code).strip()
        label_text = str(label).strip()

        if not code_text or not label_text:
            raise ValueError(
                f"El registro {index + 1} del catálogo "
                f"'{catalog_name}' contiene código "
                "o descripción vacíos."
            )

        if code_text in seen_codes:
            raise ValueError(
                f"El código '{code_text}' está duplicado "
                f"en el catálogo '{catalog_name}'."
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
            f"El catálogo '{catalog_name}' no contiene "
            "valores permitidos."
        )

    return values


# ============================================================
# CATÁLOGO DE PAÍSES
# ============================================================

def _load_paises() -> list[AllowedValue]:
    """
    Carga los países desde Tabla_paises_SNIES.yaml.

    El archivo contiene la estructura:

        master_tables:
            paises:
                records:
                    - ID_PAIS: ...
                      DESC_PAIS: ...

    Se conserva el valor especial 0 que ya utilizaba
    el proyecto para representar organismos multilaterales.
    """

    path = CATALOGS_DIR / "Tabla_paises_SNIES.yaml"

    catalog_data = _read_yaml(path)

    master_tables = catalog_data.get("master_tables")

    if not isinstance(master_tables, dict):
        raise ValueError(
            f"El catálogo '{path.name}' no contiene "
            "la sección 'master_tables'."
        )

    paises = master_tables.get("paises")

    if not isinstance(paises, dict):
        raise ValueError(
            f"El catálogo '{path.name}' no contiene "
            "la tabla 'paises'."
        )

    records = paises.get("records")

    if not isinstance(records, list):
        raise ValueError(
            f"La tabla 'paises' de '{path.name}' "
            "no contiene una lista de registros."
        )


    return _build_allowed_values(
    records=records,
    code_column="ID_PAIS",
    label_column="DESC_PAIS",
    catalog_name="paises",
)

# ============================================================
# CATÁLOGO CINE CAMPO DETALLADO
# ============================================================

def _load_cine_campo_detallado() -> list[AllowedValue]:
    """
    Carga la clasificación CINE Campo Detallado.

    El archivo contiene la estructura:

        records:
            - codigo: ...
              descripcion: ...
    """

    path = CATALOGS_DIR / "cine_campo_detallado.yaml"

    catalog_data = _read_yaml(path)

    records = catalog_data.get("records")

    if not isinstance(records, list):
        raise ValueError(
            f"El catálogo '{path.name}' no contiene "
            "una lista de registros."
        )

    return _build_allowed_values(
        records=records,
        code_column="codigo",
        label_column="descripcion",
        catalog_name="cine_campo_detallado",
    )


# ============================================================
# REGISTRO DE CARGADORES
# ============================================================

# Relaciona el identificador interno del catálogo con
# la función encargada de cargarlo.
#
# Para incorporar un nuevo catálogo reconocido desde
# comentarios, se agrega su cargador aquí y su patrón
# correspondiente en _TRIGGER_PATTERNS.

_LOADERS: dict[str, Callable[[], list[AllowedValue]]] = {
    "paises": _load_paises,
    "cine_campo_detallado": _load_cine_campo_detallado,
}


# ============================================================
# APLICACIÓN DE REFERENCIAS
# ============================================================

def apply_master_table_reference(
    rule: ValidationRule,
    raw_comment: str,
) -> ValidationRule:
    """
    Detecta referencias a catálogos maestros en el comentario
    y carga los valores permitidos correspondientes.

    Reglas:

        1. Si la regla ya tiene valores permitidos,
           no se sobrescriben.

        2. Si el comentario no menciona un catálogo reconocido,
           la regla permanece sin cambios.

        3. Si se identifica un catálogo, se carga su contenido.

        4. Si el catálogo no puede cargarse, se propaga el error.
           No se oculta un problema de configuración.
    """

    # Una lista interpretada directamente desde el comentario
    # tiene prioridad sobre las referencias automáticas.
    if rule.allowed_values:
        return rule

    comment = raw_comment or ""

    for pattern, table_name in _TRIGGER_PATTERNS:

        if not pattern.search(comment):
            continue

        loader = _LOADERS.get(table_name)

        if loader is None:
            raise ValueError(
                f"No existe un cargador para el catálogo "
                f"'{table_name}'."
            )

        # Si el catálogo fue identificado, su carga es obligatoria.
        # Cualquier problema debe llegar al nivel superior.
        rule.allowed_values = loader()

        break

    return rule
