
"""
Aplica el catálogo de known_fields.yaml como complemento
de las reglas interpretadas desde los comentarios de Excel.

Responsabilidades:
    - Localizar la definición de un campo conocido.
    - Completar el tipo de dato.
    - Completar restricciones de longitud.
    - Completar obligatoriedad.
    - Completar valores permitidos.
    - Completar descripciones.

Principio de funcionamiento:

    La información interpretada desde el comentario de Excel
    tiene prioridad.

    known_fields.yaml solamente completa atributos que no
    pudieron obtenerse del comentario.

La configuración puede recibirse en dos estructuras:

    1. Nueva arquitectura:

        sheets:
            NOMBRE_HOJA:
                NOMBRE_CAMPO:
                    datatype: integer

    2. Arquitectura anterior:

        NOMBRE_CAMPO:
            datatype: integer
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from backend.rules.general_model import (
    AllowedValue,
    DataType,
    ValidationRule,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

_CATALOG_PATH = (
    Path(__file__).resolve().parent
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

def _load_catalog() -> dict[str, Any]:
    """
    Carga el catálogo global anterior de campos conocidos.

    Se conserva exclusivamente para mantener compatibilidad
    con las plantillas que todavía no utilizan la nueva
    arquitectura de configuración.
    """

    if not _CATALOG_PATH.exists():
        return {}

    with _CATALOG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        catalog = yaml.safe_load(file)

    if catalog is None:
        return {}

    if not isinstance(catalog, dict):
        raise ValueError(
            f"El archivo '{_CATALOG_PATH}' debe contener "
            "un diccionario YAML."
        )

    return catalog


# Se carga una sola vez al importar el módulo.
_CATALOG = _load_catalog()


# ============================================================
# UTILIDADES DE VALIDACIÓN
# ============================================================

def _validate_field_entry(
    entry: Any,
    column_name: str,
) -> dict[str, Any]:
    """
    Comprueba que la definición de un campo sea un diccionario.

    Evita que configuraciones incorrectas produzcan errores
    difíciles de localizar durante la interpretación.
    """

    if not isinstance(entry, dict):
        raise ValueError(
            f"La definición del campo '{column_name}' "
            "en known_fields.yaml debe ser un diccionario."
        )

    return entry


def _validate_length(
    value: Any,
    attribute: str,
    column_name: str,
) -> int:
    """
    Valida una restricción de longitud.

    La longitud debe ser un entero no negativo.
    Se rechazan valores booleanos porque bool hereda de int
    en Python.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"El atributo '{attribute}' del campo "
            f"'{column_name}' debe ser un entero."
        )

    if value < 0:
        raise ValueError(
            f"El atributo '{attribute}' del campo "
            f"'{column_name}' no puede ser negativo."
        )

    return value


def _validate_required(
    value: Any,
    column_name: str,
) -> bool:
    """
    Comprueba que required sea un booleano real.
    """

    if not isinstance(value, bool):
        raise ValueError(
            f"El atributo 'required' del campo "
            f"'{column_name}' debe ser true o false."
        )

    return value


def _load_allowed_values(
    values: Any,
    column_name: str,
) -> list[AllowedValue]:
    """
    Convierte los valores permitidos del YAML en AllowedValue.

    Cada elemento debe contener:
        - code
        - label
    """

    if not isinstance(values, list):
        raise ValueError(
            f"'allowed_values' del campo '{column_name}' "
            "debe ser una lista."
        )

    allowed_values: list[AllowedValue] = []

    seen_codes: set[str] = set()

    for index, value in enumerate(values):

        if not isinstance(value, dict):
            raise ValueError(
                f"El elemento {index + 1} de 'allowed_values' "
                f"del campo '{column_name}' debe ser "
                "un diccionario."
            )

        if "code" not in value or "label" not in value:
            raise ValueError(
                f"Cada elemento de 'allowed_values' del campo "
                f"'{column_name}' debe contener 'code' y 'label'."
            )

        code = str(value["code"]).strip()
        label = str(value["label"]).strip()

        if not code:
            raise ValueError(
                f"Se encontró un código vacío en "
                f"'allowed_values' del campo '{column_name}'."
            )

        if code in seen_codes:
            raise ValueError(
                f"El código '{code}' está duplicado en "
                f"'allowed_values' del campo '{column_name}'."
            )

        seen_codes.add(code)

        allowed_values.append(
            AllowedValue(
                code=code,
                label=label,
            )
        )

    return allowed_values


# ============================================================
# LOCALIZACIÓN DE CAMPOS
# ============================================================

def _get_field_entry(
    catalog: dict[str, Any],
    column_name: str,
    sheet_name: str | None,
) -> dict[str, Any]:
    """
    Localiza la definición de un campo.

    Si la configuración utiliza la nueva arquitectura,
    busca primero dentro de la hoja correspondiente.

    Si utiliza la estructura anterior, busca directamente
    por nombre de columna.
    """

    if "sheets" in catalog:

        sheets = catalog.get(
            "sheets",
            {},
        )

        if not isinstance(sheets, dict):
            raise ValueError(
                "La sección 'sheets' de known_fields "
                "debe ser un diccionario."
            )

        if sheet_name is None:
            return {}

        sheet_rules = sheets.get(
            sheet_name,
            {},
        )

        if not isinstance(sheet_rules, dict):
            raise ValueError(
                f"La configuración de campos conocidos "
                f"para la hoja '{sheet_name}' debe ser "
                "un diccionario."
            )

        entry = sheet_rules.get(
            column_name,
            {},
        )

    else:

        # Compatibilidad con el formato global anterior.
        entry = catalog.get(
            column_name,
            {},
        )

    if not entry:
        return {}

    return _validate_field_entry(
        entry,
        column_name,
    )


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
    desde el comentario del encabezado de Excel.

    Parámetros:
        rule:
            Regla que ya fue interpretada.

        known_fields:
            Configuración de campos conocidos.
            Si es None, se utiliza el catálogo legacy.

        sheet_name:
            Nombre de la hoja para buscar la definición
            específica del campo.

    Retorna:
        La misma ValidationRule con los atributos faltantes
        complementados.

    IMPORTANTE:
    No sobrescribe información que ya fue interpretada
    desde el comentario de Excel.
    """

    catalog = (
        known_fields
        if known_fields is not None
        else _CATALOG
    )

    if not isinstance(catalog, dict):
        raise ValueError(
            "La configuración de known_fields debe "
            "ser un diccionario."
        )

    # --------------------------------------------------------
    # 1. LOCALIZAR LA DEFINICIÓN DEL CAMPO
    # --------------------------------------------------------

    entry = _get_field_entry(
        catalog,
        rule.column_name,
        sheet_name,
    )

    if not entry:
        return rule

    # --------------------------------------------------------
    # 2. COMPLETAR EL TIPO DE DATO
    # --------------------------------------------------------

    if (
        rule.datatype == DataType.UNKNOWN
        and "datatype" in entry
    ):

        datatype_name = str(
            entry["datatype"]
        ).strip().lower()

        if datatype_name not in _DATATYPE_MAP:
            raise ValueError(
                f"El tipo de dato '{datatype_name}' del campo "
                f"'{rule.column_name}' no está soportado."
            )

        rule.datatype = _DATATYPE_MAP[datatype_name]

    # --------------------------------------------------------
    # 3. COMPLETAR RESTRICCIONES DE LONGITUD
    # --------------------------------------------------------

    if (
        rule.max_length is None
        and "max_length" in entry
    ):

        rule.max_length = _validate_length(
            entry["max_length"],
            "max_length",
            rule.column_name,
        )

    if (
        rule.min_length is None
        and "min_length" in entry
    ):

        rule.min_length = _validate_length(
            entry["min_length"],
            "min_length",
            rule.column_name,
        )

    if (
        rule.exact_length is None
        and "exact_length" in entry
    ):

        rule.exact_length = _validate_length(
            entry["exact_length"],
            "exact_length",
            rule.column_name,
        )

    # Comprobar que las restricciones resultantes
    # no sean contradictorias.
    if (
        rule.min_length is not None
        and rule.max_length is not None
        and rule.min_length > rule.max_length
    ):

        raise ValueError(
            f"El campo '{rule.column_name}' tiene una "
            "longitud mínima superior a la máxima."
        )

    if (
        rule.exact_length is not None
        and rule.min_length is not None
        and rule.exact_length < rule.min_length
    ):

        raise ValueError(
            f"El campo '{rule.column_name}' tiene una "
            "longitud exacta inferior a la mínima."
        )

    if (
        rule.exact_length is not None
        and rule.max_length is not None
        and rule.exact_length > rule.max_length
    ):

        raise ValueError(
            f"El campo '{rule.column_name}' tiene una "
            "longitud exacta superior a la máxima."
        )

    # --------------------------------------------------------
    # 4. COMPLETAR OBLIGATORIEDAD
    # --------------------------------------------------------

    # Si el comentario menciona explícitamente obligatoriedad
    # u opcionalidad, esa información tiene prioridad.
    #
    # También se respeta una obligatoriedad condicional.
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

        rule.required = _validate_required(
            entry["required"],
            rule.column_name,
        )

    # --------------------------------------------------------
    # 5. COMPLETAR VALORES PERMITIDOS
    # --------------------------------------------------------

    if (
        not rule.allowed_values
        and "allowed_values" in entry
    ):

        rule.allowed_values = _load_allowed_values(
            entry["allowed_values"],
            rule.column_name,
        )

    # --------------------------------------------------------
    # 6. COMPLETAR DESCRIPCIÓN
    # --------------------------------------------------------

    if (
        not rule.description
        and "description" in entry
    ):

        description = entry["description"]

        if not isinstance(description, str):
            raise ValueError(
                f"La descripción del campo '{rule.column_name}' "
                "debe ser un texto."
            )

        rule.description = description.strip()

    # --------------------------------------------------------
    # 7. ACTUALIZAR ESTADO DE REVISIÓN MANUAL
    # --------------------------------------------------------

    # Si el campo ya tiene un tipo conocido o una lista de valores,
    # eliminamos la marca que indicaba que no se pudo interpretar
    # el comentario por estar vacío.
    #
    # No eliminamos otros fragmentos pendientes de interpretación.
    if (
        rule.datatype != DataType.UNKNOWN
        or rule.allowed_values
    ):

        rule.unparsed_fragments = [
            fragment
            for fragment in rule.unparsed_fragments
            if fragment != "(sin comentario)"
        ]

    return rule
