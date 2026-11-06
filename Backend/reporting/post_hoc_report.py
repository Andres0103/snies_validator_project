"""Reporte Excel de la validación post-hoc: un Resumen y un Detalle por fila con error."""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from validators.post_hoc_validator import SheetValidationResult

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
ERROR_FILL = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
WARNING_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def _autosize(ws):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 10), 70)


def build_post_hoc_report(all_results: dict[str, list[SheetValidationResult]]) -> Workbook:
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Resumen"
    summary_ws.append(["Archivo", "Hoja", "Filas con datos", "Errores", "Advertencias", "Columnas con comentario ambiguo"])
    _style_header(summary_ws)

    detail_ws = wb.create_sheet("Detalle")
    detail_ws.append(["Archivo", "Hoja", "Fila (Excel)", "Columna", "Valor", "Severidad", "Mensaje"])
    _style_header(detail_ws)

    total_errors = 0
    total_warnings = 0

    for fname, sheet_results in all_results.items():
        for sr in sheet_results:
            errors = sum(1 for i in sr.issues if i.severity == "error")
            warnings = sum(1 for i in sr.issues if i.severity == "warning")
            total_errors += errors
            total_warnings += warnings
            summary_ws.append([
                fname, sr.sheet_name, sr.total_rows, errors, warnings,
                ", ".join(sr.columns_needing_review) or "(ninguna)",
            ])

            for issue in sr.issues:
                detail_ws.append([
                    fname, issue.sheet, issue.row, issue.column_name,
                    str(issue.value) if issue.value is not None else "",
                    "Error" if issue.severity == "error" else "Advertencia",
                    issue.message,
                ])
                fill = ERROR_FILL if issue.severity == "error" else WARNING_FILL
                for cell in detail_ws[detail_ws.max_row]:
                    cell.fill = fill

    summary_ws.append([])
    summary_ws.append(["TOTAL", "", "", total_errors, total_warnings, ""])
    for cell in summary_ws[summary_ws.max_row]:
        cell.font = Font(bold=True)

    _autosize(summary_ws)
    _autosize(detail_ws)
    return wb
