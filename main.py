"""CLI del motor de validación SNIES.

Uso:
    python main.py <carpeta_entrada> <carpeta_salida>

Procesa todos los .xlsx de <carpeta_entrada> (excepto los que empiecen con
"validation_report" o "_", que son salidas de otras herramientas) y
escribe en <carpeta_salida> una copia de cada uno con las validaciones
nativas aplicadas, preservando el resto del archivo intacto. También
genera un `reporte_generacion.xlsx` consolidado.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import openpyxl
from openpyxl import Workbook

from excel_io.writer import ColumnReport, process_workbook
from reporting.report_generator import build_report_workbook

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("snies_validator")

SKIP_PREFIXES = ("validation_report", "_", "reporte_")


def process_file(input_path: Path, output_path: Path) -> list[ColumnReport]:
    logger.info("Procesando %s", input_path.name)
    wb: Workbook = openpyxl.load_workbook(input_path)
    reports = process_workbook(wb)
    wb.save(output_path)
    logger.info(
        "  -> %s (%d columnas procesadas, %d requieren revisión manual)",
        output_path.name,
        len(reports),
        sum(1 for r in reports if r.needs_review),
    )
    return reports


def main(input_dir: str, output_dir: str) -> None:
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    all_reports: dict[str, list[ColumnReport]] = {}

    for xlsx_file in sorted(in_path.glob("*.xlsx")):
        if xlsx_file.name.lower().startswith(SKIP_PREFIXES):
            continue
        output_file = out_path / xlsx_file.name
        try:
            reports = process_file(xlsx_file, output_file)
            all_reports[xlsx_file.name] = reports
        except Exception:
            logger.exception("Error procesando %s", xlsx_file.name)

    report_path = out_path / "reporte_generacion_validaciones.xlsx"
    build_report_workbook(all_reports).save(report_path)
    logger.info("Reporte consolidado guardado en %s", report_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python main.py <carpeta_entrada> <carpeta_salida>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
