
from rules.interpreter import interpret_comment
from validators.row_validator import validate_cell


def test_alphabetic_names():
    rule = interpret_comment(
        "PRIMER_NOMBRE",
        "Obligatorio, alfabético (50).",
    )

    valid_values = [
        "María",
        "Del Carmen",
        "D'León",
        "Ana-María",
        "José Luis",
    ]

    for value in valid_values:
        issues = validate_cell(rule, value)
        assert not issues, f"{value}: {issues}"


def test_descriptive_alphanumeric():
    rule = interpret_comment(
        "DESCRIPCION_CONSULTORIA",
        "Obligatorio, alfanumérico (200).",
    )

    valid_values = [
        "Consultoría para el desarrollo regional.",
        "Acompañamiento técnico a entidades públicas.",
        "Formación en gestión, planeación y evaluación.",
        "Proyecto de investigación (fase 2).",
    ]

    for value in valid_values:
        issues = validate_cell(rule, value)
        assert not issues, f"{value}: {issues}"


def test_description_length():
    rule = interpret_comment(
        "DESCRIPCION_CONSULTORIA",
        "Obligatorio, alfanumérico (200).",
    )

    value = "A" * 201
    issues = validate_cell(rule, value)

    assert any(
        "máximo permitido: 200" in issue.message
        for issue in issues
    )


if __name__ == "__main__":
    test_alphabetic_names()
    test_descriptive_alphanumeric()
    test_description_length()

    print("Pruebas de texto y longitud superadas.")
