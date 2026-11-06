"""Genera el reporte consolidado de generación de validaciones.

Complementa (no reemplaza) al validador post-hoc que ya existía: mientras
ese reporta errores en datos ya diligenciados, este reporta qué reglas se
lograron interpretar y aplicar de forma NATIVA en cada plantilla, y qué
columnas quedaron marcadas para revisión manual.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from excel_io.writer import ColumnReport

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
REVIEW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")


def build_report_workbook(all_reports: dict[str, list[ColumnReport]]) -> Workbook:
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Resumen"

    summary_ws.append(["Archivo", "Columnas procesadas", "Validaciones aplicadas", "Requieren revisión manual"])
    for cell in summary_ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    for fname, reports in all_reports.items():
        applied = sum(1 for r in reports if r.validations_applied)
        review = sum(1 for r in reports if r.needs_review)
        summary_ws.append([fname, len(reports), applied, review])

    detail_ws = wb.create_sheet("Detalle")
    headers = [
        "Archivo", "Hoja", "Columna", "Obligatorio", "Tipo de dato",
        "Longitud máx.", "Valores permitidos", "Validaciones aplicadas",
        "Requiere revisión", "Fragmentos no interpretados",
    ]
    detail_ws.append(headers)
    for cell in detail_ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    for fname, reports in all_reports.items():
        for r in reports:
            rule = r.rule
            row = [
                fname,
                r.sheet_name,
                r.column_name,
                "Sí" if rule.required else ("Condicional" if rule.conditional_requirement else "No"),
                rule.datatype.value,
                rule.max_length or "",
                len(rule.allowed_values) or "",
                ", ".join(r.validations_applied) or "(ninguna)",
                "Sí" if r.needs_review else "",
                "; ".join(rule.unparsed_fragments),
            ]
            detail_ws.append(row)
            if r.needs_review:
                for cell in detail_ws[detail_ws.max_row]:
                    cell.fill = REVIEW_FILL

    for ws in (summary_ws, detail_ws):
        for col_cells in ws.columns:
            length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 10), 60)

    return wb
