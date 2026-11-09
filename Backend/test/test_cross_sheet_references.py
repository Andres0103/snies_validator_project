
from openpyxl import Workbook

from validators.cross_sheet_validator import validate_sheet_references


def test_consultoria_child_must_reference_existing_parent():
    wb = Workbook()

    parent = wb.active
    parent.title = "CONSULTORIA"
    parent.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    parent.append([2026, -1, "CON-001"])

    child = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    child.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_CONSULTORIA",
        "NUM_DOCUMENTO",
    ])
    child.append([2026, -1, "CON-001", "123"])
    child.append([2026, -1, "CON-999", "456"])

    issues = validate_sheet_references(wb, "CONSULTORIA")

    assert len(issues) == 1
    assert issues[0]["sheet"] == "CONSULTORIA_REC_HUMANO"
    assert issues[0]["row"] == 3


def test_service_reference_uses_composite_key():
    wb = Workbook()

    parent = wb.active
    parent.title = "SERVICIOS_EXTENSION"
    parent.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_SERVICIO",
    ])
    parent.append([2026, -1, "U-01", "SER-01"])

    child = wb.create_sheet("SERV_EXT_AREA_TRABAJO")
    child.append([
        "AÑO",
        "SEMESTRE",
        "CODIGO_UNIDAD_ORGANIZACIONAL",
        "CODIGO_SERVICIO",
        "ID_AREA_TRABAJO",
    ])
    child.append([2026, -1, "U-01", "SER-01", 2])
    child.append([2026, -1, "U-02", "SER-01", 3])

    issues = validate_sheet_references(wb, "SERVICIOS_EXTENSION")

    assert len(issues) == 1
    assert issues[0]["row"] == 3


def test_empty_reference_key_is_not_duplicated():
    wb = Workbook()

    parent = wb.active
    parent.title = "CONSULTORIA"
    parent.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    parent.append([2026, -1, "CON-001"])

    child = wb.create_sheet("CONSULTORIA_REC_HUMANO")
    child.append(["AÑO", "SEMESTRE", "CODIGO_CONSULTORIA"])
    child.append([2026, -1, None])

    issues = validate_sheet_references(wb, "CONSULTORIA")

    assert issues == []
