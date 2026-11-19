
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import Workbook, load_workbook
from main import process_post_hoc_file


def snapshot_workbook(workbook):
    """
    Captura la estructura y los valores almacenados de todas
    las hojas del libro.
    """
    snapshot = {}

    for ws in workbook.worksheets:
        snapshot[ws.title] = {
            "max_row": ws.max_row,
            "max_column": ws.max_column,
            "values": tuple(
                tuple(
                    ws.cell(row=row, column=column).value
                    for column in range(1, ws.max_column + 1)
                )
                for row in range(1, ws.max_row + 1)
            ),
        }

    return snapshot


def test_post_hoc_pipeline_preserves_original_data(tmp_path):
    # Arrange: crear un archivo Excel de entrada.
    input_path = tmp_path / "original.xlsx"
    output_path = tmp_path / "validado.xlsx"

    wb = Workbook()

    ws = wb.active
    ws.title = "CONSULTORIA"

    ws["A1"] = "AÑO"
    ws["B1"] = "SEMESTRE"
    ws["C1"] = "CODIGO_CONSULTORIA"
    ws["D1"] = "DESCRIPCION_CONSULTORIA"
    ws["E1"] = "ID_CINE_CAMPO_DETALLADO"
    ws["F1"] = "NOMBRE_ENTIDAD"
    ws["G1"] = "ID_SECTOR_CONSULTORIA"
    ws["H1"] = "VALOR"
    ws["I1"] = "FECHA_INICIO"
    ws["J1"] = "FECHA_FINAL"

    ws.append([
        2025,
        1,
        "TEST001",
        "Consultoría de prueba",
        613,
        "Entidad de prueba",
        1,
        100000,
        "2025-01-15",
        "2025-02-15",
    ])

    # Columna sin encabezado, pero con información.
    ws["K1"] = None
    ws["K2"] = "Dato que debe preservarse"

    # Otra hoja para verificar que no desaparezca.
    ws2 = wb.create_sheet("CONSULTORIA_REC_HUMANO")

    ws2.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_CONSULTORIA",
        "ID_TIPO_DOCUMENTO",
        "NUM_DOCUMENTO",
        "ID_MAXIMO_NIVEL_ESTUDIO",
    ])

    ws2.append([
        2025,
        1,
        "TEST001",
        "CC",
        "123456789",
        5,
    ])

    original_snapshot = snapshot_workbook(wb)

    wb.save(input_path)
    wb.close()

    # Act: ejecutar el pipeline real de validación post-hoc.
    process_post_hoc_file(input_path, output_path)

    # Assert: comprobar que el archivo generado exista.
    assert output_path.exists()

    # Abrir nuevamente la entrada y la salida.
    original_wb = load_workbook(input_path, data_only=False)
    output_wb = load_workbook(output_path, data_only=False)

    try:
        # Comparar estructura y datos originales contra la salida.
        assert snapshot_workbook(output_wb) == snapshot_workbook(
            original_wb
        ), (
            "El pipeline modificó la estructura o los valores "
            "del archivo original."
        )

        # Verificar que la columna sin encabezado conserve su dato.
        assert (
            output_wb["CONSULTORIA"]["K2"].value
            == "Dato que debe preservarse"
        )

        # Verificar que las hojas originales sigan existiendo.
        assert "CONSULTORIA" in output_wb.sheetnames
        assert "CONSULTORIA_REC_HUMANO" in output_wb.sheetnames

    finally:
        original_wb.close()
        output_wb.close()
