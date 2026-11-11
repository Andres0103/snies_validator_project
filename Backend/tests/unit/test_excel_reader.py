import pytest
from openpyxl import Workbook

from backend.excel.reader import (
    CONTROL_SHEET_NAMES,
    HEADER_ROW,
    HeaderCell,
    is_data_sheet,
    iter_data_sheets,
    read_headers,
)


class TestIsDataSheet:

    @pytest.mark.parametrize(
        "sheet_name, expected",
        [
            ("Estudiantes", True),
            ("INFORMACION", True),
            ("INFO", False),
            ("info", False),
            ("Info", False),
            (" INFO ", False),
            ("_CONFIG", False),
            ("_auxiliar", False),
            ("__interno", False),
            ("", False),
            ("   ", False),
            ("_INFO", False),
            ("INFO_", True),
            ("DATOS_INFO", True),
        ],
    )
    def test_is_data_sheet(self, sheet_name, expected):
        assert is_data_sheet(sheet_name) is expected

    def test_control_sheet_names_contains_info(self):
        assert "INFO" in CONTROL_SHEET_NAMES

    def test_header_row_is_first_row(self):
        assert HEADER_ROW == 1


class TestIterDataSheets:

    def test_returns_only_data_sheets(self):
        workbook = Workbook()
        default_sheet = workbook.active
        default_sheet.title = "INFO"

        students = workbook.create_sheet("Estudiantes")
        programs = workbook.create_sheet("Programas")
        workbook.create_sheet("_CONFIG")

        result = iter_data_sheets(workbook)

        assert result == [students, programs]

    def test_preserves_workbook_sheet_order(self):
        workbook = Workbook()
        workbook.active.title = "Primera"
        second = workbook.create_sheet("Segunda")
        third = workbook.create_sheet("Tercera")

        result = iter_data_sheets(workbook)

        assert result == [workbook["Primera"], second, third]

    def test_returns_empty_list_when_all_sheets_are_excluded(self):
        workbook = Workbook()
        workbook.active.title = "INFO"
        workbook.create_sheet("_CONFIG")
        workbook.create_sheet("   ")

        assert iter_data_sheets(workbook) == []

    def test_does_not_modify_workbook(self):
        workbook = Workbook()
        workbook.active.title = "INFO"
        workbook.create_sheet("Datos")
        original_names = workbook.sheetnames.copy()

        iter_data_sheets(workbook)

        assert workbook.sheetnames == original_names

    def test_returns_worksheet_instances(self):
        workbook = Workbook()
        workbook.active.title = "Datos"

        result = iter_data_sheets(workbook)

        assert len(result) == 1
        assert result[0] is workbook["Datos"]


class TestHeaderCell:

    def test_header_cell_stores_all_attributes(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Estudiantes"
        cell = worksheet["A1"]
        cell.value = "CODIGO"

        header = HeaderCell(
            sheet_name="Estudiantes",
            column_name="CODIGO",
            column_letter="A",
            comment_text=None,
            cell=cell,
        )

        assert header.sheet_name == "Estudiantes"
        assert header.column_name == "CODIGO"
        assert header.column_letter == "A"
        assert header.comment_text is None
        assert header.cell is cell


class TestReadHeaders:

    def test_reads_headers_from_first_row(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["CODIGO", "NOMBRE", "ESTADO"])
        worksheet.append(["001", "Ana", "Activo"])

        headers = read_headers(worksheet)

        assert [header.column_name for header in headers] == [
            "CODIGO",
            "NOMBRE",
            "ESTADO",
        ]

    def test_does_not_read_values_from_other_rows(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["CODIGO", "NOMBRE"])
        worksheet.append(["001", "Ana"])
        worksheet.append(["002", "Luis"])

        headers = read_headers(worksheet)

        assert len(headers) == 2
        assert [header.column_name for header in headers] == [
            "CODIGO",
            "NOMBRE",
        ]

    def test_preserves_column_positions_when_none_cells_are_skipped(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["C1"] = "ESTADO"

        headers = read_headers(worksheet)

        assert len(headers) == 2
        assert [header.column_letter for header in headers] == ["A", "C"]

    def test_skips_cells_with_none_values(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["B1"] = None
        worksheet["C1"] = "ESTADO"

        headers = read_headers(worksheet)

        assert [header.column_name for header in headers] == [
            "CODIGO",
            "ESTADO",
        ]

    def test_preserves_empty_string_headers(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["B1"] = ""
        worksheet["C1"] = "ESTADO"

        headers = read_headers(worksheet)

        assert [header.column_name for header in headers] == [
            "CODIGO",
            "",
            "ESTADO",
        ]

    def test_preserves_whitespace_only_headers_as_empty_strings(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["B1"] = "   "

        headers = read_headers(worksheet)

        assert len(headers) == 2
        assert headers[1].column_name == ""

    def test_strips_outer_whitespace_from_header_names(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "  CODIGO  "

        headers = read_headers(worksheet)

        assert headers[0].column_name == "CODIGO"

    def test_preserves_internal_whitespace(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "NOMBRE DEL PROGRAMA"

        headers = read_headers(worksheet)

        assert headers[0].column_name == "NOMBRE DEL PROGRAMA"

    def test_converts_numeric_headers_to_strings(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = 123

        headers = read_headers(worksheet)

        assert headers[0].column_name == "123"
        assert isinstance(headers[0].column_name, str)

    def test_converts_date_headers_to_strings(self):
        from datetime import date

        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = date(2025, 1, 15)

        headers = read_headers(worksheet)

        assert headers[0].column_name == "2025-01-15"

    def test_extracts_header_comment(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["A1"].comment = Comment("Código único", "MEN")

        headers = read_headers(worksheet)

        assert headers[0].comment_text == "Código único"

    def test_returns_none_when_header_has_no_comment(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"

        headers = read_headers(worksheet)

        assert headers[0].comment_text is None

    def test_preserves_comment_text_without_interpreting_it(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        comment_text = "Obligatorio. Longitud máxima: 10. No modificar."
        worksheet["A1"].comment = Comment(comment_text, "MEN")

        headers = read_headers(worksheet)

        assert headers[0].comment_text == comment_text

    def test_returns_original_cell_reference(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"

        headers = read_headers(worksheet)

        assert headers[0].cell is worksheet["A1"]

    def test_returns_correct_sheet_name(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Estudiantes"
        worksheet["A1"] = "CODIGO"

        headers = read_headers(worksheet)

        assert headers[0].sheet_name == "Estudiantes"

    def test_returns_correct_column_letters(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        worksheet["C1"] = "ESTADO"
        worksheet["AA1"] = "OBSERVACION"

        headers = read_headers(worksheet)

        assert [header.column_letter for header in headers] == [
            "A",
            "C",
            "AA",
        ]

    def test_returns_empty_list_for_empty_worksheet(self):
        workbook = Workbook()
        worksheet = workbook.active

        assert read_headers(worksheet) == []

    def test_returns_empty_list_when_first_row_is_empty(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A2"] = "DATO"
        worksheet["B3"] = "OTRO DATO"

        assert read_headers(worksheet) == []

    def test_preserves_header_order(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Z", "A", "M", "B"])

        headers = read_headers(worksheet)

        assert [header.column_name for header in headers] == [
            "Z",
            "A",
            "M",
            "B",
        ]

    def test_does_not_modify_original_cells(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "  CODIGO  "
        original_value = worksheet["A1"].value

        read_headers(worksheet)

        assert worksheet["A1"].value == original_value

    def test_does_not_modify_comments(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["A1"] = "CODIGO"
        comment = Comment("Descripción", "MEN")
        worksheet["A1"].comment = comment

        read_headers(worksheet)

        assert worksheet["A1"].comment is comment
        assert worksheet["A1"].comment.text == "Descripción"


# Importación necesaria para crear comentarios de Excel.
from openpyxl.comments import Comment