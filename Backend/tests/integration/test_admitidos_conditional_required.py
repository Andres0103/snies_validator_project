
from openpyxl import Workbook

from validators.post_hoc_validator import validate_workbook


HEADERS = [
    "AÑO",
    "SEMESTRE",
    "ID_TIPO_DOCUMENTO",
    "NUM_DOCUMENTO",
    "PRO_CONSECUTIVO",
    "ID_MUNICIPIO",
    "TELEFONO_CONTACTO",
    "EMAIL_PERSONAL",
    "FECHA_NACIMIENTO",
    "ID_ESTRATO",
    "ID_BENEFICIARIO_LEY_VETERANOS",
]


def create_admitidos_workbook(year, semester):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ADMITIDO"

    sheet.append(HEADERS)

    sheet.append([
        year,
        semester,
        "CC",
        "123456789",
        123456,
        "05001",
        None,
        None,
        None,
        None,
        None,
    ])

    return workbook


def get_issues_for_column(results, column_name):
    return [
        issue
        for result in results
        for issue in result.issues
        if issue.column_name == column_name
    ]


def test_estrato_optional_before_2022():
    workbook = create_admitidos_workbook(2021, 2)

    results = validate_workbook(
        workbook,
        template_name="ADMITIDOS",
    )

    issues = get_issues_for_column(results, "ID_ESTRATO")

    assert issues == []


def test_estrato_required_from_2022():
    workbook = create_admitidos_workbook(2022, 1)

    results = validate_workbook(
        workbook,
        template_name="ADMITIDOS",
    )

    issues = get_issues_for_column(results, "ID_ESTRATO")

    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_veterans_optional_before_2023():
    workbook = create_admitidos_workbook(2022, 2)

    results = validate_workbook(
        workbook,
        template_name="ADMITIDOS",
    )

    issues = get_issues_for_column(
        results,
        "ID_BENEFICIARIO_LEY_VETERANOS",
    )

    assert issues == []


def test_veterans_required_from_2023():
    workbook = create_admitidos_workbook(2023, 1)

    results = validate_workbook(
        workbook,
        template_name="ADMITIDOS",
    )

    issues = get_issues_for_column(
        results,
        "ID_BENEFICIARIO_LEY_VETERANOS",
    )

    assert len(issues) == 1
    assert issues[0].severity == "error"
