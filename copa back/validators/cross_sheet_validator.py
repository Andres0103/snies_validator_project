"""Validaciones referenciales entre hojas principales y complementarias."""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl.workbook.workbook import Workbook

from rules.general_model import DataType
from excel.reader import read_headers
from rules.template_profiles import load_template_profiles

HEADER_ROW = 1

DEFAULT_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
)


# ============================================================
# NORMALIZACIÓN DE VALORES
# ============================================================


def _normalize_text(value: Any) -> str | None:
    """
    Normaliza valores para comparaciones referenciales.

    Los valores numéricos enteros almacenados por Excel como
    float se representan sin la parte decimal .0.

    Los valores textuales conservan sus ceros iniciales,
    caracteres internos y signos originales.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return str(value).upper()

    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))

            if not number.is_finite():
                return None

            if number == number.to_integral_value():
                return str(int(number))

            return format(number.normalize(), "f")

        except (InvalidOperation, ValueError, TypeError):
            return None

    text = str(value).strip()

    if not text:
        return None

    return text.upper()


def _normalize_integer(value: Any) -> str | None:
    """
    Normaliza un valor entero.

    Acepta representaciones equivalentes como:
        2026
        2026.0
        "2026"
        "2026.0"

    No acepta valores fraccionarios.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        number = Decimal(str(value).strip())

    except (InvalidOperation, ValueError, TypeError):
        return None

    if not number.is_finite():
        return None

    if number != number.to_integral_value():
        return None

    return str(int(number))


def _normalize_decimal(value: Any) -> str | None:
    """
    Normaliza números decimales sin depender de float.

    Por ejemplo:
        10
        10.0
        "10.000"

    Se convierten a la misma representación normalizada.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        number = Decimal(str(value).strip())

    except (InvalidOperation, ValueError, TypeError):
        return None

    if not number.is_finite():
        return None

    normalized = number.normalize()

    if normalized == 0:
        normalized = Decimal(0)

    return format(normalized, "f")


def _normalize_date(value: Any) -> str | None:
    """
    Normaliza fechas a ISO 8601 (YYYY-MM-DD).

    Acepta fechas nativas de Excel y los formatos textuales
    generales utilizados por el motor.
    """

    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        return value.date().isoformat()

    if isinstance(value, datetime.date):
        return value.isoformat()

    if isinstance(value, str):

        text = value.strip()

        if not text:
            return None

        for date_format in DEFAULT_DATE_FORMATS:

            try:
                parsed_date = datetime.datetime.strptime(
                    text,
                    date_format,
                ).date()

                return parsed_date.isoformat()

            except ValueError:
                continue

        # Si no se reconoce como fecha, no se convierte
        # silenciosamente a otra representación.
        return text.upper()

    return None


def _normalize_key_value(
    value: Any,
    data_type: DataType = DataType.UNKNOWN,
) -> str | None:
    """
    Normaliza un componente de una clave referencial según su tipo.

    TEXT, ALPHANUMERIC y ALPHABETIC:
        Conservan los ceros iniciales.

    INTEGER:
        Normaliza representaciones numéricas enteras.

    DECIMAL:
        Normaliza representaciones decimales.

    DATE:
        Normaliza fechas a YYYY-MM-DD.

    UNKNOWN:
        Conserva el valor como texto para no perder información.
    """

    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    if data_type == DataType.INTEGER:
        return _normalize_integer(value)

    if data_type == DataType.DECIMAL:
        return _normalize_decimal(value)

    if data_type == DataType.DATE:
        return _normalize_date(value)

    if data_type in (
        DataType.TEXT,
        DataType.ALPHANUMERIC,
        DataType.ALPHABETIC,
    ):
        return _normalize_text(value)

    return _normalize_text(value)


# ============================================================
# LECTURA DE HOJAS
# ============================================================


def _read_rows(
    ws: Any,
) -> tuple[list[str], list[tuple[int, dict[str, Any]]]]:
    """
    Obtiene los encabezados y las filas de una hoja.

    Retorna:
        - Lista de nombres de columnas.
        - Lista de tuplas (número de fila, valores de la fila).

    Las filas completamente vacías se omiten.
    """

    headers = read_headers(ws)

    names = [header.column_name for header in headers]

    rows: list[tuple[int, dict[str, Any]]] = []

    for row_number in range(
        HEADER_ROW + 1,
        ws.max_row + 1,
    ):

        values = {
            header.column_name: ws.cell(
                row_number,
                header.cell.column,
            ).value
            for header in headers
        }

        if any(
            value is not None and not (isinstance(value, str) and not value.strip())
            for value in values.values()
        ):
            rows.append((row_number, values))

    return names, rows


# ============================================================
# CONFIGURACIÓN DE TIPOS
# ============================================================


def _get_column_type(
    column_types_by_sheet: dict[str, dict[str, DataType]],
    sheet_name: str,
    column_name: str,
) -> DataType:
    """
    Obtiene el tipo de dato de una columna.

    La búsqueda de la hoja ignora mayúsculas y espacios exteriores.
    Si no existe información del tipo, utiliza UNKNOWN.
    """

    normalized_sheet = sheet_name.strip().casefold()

    for configured_sheet, column_types in column_types_by_sheet.items():

        if configured_sheet.strip().casefold() == normalized_sheet:

            if not isinstance(column_types, dict):
                return DataType.UNKNOWN

            data_type = column_types.get(
                column_name,
                DataType.UNKNOWN,
            )

            if isinstance(data_type, DataType):
                return data_type

            # Compatibilidad si algún consumidor proporciona
            # el valor textual del enum.
            try:
                return DataType(data_type)

            except (ValueError, TypeError):
                return DataType.UNKNOWN

    return DataType.UNKNOWN


def _build_row_key(
    row: dict[str, Any],
    key_columns: list[str],
    column_types: dict[str, DataType],
) -> tuple[str, ...] | None:
    """
    Construye una clave normalizada.

    Retorna None cuando alguno de sus componentes está vacío
    o no puede normalizarse.
    """

    normalized_values = []

    for column in key_columns:

        data_type = column_types.get(
            column,
            DataType.UNKNOWN,
        )

        normalized_value = _normalize_key_value(
            row.get(column),
            data_type,
        )

        if normalized_value is None:
            return None

        normalized_values.append(normalized_value)

    return tuple(normalized_values)


# ============================================================
# VALIDACIÓN REFERENCIAL
# ============================================================


def validate_sheet_references(
    workbook: Workbook,
    template_name: str,
    column_types_by_sheet: (
        dict[
            str,
            dict[str, DataType],
        ]
        | None
    ) = None,
) -> list[dict[str, Any]]:
    """
    Comprueba relaciones entre hojas principales y complementarias.

    No exige que el libro contenga todas las hojas de una plantilla.

    Si falta la hoja principal o complementaria de una relación,
    esta relación se omite.

    Si ambas hojas existen, comprueba que las claves completas
    de la hoja hija estén presentes en la hoja principal.

    Los valores se normalizan según el DataType de cada columna.
    """

    if not isinstance(template_name, str) or not template_name.strip():
        raise ValueError(
            "Debe especificarse una plantilla para "
            "validar las relaciones entre hojas."
        )

    template_name = template_name.strip().upper()

    profiles = load_template_profiles().get(
        "templates",
        {},
    )

    if template_name not in profiles:
        raise ValueError(
            f"No existe un perfil estructural para " f"la plantilla '{template_name}'."
        )

    issues: list[dict[str, Any]] = []

    column_types_by_sheet = column_types_by_sheet or {}

    # --------------------------------------------------------
    # 1. INDEXAR LAS HOJAS DEL LIBRO
    # --------------------------------------------------------

    workbook_sheets_by_normalized = {
        sheet_name.strip().casefold(): sheet_name for sheet_name in workbook.sheetnames
    }

    # --------------------------------------------------------
    # 2. RECORRER LOS PERFILES
    # --------------------------------------------------------

    profile = profiles[template_name]

    current_template = template_name

    references = profile.get(
        "references",
        [],
    )

    if not isinstance(references, list):
        raise ValueError(
            f"Las referencias de '{current_template}' "
            "deben estar definidas como una lista."
        )

    for relation in references:

        if not isinstance(relation, dict):
            raise ValueError(
                f"Existe una relación mal configurada "
                f"en el perfil '{current_template}'."
            )

        child_name = relation.get("child_sheet")
        parent_name = relation.get("parent_sheet")
        key_columns = relation.get("key")

        # ------------------------------------------------
        # 2.1. VALIDAR CONFIGURACIÓN DE LA RELACIÓN
        # ------------------------------------------------

        if not isinstance(child_name, str) or not child_name.strip():
            raise ValueError(
                f"Una relación de '{current_template}' "
                "no tiene un child_sheet válido."
            )

        if not isinstance(parent_name, str) or not parent_name.strip():
            raise ValueError(
                f"Una relación de '{current_template}' "
                "no tiene un parent_sheet válido."
            )

        if (
            not isinstance(key_columns, list)
            or not key_columns
            or any(
                not isinstance(column, str) or not column.strip()
                for column in key_columns
            )
        ):
            raise ValueError(
                f"La relación '{child_name} -> {parent_name}' "
                "debe tener una lista no vacía de columnas "
                "en 'key'."
            )

        if len(set(key_columns)) != len(key_columns):
            raise ValueError(
                f"La relación '{child_name} -> {parent_name}' "
                "contiene columnas clave duplicadas."
            )

        # ------------------------------------------------
        # 2.2. LOCALIZAR LAS HOJAS
        # ------------------------------------------------

        normalized_child = child_name.strip().casefold()
        normalized_parent = parent_name.strip().casefold()

        actual_child_name = workbook_sheets_by_normalized.get(normalized_child)

        actual_parent_name = workbook_sheets_by_normalized.get(normalized_parent)

        # La ausencia de una hoja no genera error por sí sola.
        # Esto mantiene la compatibilidad con libros parciales.
        if actual_child_name is None or actual_parent_name is None:
            continue

        child_ws = workbook[actual_child_name]
        parent_ws = workbook[actual_parent_name]

        # ------------------------------------------------
        # 2.3. LEER ENCABEZADOS Y FILAS
        # ------------------------------------------------

        parent_headers, parent_rows = _read_rows(parent_ws)
        child_headers, child_rows = _read_rows(child_ws)

        missing_parent_columns = [
            column for column in key_columns if column not in parent_headers
        ]

        missing_child_columns = [
            column for column in key_columns if column not in child_headers
        ]

        # ------------------------------------------------
        # 2.4. VALIDAR COLUMNAS NECESARIAS
        # ------------------------------------------------

        if missing_parent_columns or missing_child_columns:

            missing_columns = missing_child_columns or missing_parent_columns

            issues.append(
                {
                    "sheet": actual_child_name,
                    "row": HEADER_ROW,
                    "column_name": ", ".join(missing_columns),
                    "value": None,
                    "message": (
                        f"No se puede comprobar la relación "
                        f"{actual_child_name} -> "
                        f"{actual_parent_name}. "
                        f"Columnas faltantes en padre: "
                        f"{missing_parent_columns}; "
                        f"en hija: {missing_child_columns}."
                    ),
                    "severity": "error",
                }
            )

            continue

        # ------------------------------------------------
        # 2.5. OBTENER LOS TIPOS DE LAS COLUMNAS CLAVE
        # ------------------------------------------------

        parent_column_types = {
            column: _get_column_type(
                column_types_by_sheet,
                actual_parent_name,
                column,
            )
            for column in key_columns
        }

        child_column_types = {
            column: _get_column_type(
                column_types_by_sheet,
                actual_child_name,
                column,
            )
            for column in key_columns
        }

        # Una relación debe comparar cada componente con
        # una semántica compatible en ambas hojas.
        #
        # Si los tipos difieren, se usa UNKNOWN para ese
        # componente y se conserva su representación textual.
        compatible_column_types: dict[str, DataType] = {}

        for column in key_columns:

            parent_type = parent_column_types[column]
            child_type = child_column_types[column]

            if parent_type == child_type:
                compatible_column_types[column] = parent_type

            else:
                compatible_column_types[column] = DataType.UNKNOWN

        # ------------------------------------------------
        # 2.6. CONSTRUIR LAS CLAVES DEL PADRE
        # ------------------------------------------------

        parent_keys: set[tuple[str, ...]] = set()

        for _, parent_row in parent_rows:

            parent_key = _build_row_key(
                parent_row,
                key_columns,
                compatible_column_types,
            )

            if parent_key is not None:
                parent_keys.add(parent_key)

        # ------------------------------------------------
        # 2.7. VALIDAR LAS REFERENCIAS DE LAS FILAS HIJAS
        # ------------------------------------------------

        for row_number, child_row in child_rows:

            child_key = _build_row_key(
                child_row,
                key_columns,
                compatible_column_types,
            )

            # Las claves incompletas corresponden a las
            # validaciones de obligatoriedad de las columnas.
            if child_key is None:
                continue

            if child_key not in parent_keys:

                readable_key = " | ".join(
                    f"{column}={child_row.get(column)}" for column in key_columns
                )

                issues.append(
                    {
                        "sheet": actual_child_name,
                        "row": row_number,
                        "column_name": key_columns[-1],
                        "value": child_row.get(key_columns[-1]),
                        "message": (
                            f"El registro de "
                            f"'{actual_child_name}' no tiene "
                            f"un registro principal correspondiente "
                            f"en '{actual_parent_name}'. "
                            f"Clave: {readable_key}."
                        ),
                        "severity": "error",
                    }
                )

    return issues
