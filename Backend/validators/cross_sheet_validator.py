
"""Validaciones referenciales entre hojas principales y complementarias."""

from __future__ import annotations

from typing import Any

from openpyxl.workbook.workbook import Workbook

from excel.reader import read_headers
from rules.template_profiles import load_template_profiles


def _normalize_key_value(value: Any) -> str | None:
    """Normaliza valores para comparar claves provenientes de Excel."""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # Evitar diferencias entre valores como 2026 y 2026.0.
    try:
        number = float(text)

        if number.is_integer():
            return str(int(number))

    except ValueError:
        pass

    return text.upper()


def _read_rows(ws):
    """Obtiene los encabezados y las filas de una hoja."""

    headers = read_headers(ws)

    names = [
        header.column_name
        for header in headers
    ]

    rows = []

    for row_number in range(2, ws.max_row + 1):

        values = {
            name: ws.cell(
                row_number,
                header.cell.column
            ).value
            for name, header in zip(names, headers)
        }

        if any(
            _normalize_key_value(value) is not None
            for value in values.values()
        ):
            rows.append((row_number, values))

    return names, rows


def validate_sheet_references(
    workbook: Workbook,
    template_name: str | None = None,
) -> list[dict]:
    """
    Comprueba relaciones entre hojas cuando ambas están disponibles.

    No exige que el libro contenga todas las hojas de una plantilla.

    Si template_name se proporciona, limita la validación a esa plantilla.
    Si no se proporciona, evalúa todas las relaciones configuradas.
    """

    profiles = load_template_profiles().get("templates", {})

    issues = []

    # Recorrer las relaciones configuradas.
    for current_template, profile in profiles.items():

        # Mantener compatibilidad con llamadas que especifican plantilla.
        if (
            template_name is not None
            and current_template != template_name
        ):
            continue

        for relation in profile.get("references", []):

            child_name = relation["child_sheet"]
            parent_name = relation["parent_sheet"]
            key_columns = relation["key"]

            # Si falta cualquiera de las hojas, no se ejecuta
            # esta relación. Su ausencia no genera un error.
            if (
                child_name not in workbook.sheetnames
                or parent_name not in workbook.sheetnames
            ):
                continue

            parent_ws = workbook[parent_name]
            child_ws = workbook[child_name]

            parent_headers, parent_rows = _read_rows(parent_ws)
            child_headers, child_rows = _read_rows(child_ws)

            missing_parent_columns = [
                column
                for column in key_columns
                if column not in parent_headers
            ]

            missing_child_columns = [
                column
                for column in key_columns
                if column not in child_headers
            ]

            # Si faltan columnas necesarias para comparar,
            # se informa que no fue posible ejecutar la relación.
            if missing_parent_columns or missing_child_columns:

                issues.append({
                    "sheet": child_name,
                    "row": 1,
                    "column_name": ", ".join(
                        missing_child_columns
                        or missing_parent_columns
                    ),
                    "value": None,
                    "message": (
                        f"No se puede comprobar la relación "
                        f"{child_name} -> {parent_name}. "
                        f"Columnas faltantes en padre: "
                        f"{missing_parent_columns}; "
                        f"en hija: {missing_child_columns}."
                    ),
                    "severity": "error",
                })

                continue

            # Construir las claves existentes en la hoja principal.
            parent_keys = set()

            for _, parent_row in parent_rows:

                values = [
                    _normalize_key_value(
                        parent_row.get(column)
                    )
                    for column in key_columns
                ]

                if all(value is not None for value in values):
                    parent_keys.add(tuple(values))

            # Comprobar las referencias de cada fila hija.
            for row_number, child_row in child_rows:

                values = [
                    _normalize_key_value(
                        child_row.get(column)
                    )
                    for column in key_columns
                ]

                # Las claves incompletas corresponden a las
                # validaciones de obligatoriedad de las columnas.
                if not all(value is not None for value in values):
                    continue

                key = tuple(values)

                if key not in parent_keys:

                    readable_key = " | ".join(
                        f"{column}={child_row.get(column)}"
                        for column in key_columns
                    )

                    issues.append({
                        "sheet": child_name,
                        "row": row_number,
                        "column_name": key_columns[-1],
                        "value": child_row.get(key_columns[-1]),
                        "message": (
                            f"El registro de '{child_name}' no tiene "
                            f"un registro principal correspondiente "
                            f"en '{parent_name}'. "
                            f"Clave: {readable_key}."
                        ),
                        "severity": "error",
                    })

    return issues
