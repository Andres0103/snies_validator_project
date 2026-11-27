from rules.interpreter import interpret_comment
from validators.row_validator import validate_cell


def test_semestre():
    # Construimos la regla utilizando el mismo intérprete del proyecto.
    rule = interpret_comment("SEMESTRE", "")

    # Comprobamos que la regla se haya construido correctamente.
    assert rule.required is True
    assert rule.max_length == 1

    allowed_values = {
        value.code
        for value in rule.allowed_values
    }

    assert allowed_values == {"1", "2"}

    # Valores que deben ser aceptados.
    valid_values = ["1", "2"]

    for value in valid_values:
        issues = validate_cell(rule, value)

        assert not issues, (
            f"El valor {value} debería ser válido, "
            f"pero produjo: {[issue.message for issue in issues]}"
        )

    # Valores que deben ser rechazados.
    invalid_values = ["-1", "-2"]

    for value in invalid_values:
        issues = validate_cell(rule, value)

        assert issues, (
            f"El valor {value} debería ser rechazado."
        )

    print("Prueba de validación real de SEMESTRE superada.")
    print("Valores aceptados: 1, 2.")
    print("Valores rechazados: -1, -2.")


if __name__ == "__main__":
    test_semestre()