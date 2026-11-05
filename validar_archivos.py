"""CLI del validador post-hoc para archivos SNIES diligenciados.

Uso:
    python validar_archivos.py <carpeta_entrada> <carpeta_salida>

Por cada archivo Excel de entrada:
    1. Valida los datos.
    2. Crea una copia del archivo original.
    3. Resalta las celdas con errores y advertencias.
    4. Agrega comentarios con el detalle de cada hallazgo.
    5. Guarda una versión consecutiva sin sobrescribir reportes anteriores.

También genera un reporte resumen general como archivo complementario.
"""

from __future__ import annotations

import logging
import re
import sys
from copy import copy
from pathlib import Path

import openpyxl
from openpyxl import cell
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill

from reporting.post_hoc_report import build_post_hoc_report
from validators.post_hoc_validator import validate_workbook

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("snies_post_hoc")

# Evita procesar reportes generados por el propio validador.
SKIP_PREFIXES = ("reporte_", "validation_report", "_")

# Colores para identificar visualmente los hallazgos.
ERROR_FILL = PatternFill(
    fill_type="solid",
    fgColor="FFC7CE",  # Rojo claro
)

WARNING_FILL = PatternFill(
    fill_type="solid",
    fgColor="FFEB9C",  # Amarillo claro
)


def get_next_version(output_dir: Path, original_name: str) -> Path:
    """Devuelve la siguiente ruta disponible para el reporte versionado.

    Ejemplo:
        Consultoria.xlsx
        -> Consultoria_validado_v1.xlsx
        -> Consultoria_validado_v2.xlsx
    """
    original_stem = Path(original_name).stem

    # Busca reportes previos de este archivo.
    pattern = re.compile(
        rf"^{re.escape(original_stem)}_validado_v(\d+)\.xlsx$",
        re.IGNORECASE,
    )

    existing_versions = []

    for file_path in output_dir.glob("*.xlsx"):
        match = pattern.match(file_path.name)
        if match:
            existing_versions.append(int(match.group(1)))

    # Si no existen versiones, empieza en 1.
    next_version = max(existing_versions, default=0) + 1

    return output_dir / f"{original_stem}_validado_v{next_version}.xlsx"


def mark_issues(workbook, validation_results) -> None:
    """Marca en el libro las celdas que tienen errores o advertencias.

    Cada RowIssue contiene:
        - sheet: nombre de la hoja
        - row: número de fila
        - column_name: encabezado de la columna
        - message: explicación del hallazgo
        - severity: error o warning
    """

    # Recorremos los resultados de validación hoja por hoja.
    for sheet_result in validation_results:
        sheet_name = sheet_result.sheet_name

        # Ignorar resultados si la hoja no existe en el libro.
        if sheet_name not in workbook.sheetnames:
            continue

        ws = workbook[sheet_name]

        # Construimos un mapa:
        # nombre de columna -> número de columna en Excel.
        #
        # Se asume que los encabezados están en la fila 1,
        # igual que en post_hoc_validator.py.
        column_by_name = {}

        for cell in ws[1]:
            if cell.value is not None:
                column_name = str(cell.value).strip()
                column_by_name[column_name] = cell.column

        # Aplicamos el marcado de cada hallazgo.
        for issue in sheet_result.issues:
            column_number = column_by_name.get(issue.column_name)

            # Si no encontramos el encabezado, no podemos ubicar
            # de forma segura la celda; dejamos registro en el log.
            if column_number is None:
                logger.warning(
                    "No se encontró la columna '%s' en la hoja '%s'.",
                    issue.column_name,
                    sheet_name,
                )
                continue

            cell = ws.cell(
                row=issue.row,
                column=column_number,
            )

            # Seleccionamos el color según la severidad.
            if issue.severity == "warning":
                cell.fill = copy(WARNING_FILL)
            else:
                cell.fill = copy(ERROR_FILL)

            # Si la celda ya tenía un comentario, lo conservamos
            # y agregamos el nuevo hallazgo al final.
            # El comentario debe mostrar únicamente el hallazgo actual.
            comment_text = f"[{issue.severity.upper()}] {issue.message}"

            cell.comment = Comment(comment_text, "Validador SNIES")


def process_file(xlsx_file: Path, output_dir: Path):
    """Valida un archivo y genera su copia marcada y versionada."""

    logger.info("Validando %s", xlsx_file.name)

    # Cargamos el archivo para validación con data_only=True.
    # Esto permite leer valores calculados de fórmulas cuando Excel
    # tiene guardados sus resultados en caché.
    wb_validation = openpyxl.load_workbook(
        xlsx_file,
        data_only=True,
    )

    validation_results = validate_workbook(wb_validation)

    # Contamos errores y advertencias para el log.
    errors = sum(
        1
        for sheet_result in validation_results
        for issue in sheet_result.issues
        if issue.severity == "error"
    )

    warnings = sum(
        1
        for sheet_result in validation_results
        for issue in sheet_result.issues
        if issue.severity == "warning"
    )

    logger.info(
        "  -> %d errores, %d advertencias",
        errors,
        warnings,
    )

    # Cargamos nuevamente el archivo SIN data_only=True.
    # Esta será la copia que guardaremos, para conservar fórmulas.
    wb_output = openpyxl.load_workbook(xlsx_file)

    # Marcamos los errores y advertencias en las celdas originales.
    mark_issues(wb_output, validation_results)

    # Calculamos el siguiente consecutivo para este archivo.
    output_path = get_next_version(output_dir, xlsx_file.name)

    # Guardamos una copia marcada, sin modificar el archivo de entrada.
    wb_output.save(output_path)

    logger.info("  -> Archivo marcado: %s", output_path.name)

    return validation_results


def main(input_dir: str, output_dir: str) -> None:
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    # Crear carpeta de salida si todavía no existe.
    out_path.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        logger.error("La carpeta de entrada no existe: %s", in_path)
        return

    all_results = {}

    # Procesamos cada archivo Excel de la carpeta de entrada.
    for xlsx_file in sorted(in_path.glob("*.xlsx")):

        # Evitar procesar archivos de reporte.
        if xlsx_file.name.lower().startswith(SKIP_PREFIXES):
            continue

        try:
            results = process_file(xlsx_file, out_path)
            all_results[xlsx_file.name] = results

        except Exception:
            logger.exception("Error validando %s", xlsx_file.name)

    # El reporte resumen se mantiene como complemento.
    # También se versiona para no sobrescribir ejecuciones anteriores.
    summary_path = get_next_version(
        out_path,
        "reporte_validacion_post_hoc.xlsx",
    )

    build_post_hoc_report(all_results).save(summary_path)

    logger.info("Reporte resumen guardado en %s", summary_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Uso: python validar_archivos.py "
            "<carpeta_entrada> <carpeta_salida>"
        )
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])