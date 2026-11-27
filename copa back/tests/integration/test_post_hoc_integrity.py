from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import Workbook, load_workbook
from validators.post_hoc_validator import RowIssue, SheetValidationResult
from excel.post_hoc_marker import mark_workbook


def snapshot_values(workbook):
    """
    Captura los nombres de hojas, dimensiones y valores almacenados
    para comprobar que el marcado no modifica los datos.
    """
    return {
        ws.title: {
            "max_row": ws.max_row,
            "max_column": ws.max_column,
            "values": {
                cell.coordinate: cell.value
                for row in ws.iter_rows()
                for cell in row
                if cell.value is not None
            },
        }
        for ws in workbook.worksheets
    }


def test_post_hoc_marking_preserves_original_values(tmp_path):
    # Arrange: crear un libro de prueba con datos y una columna
    # sin encabezado, como las que encontramos en CONSULTORIA.
    wb = Workbook()
    ws = wb.active
    ws.title = "CONSULTORIA"

    ws["A1"] = "CODIGO"
    ws["B1"] = "DESCRIPCION"
    ws["C1"] = None  # Encabezado intencionalmente vacío
    ws["D1"] = "VALOR"

    ws["A2"] = "001"
    ws["B2"] = "Texto de prueba"
    ws["C2"] = "Dato en columna sin encabezado"
    ws["D2"] = 125000

    ws["A3"] = "002"
    ws["B3"] = "Otro texto"
    ws["C3"] = "Otro dato sin encabezado"
    ws["D3"] = 0

    # Guardar el estado original de los valores.
    original_snapshot = snapshot_values(wb)

    # Crear un error de prueba para marcar.
    result = SheetValidationResult(
        sheet_name="CONSULTORIA",
        total_rows=2,
        issues=[
            RowIssue(
                sheet="CONSULTORIA",
                row=2,
                column_name="VALOR",
                value=125000,
                message="Prueba de marcación",
                severity="error",
            )
        ],
    )

    # Act: marcar el libro y guardarlo.
    mark_workbook(wb, [result])

    output_path = tmp_path / "marcado.xlsx"
    wb.save(output_path)
    wb.close()

    # Abrir nuevamente el archivo guardado.
    reopened = load_workbook(output_path, data_only=False)

    # Assert: los valores y dimensiones deben ser idénticos.
    assert snapshot_values(reopened) == original_snapshot

    # Comprobar que el marcado sí se aplicó.
    assert reopened["CONSULTORIA"]["D2"].comment is not None
    assert reopened["CONSULTORIA"]["D2"].fill.fgColor.rgb.endswith("FCE4E4")

    reopened.close()