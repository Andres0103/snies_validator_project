
"""CLI del motor de validación SNIES.

Uso:

Generar plantillas con validaciones nativas:
    python main.py <carpeta_entrada> <carpeta_salida>

Validar archivos Excel diligenciados:
    python main.py --post-hoc <carpeta_entrada> <carpeta_salida>
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import openpyxl
from openpyxl import Workbook

from excel_io.writer import ColumnReport, process_workbook
from excel_io.post_hoc_marker import mark_workbook

from reporting.report_generator import build_report_workbook
from reporting.post_hoc_report import build_post_hoc_report

from validators.post_hoc_validator import (
    SheetValidationResult,
    validate_workbook,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger("snies_validator")


SKIP_PREFIXES = (
    "validation_report",
    "_",
    "reporte_",
)

MARKED_SUFFIX = "_marcado"


def should_skip_file(file_path: Path) -> bool:
    """Determina si un archivo debe excluirse del procesamiento."""

    filename = file_path.name.lower()

    if filename.startswith(SKIP_PREFIXES):
        return True

    if filename.startswith("~$"):
        return True

    if file_path.stem.lower().endswith(MARKED_SUFFIX):
        return True

    return False


# ============================================================
# MODO 1: GENERACIÓN DE PLANTILLAS
# ============================================================

def process_file(
    input_path: Path,
    output_path: Path,
) -> list[ColumnReport]:

    logger.info("Procesando plantilla: %s", input_path.name)

    wb: Workbook = openpyxl.load_workbook(input_path)

    try:
        reports = process_workbook(wb)

        wb.save(output_path)

        logger.info(
            "  -> %s (%d columnas procesadas, %d requieren revisión manual)",
            output_path.name,
            len(reports),
            sum(1 for report in reports if report.needs_review),
        )

        return reports

    finally:
        wb.close()


def main(input_dir: str, output_dir: str) -> None:
    """Genera plantillas con validaciones nativas."""

    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        raise NotADirectoryError(
            f"La carpeta de entrada no existe: {in_path}"
        )

    out_path.mkdir(parents=True, exist_ok=True)

    all_reports: dict[str, list[ColumnReport]] = {}

    for xlsx_file in sorted(in_path.glob("*.xlsx")):

        if should_skip_file(xlsx_file):
            continue

        output_file = out_path / xlsx_file.name

        try:
            reports = process_file(xlsx_file, output_file)
            all_reports[xlsx_file.name] = reports

        except Exception:
            logger.exception(
                "Error procesando la plantilla %s",
                xlsx_file.name,
            )

    report_path = (
        out_path / "reporte_generacion_validaciones.xlsx"
    )

    build_report_workbook(all_reports).save(report_path)

    logger.info(
        "Reporte de generación guardado en %s",
        report_path,
    )


# ============================================================
# MODO 2: VALIDACIÓN POST-HOC
# ============================================================

def process_post_hoc_file(
    input_path: Path,
    output_path: Path,
) -> list[SheetValidationResult]:
    """Valida un Excel diligenciado y genera una copia marcada."""

    logger.info(
        "Validando archivo diligenciado: %s",
        input_path.name,
    )

    wb: Workbook = openpyxl.load_workbook(input_path)

    try:
        # 1. Ejecutar todas las validaciones sobre los datos originales.
        results = validate_workbook(wb)

        # 2. Marcar las celdas utilizando los resultados obtenidos.
        mark_workbook(wb, results)

        # 3. Guardar una copia del archivo con las marcas.
        wb.save(output_path)

        total_errors = sum(
            1
            for sheet in results
            for issue in sheet.issues
            if issue.severity == "error"
        )

        total_warnings = sum(
            1
            for sheet in results
            for issue in sheet.issues
            if issue.severity == "warning"
        )

        logger.info(
            "  -> %s | Hojas: %d | Errores: %d | Advertencias: %d",
            output_path.name,
            len(results),
            total_errors,
            total_warnings,
        )

        return results

    finally:
        wb.close()


def main_post_hoc(
    input_dir: str,
    output_dir: str,
) -> None:
    """Valida archivos diligenciados y genera las salidas post-hoc."""

    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        raise NotADirectoryError(
            f"La carpeta de entrada no existe: {in_path}"
        )

    out_path.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[SheetValidationResult]] = {}

    for xlsx_file in sorted(in_path.glob("*.xlsx")):

        if should_skip_file(xlsx_file):
            continue

        # Ejemplo: servicios.xlsx -> servicios_marcado.xlsx
        output_file = (
            out_path / f"{xlsx_file.stem}{MARKED_SUFFIX}.xlsx"
        )

        try:
            results = process_post_hoc_file(
                xlsx_file,
                output_file,
            )

            all_results[xlsx_file.name] = results

        except Exception:
            logger.exception(
                "Error validando el archivo %s",
                xlsx_file.name,
            )

    # Construir un único informe consolidado.
    report_path = (
        out_path / "reporte_validacion_post_hoc.xlsx"
    )

    report_wb = build_post_hoc_report(all_results)

    try:
        report_wb.save(report_path)
    finally:
        report_wb.close()

    logger.info(
        "Informe consolidado guardado en %s",
        report_path,
    )

    logger.info(
        "Archivos procesados correctamente: %d",
        len(all_results),
    )


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

def print_usage() -> None:
    print(
        "\nUso:\n"
        "  Generar plantillas:\n"
        "    python main.py <carpeta_entrada> <carpeta_salida>\n\n"
        "  Validar archivos diligenciados:\n"
        "    python main.py --post-hoc <carpeta_entrada> <carpeta_salida>\n"
    )


if __name__ == "__main__":

    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])

    elif len(sys.argv) == 4 and sys.argv[1] == "--post-hoc":
        main_post_hoc(sys.argv[2], sys.argv[3])

    else:
        print_usage()
        sys.exit(1)
