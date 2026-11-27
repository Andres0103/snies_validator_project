
from pathlib import Path
import sys

from openpyxl import Workbook, load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from validators.post_hoc_validator import (
    RowIssue,
    SheetValidationResult,
)
from excel.post_hoc_marker import mark_workbook


# Crear un Excel de prueba.
wb = Workbook()
ws = wb.active
ws.title = "CONSULTORIA"

ws["A1"] = "FECHA_INICIO"
ws["B1"] = "FECHA_FINAL"

ws["A2"] = "2025-05-20"
ws["B2"] = "2025-05-10"

ws["A3"] = "2025-05-10"
ws["B3"] = "2025-05-20"


# Simular el resultado que entrega el validador.
result = SheetValidationResult(
    sheet_name="CONSULTORIA",
    total_rows=2,
    issues=[
        RowIssue(
            sheet="CONSULTORIA",
            row=2,
            column_name="FECHA_FINAL",
            value="2025-05-10",
            message=(
                "La fecha final debe ser igual o posterior "
                "a la fecha de inicio."
            ),
            severity="error",
        )
    ],
)


# Aplicar las marcas.
mark_workbook(wb, [result])

# Comprobar el resultado.
cell = ws["B2"]

print("Relleno aplicado:", cell.fill.fgColor.rgb)
print("Comentario:", cell.comment.text if cell.comment else None)

assert cell.fill.fgColor.rgb.endswith("FCE4E4")
assert cell.comment is not None
assert "La fecha final debe ser igual o posterior" in cell.comment.text

# Comprobar que la celda correcta fue marcada.
assert ws["B3"].comment is None

print("\nPrueba del marcador completada correctamente.")
