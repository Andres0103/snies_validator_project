
from rules.interpreter import interpret_comment
from validators.row_validator import validate_cell


def test_nombre_entidad():
    rule = interpret_comment(
        "NOMBRE_ENTIDAD",
        "Obligatorio, alfanumérico (200).",
    )

    valid_values = [
        "Gobernación de Antioquia",
        "Facultad de Medicina - Grupo NACER",
        "Corporación de Alta Tecnología para la Defensa",
        "Ingenieros Electricos S.A.S",
        "E.S.E. Norte 3",
    ]

    for value in valid_values:
        issues = validate_cell(rule, value)
        assert not issues, f"Se rechazó incorrectamente: {value}"


def test_nombre_institucion():
    rule = interpret_comment(
        "NOMBRE_INSTITUCION",
        "Obligatorio, alfanumérico (200).",
    )

    valid_values = [
        "Universidad de Antioquia",
        "Organización de Estados Iberoamericanos (OEI)",
        "Institución Educativa N.º 3",
    ]

    for value in valid_values:
        issues = validate_cell(rule, value)
        assert not issues, f"Se rechazó incorrectamente: {value}"


def test_nombre_entidad_longitud():
    rule = interpret_comment(
        "NOMBRE_ENTIDAD",
        "Obligatorio, alfanumérico (200).",
    )

    issues = validate_cell(rule, "A" * 201)

    assert any(
        "máximo permitido: 200" in issue.message
        for issue in issues
    )
