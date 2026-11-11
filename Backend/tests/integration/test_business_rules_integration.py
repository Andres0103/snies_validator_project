
from openpyxl import Workbook
from openpyxl.comments import Comment

from validators.post_hoc_validator import validate_workbook


def create_consultoria_workbook(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "CONSULTORIA"

    headers = [
        ("FECHA_INICIO", "Opcional, fecha."),
        ("FECHA_FINAL", "Opcional, fecha."),
    ]

    for col, (header, comment) in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.comment = Comment(comment, "Prueba")

    for row in rows:
        ws.append(row)

    return wb


def get_consultoria_issues(workbook):
    results = validate_workbook(workbook)

    result = next(
        item for item in results
        if item.sheet_name == "CONSULTORIA"
    )

    return result.issues


def issues_for_column(issues, column_name):
    return [
        issue for issue in issues
        if issue.row == 2
        and issue.column_name == column_name
    ]


def test_invalid_start_date_generates_cell_validation_error():
    wb = create_consultoria_workbook([
        ["fecha incorrecta", "15-12-2025"]
    ])

    issues = get_consultoria_issues(wb)

    start_date_issues = issues_for_column(
        issues, "FECHA_INICIO"
    )

    assert len(start_date_issues) == 1
    assert start_date_issues[0].severity == "error"


def test_invalid_final_date_generates_cell_validation_error_without_duplicate():
    wb = create_consultoria_workbook([
        ["10-12-2025", "fecha incorrecta"]
    ])

    issues = get_consultoria_issues(wb)

    final_date_issues = issues_for_column(
        issues, "FECHA_FINAL"
    )

    assert len(final_date_issues) == 1
    assert final_date_issues[0].severity == "error"


def test_final_date_equal_to_start_date_violates_strict_rule():
    wb = create_consultoria_workbook([
        ["10-12-2025", "10-12-2025"]
    ])

    issues = get_consultoria_issues(wb)

    final_date_issues = issues_for_column(
        issues, "FECHA_FINAL"
    )

    assert len(final_date_issues) == 1
    assert final_date_issues[0].severity == "error"
    assert "estrictamente posterior" in (
        final_date_issues[0].message.lower()
    )


def test_final_date_after_start_date_is_valid():
    wb = create_consultoria_workbook([
        ["10-12-2025", "15-12-2025"]
    ])

    issues = get_consultoria_issues(wb)

    date_issues = [
        issue for issue in issues
        if issue.row == 2
        and issue.column_name in {
            "FECHA_INICIO",
            "FECHA_FINAL",
        }
    ]

    assert date_issues == []


