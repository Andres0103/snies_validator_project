
from validators.post_hoc_validator import (
    _conditional_requirement_applies,
)
from validators.row_validator import validate_cell
from rules.interpreter import interpret_comment


RULES = {
    "conditional_required_fields": {
        "CONSULTORIA": {
            "VLR_FINANCIACION_NACIONAL": {
                "when": {
                    "column": "ID_FUENTE_NACIONAL",
                    "operator": "not_blank",
                }
            },
            "VLR_FINANCIACION_INTERNACIONAL": {
                "when": {
                    "column": "ID_FUENTE_INTERNACIONAL",
                    "operator": "not_blank",
                }
            },
            "NOMBRE_INSTITUCION": {
                "when": {
                    "any": [
                        {
                            "column": "ID_FUENTE_INTERNACIONAL",
                            "operator": "not_blank",
                        },
                        {
                            "column": "VLR_FINANCIACION_INTERNACIONAL",
                            "operator": "gt",
                            "value": 0,
                        },
                    ]
                }
            },
            "ID_PAIS_FINANCIADOR": {
                "when": {
                    "any": [
                        {
                            "column": "ID_FUENTE_INTERNACIONAL",
                            "operator": "not_blank",
                        },
                        {
                            "column": "VLR_FINANCIACION_INTERNACIONAL",
                            "operator": "gt",
                            "value": 0,
                        },
                    ]
                }
            },
        }
    }
}


def check_field(column, comment, row, expected):
    rule = interpret_comment(column, comment)

    applies = _conditional_requirement_applies(
        RULES,
        "CONSULTORIA",
        column,
        row,
    )

    issues = validate_cell(
        rule,
        None,
        conditional_applies=applies,
    )

    assert applies is expected, (
        f"{column}: se esperaba applies={expected}, "
        f"pero se obtuvo {applies}. Fila: {row}"
    )

    if expected:
        assert len(issues) == 1, (
            f"{column}: debía generar un error por estar vacío. "
            f"Incidencias: {issues}"
        )
        assert issues[0].severity == "error"
    else:
        assert len(issues) == 0, (
            f"{column}: no debía generar incidencias. "
            f"Incidencias: {issues}"
        )


def test_national_financing():
    check_field(
        "VLR_FINANCIACION_NACIONAL",
        "Opcional, numérico (15).",
        {"ID_FUENTE_NACIONAL": 1},
        True,
    )

    check_field(
        "VLR_FINANCIACION_NACIONAL",
        "Opcional, numérico (15).",
        {"ID_FUENTE_NACIONAL": None},
        False,
    )


def test_international_financing():
    check_field(
        "VLR_FINANCIACION_INTERNACIONAL",
        "Opcional, numérico (15).",
        {"ID_FUENTE_INTERNACIONAL": 1},
        True,
    )

    check_field(
        "VLR_FINANCIACION_INTERNACIONAL",
        "Opcional, numérico (15).",
        {"ID_FUENTE_INTERNACIONAL": None},
        False,
    )


def test_international_institution():
    comment = "Opcional, alfanumérico (200)."

    check_field(
        "NOMBRE_INSTITUCION",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": 1,
            "VLR_FINANCIACION_INTERNACIONAL": None,
        },
        True,
    )

    check_field(
        "NOMBRE_INSTITUCION",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": None,
            "VLR_FINANCIACION_INTERNACIONAL": 100,
        },
        True,
    )

    check_field(
        "NOMBRE_INSTITUCION",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": None,
            "VLR_FINANCIACION_INTERNACIONAL": 0,
        },
        False,
    )


def test_international_country():
    comment = "Opcional, numérico (3)."

    check_field(
        "ID_PAIS_FINANCIADOR",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": 1,
            "VLR_FINANCIACION_INTERNACIONAL": None,
        },
        True,
    )

    check_field(
        "ID_PAIS_FINANCIADOR",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": None,
            "VLR_FINANCIACION_INTERNACIONAL": 100,
        },
        True,
    )

    check_field(
        "ID_PAIS_FINANCIADOR",
        comment,
        {
            "ID_FUENTE_INTERNACIONAL": None,
            "VLR_FINANCIACION_INTERNACIONAL": 0,
        },
        False,
    )


def run_all_tests():
    test_national_financing()
    print("OK: financiación nacional")

    test_international_financing()
    print("OK: financiación internacional")

    test_international_institution()
    print("OK: nombre de institución")

    test_international_country()
    print("OK: país financiador")

    print("\nTodas las pruebas condicionales fueron superadas.")


if __name__ == "__main__":
    run_all_tests()
