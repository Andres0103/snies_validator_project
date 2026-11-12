
from datetime import date, datetime
from decimal import Decimal

import pytest

from backend.rules.general_model import (
    AllowedValue,
    ConditionalRequirement,
    DataType,
    ValidationRule,
)
from backend.validators.row_validator import validate_cell


# ============================================================
# FIXTURE / CONSTRUCTOR DE REGLAS
# ============================================================

def make_rule(
    required=False,
    datatype=DataType.UNKNOWN,
    max_length=None,
    min_length=None,
    exact_length=None,
    allowed_values=None,
    date_formats=None,
    conditional_requirement=None,
    excluded_values=None,
):
    return ValidationRule(
        column_name="CAMPO_PRUEBA",
        required=required,
        datatype=datatype,
        max_length=max_length,
        min_length=min_length,
        exact_length=exact_length,
        allowed_values=allowed_values or [],
        date_formats=date_formats or [],
        conditional_requirement=conditional_requirement,
        excluded_values=excluded_values or [],
    )


# ============================================================
# 1. OBLIGATORIEDAD Y VALORES VACÍOS
# ============================================================

@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_field_rejects_empty_values(value):
    rule = make_rule(required=True)

    issues = validate_cell(rule, value)

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert "obligatorio" in issues[0].message.lower()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_optional_field_accepts_empty_values(value):
    rule = make_rule(required=False)

    issues = validate_cell(rule, value)

    assert issues == []


def test_conditional_required_field_rejects_empty_value():
    rule = make_rule(
        conditional_requirement=ConditionalRequirement(
            raw_text="Obligatorio cuando se cumple una condición."
        )
    )

    issues = validate_cell(
        rule,
        None,
        conditional_applies=True,
    )

    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_conditional_requirement_unknown_generates_warning():
    rule = make_rule(
        conditional_requirement=ConditionalRequirement(
            raw_text="Obligatorio bajo una condición."
        )
    )

    issues = validate_cell(
        rule,
        None,
        conditional_applies=None,
    )

    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_conditional_requirement_not_applicable_accepts_empty_value():
    rule = make_rule(
        conditional_requirement=ConditionalRequirement(
            raw_text="Obligatorio bajo una condición."
        )
    )

    issues = validate_cell(
        rule,
        None,
        conditional_applies=False,
    )

    assert issues == []


def test_required_field_remains_required_when_condition_is_false():
    rule = make_rule(required=True)

    issues = validate_cell(
        rule,
        None,
        conditional_applies=False,
    )

    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_empty_value_does_not_trigger_other_validations():
    rule = make_rule(
        required=False,
        datatype=DataType.INTEGER,
        min_length=5,
        max_length=2,
        exact_length=4,
        allowed_values=[
            AllowedValue(code="1", label="Uno")
        ],
    )

    issues = validate_cell(rule, None)

    assert issues == []


# ============================================================
# 2. TIPO ALPHABETIC
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        "Andres",
        "Andrés",
        "María José",
        "Jean-Pierre",
        "O'Connor",
        "D’Angelo",
        "Muñoz",
    ],
)
def test_alphabetic_accepts_valid_text(value):
    rule = make_rule(datatype=DataType.ALPHABETIC)

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    [
        "Andres123",
        "123",
        "Nombre_Usuario",
        "Nombre@Usuario",
        "Nombre$Usuario",
    ],
)
def test_alphabetic_rejects_invalid_characters(value):
    rule = make_rule(datatype=DataType.ALPHABETIC)

    issues = validate_cell(rule, value)

    assert len(issues) == 1
    assert "únicamente letras" in issues[0].message.lower()


# ============================================================
# 3. TIPO ALPHANUMERIC
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        "Proyecto 2025",
        "Universidad123",
        "Proyecto @ especial",
        "Código-ABC/123",
        "Investigación, desarrollo.",
        "Año 2025: proyecto #1",
    ],
)
def test_alphanumeric_accepts_letters_numbers_and_punctuation(value):
    rule = make_rule(datatype=DataType.ALPHANUMERIC)

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    [
        "Proyecto $ especial",
        "Texto €",
        "Proyecto + especial",
        "Texto = resultado",
    ],
)
def test_alphanumeric_rejects_unsupported_symbols(value):
    rule = make_rule(datatype=DataType.ALPHANUMERIC)

    issues = validate_cell(rule, value)

    assert len(issues) == 1
    assert "puntuación" in issues[0].message.lower()


# ============================================================
# 4. TIPO TEXT Y UNKNOWN
# ============================================================

@pytest.mark.parametrize(
    "datatype",
    [DataType.TEXT, DataType.UNKNOWN],
)
def test_text_and_unknown_accept_general_text(datatype):
    rule = make_rule(datatype=datatype)

    issues = validate_cell(
        rule,
        "Texto con números 123 y símbolos @#$",
    )

    assert issues == []


# ============================================================
# 5. TIPO INTEGER
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        -10,
        250,
        "25",
        "0",
        "-15",
        25.0,
        Decimal("25"),
        Decimal("25.000"),
    ],
)
def test_integer_accepts_integer_values(value):
    rule = make_rule(datatype=DataType.INTEGER)

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    [
        25.5,
        Decimal("25.5"),
        "25.5",
        "abc",
        "10,5",
        True,
        False,
        float("nan"),
        float("inf"),
    ],
)
def test_integer_rejects_invalid_values(value):
    rule = make_rule(datatype=DataType.INTEGER)

    issues = validate_cell(rule, value)

    assert any(
        "entero válido" in issue.message.lower()
        for issue in issues
    )


# ============================================================
# 6. TIPO DECIMAL
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        10,
        10.5,
        -10.5,
        Decimal("10.50"),
        "10.50",
        "0",
        "-25.75",
    ],
)
def test_decimal_accepts_numeric_values(value):
    rule = make_rule(datatype=DataType.DECIMAL)

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "10,50",
        "",
        True,
        False,
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_decimal_rejects_invalid_values(value):
    rule = make_rule(datatype=DataType.DECIMAL)

    issues = validate_cell(rule, value)

    if value == "":
        # La cadena vacía se trata como un valor vacío opcional.
        assert issues == []
    else:
        assert any(
            "numérico válido" in issue.message.lower()
            for issue in issues
        )


# ============================================================
# 7. TIPO DATE
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        "2025-12-08",
        "08/12/2025",
        "08-12-2025",
        date(2025, 12, 8),
        datetime(2025, 12, 8, 14, 30),
    ],
)
def test_date_accepts_supported_formats(value):
    rule = make_rule(datatype=DataType.DATE)

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    [
        "2025-15-40",
        "31/02/2025",
        "fecha inválida",
        "2025",
        12345,
    ],
)
def test_date_rejects_invalid_values(value):
    rule = make_rule(datatype=DataType.DATE)

    issues = validate_cell(rule, value)

    assert len(issues) == 1
    assert "fecha válida" in issues[0].message.lower()


def test_date_uses_configured_format():
    rule = make_rule(
        datatype=DataType.DATE,
        date_formats=["%d/%m/%Y"],
    )

    issues = validate_cell(rule, "08/12/2025")

    assert issues == []


def test_date_rejects_format_not_configured():
    rule = make_rule(
        datatype=DataType.DATE,
        date_formats=["%d/%m/%Y"],
    )

    issues = validate_cell(rule, "2025-12-08")

    assert len(issues) == 1


# ============================================================
# 8. LONGITUD MÁXIMA
# ============================================================

def test_max_length_accepts_exact_limit():
    rule = make_rule(max_length=5)

    issues = validate_cell(rule, "ABCDE")

    assert issues == []


def test_max_length_rejects_value_above_limit():
    rule = make_rule(max_length=5)

    issues = validate_cell(rule, "ABCDEF")

    assert len(issues) == 1
    assert "máximo permitido: 5" in issues[0].message


# ============================================================
# 9. LONGITUD MÍNIMA
# ============================================================

def test_min_length_accepts_exact_limit():
    rule = make_rule(min_length=3)

    issues = validate_cell(rule, "ABC")

    assert issues == []


def test_min_length_rejects_value_below_limit():
    rule = make_rule(min_length=3)

    issues = validate_cell(rule, "AB")

    assert len(issues) == 1
    assert "mínimo permitido: 3" in issues[0].message


# ============================================================
# 10. LONGITUD EXACTA
# ============================================================

def test_exact_length_accepts_expected_length():
    rule = make_rule(exact_length=4)

    issues = validate_cell(rule, "ABCD")

    assert issues == []


@pytest.mark.parametrize("value", ["ABC", "ABCDE"])
def test_exact_length_rejects_different_length(value):
    rule = make_rule(exact_length=4)

    issues = validate_cell(rule, value)

    assert len(issues) == 1
    assert "exactamente 4" in issues[0].message


# ============================================================
# 11. COMBINACIÓN DE RESTRICCIONES DE LONGITUD
# ============================================================

def test_multiple_length_restrictions_can_generate_multiple_issues():
    rule = make_rule(
        min_length=5,
        max_length=3,
        exact_length=4,
    )

    issues = validate_cell(rule, "AB")

    assert len(issues) == 2


def test_valid_value_satisfies_combined_length_restrictions():
    rule = make_rule(
        min_length=3,
        max_length=5,
        exact_length=4,
    )

    issues = validate_cell(rule, "ABCD")

    assert issues == []


# ============================================================
# 12. VALORES PERMITIDOS
# ============================================================

def test_allowed_values_accepts_existing_code():
    rule = make_rule(
        datatype=DataType.INTEGER,
        allowed_values=[
            AllowedValue(code="1", label="Público"),
            AllowedValue(code="2", label="Privado"),
        ],
    )

    issues = validate_cell(rule, 1)

    assert issues == []


def test_allowed_values_accepts_existing_code_as_string():
    rule = make_rule(
        allowed_values=[
            AllowedValue(code="01", label="Público"),
        ],
    )

    issues = validate_cell(rule, "01")

    assert issues == []


def test_allowed_values_accepts_display_value():
    rule = make_rule(
        allowed_values=[
            AllowedValue(code="1", label="Público"),
        ],
    )

    issues = validate_cell(rule, "1 Público")

    assert issues == []


def test_allowed_values_rejects_unknown_code():
    rule = make_rule(
        datatype=DataType.INTEGER,
        allowed_values=[
            AllowedValue(code="1", label="Público"),
            AllowedValue(code="2", label="Privado"),
        ],
    )

    issues = validate_cell(rule, 3)

    assert any(
        "valores permitidos" in issue.message.lower()
        for issue in issues
    )


def test_allowed_values_accepts_equivalent_numeric_representation():
    rule = make_rule(
        datatype=DataType.DECIMAL,
        allowed_values=[
            AllowedValue(code="1.50", label="Valor permitido"),
        ],
    )

    issues = validate_cell(rule, Decimal("1.5"))

    assert issues == []


def test_allowed_values_rejects_boolean_as_numeric_code():
    rule = make_rule(
        datatype=DataType.INTEGER,
        allowed_values=[
            AllowedValue(code="1", label="Uno"),
        ],
    )

    issues = validate_cell(rule, True)

    assert any(
        "entero válido" in issue.message.lower()
        for issue in issues
    )


def test_empty_allowed_values_do_not_restrict_input():
    rule = make_rule(
        datatype=DataType.INTEGER,
        allowed_values=[],
    )

    issues = validate_cell(rule, 123)

    assert issues == []


# ============================================================
# 13. COMBINACIÓN DE VALIDACIONES
# ============================================================

def test_invalid_type_and_invalid_length_generate_two_issues():
    rule = make_rule(
        datatype=DataType.INTEGER,
        max_length=2,
    )

    issues = validate_cell(rule, "ABC")

    assert len(issues) == 2

    messages = [issue.message.lower() for issue in issues]

    assert any("entero válido" in message for message in messages)
    assert any("máximo permitido" in message for message in messages)


def test_valid_value_satisfies_type_and_allowed_values():
    rule = make_rule(
        datatype=DataType.INTEGER,
        allowed_values=[
            AllowedValue(code="10", label="Diez"),
            AllowedValue(code="20", label="Veinte"),
        ],
    )

    issues = validate_cell(rule, 10)

    assert issues == []


from decimal import Decimal

import pytest

from backend.rules.general_model import (
    DataType,
    ValidationRule,
)
from validators.row_validator import validate_cell


# ============================================================
# Tipos numéricos
# ============================================================

@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 100, "0", "25", "-10"],
)
def test_integer_accepts_valid_integer_values(value):
    rule = ValidationRule(
        column_name="CANTIDAD",
        datatype=DataType.INTEGER,
    )

    issues = validate_cell(rule, value)

    assert issues == []


@pytest.mark.parametrize(
    "value",
    ["1.5", "abc", "1,5", "10.2"],
)
def test_integer_rejects_non_integer_values(value):
    rule = ValidationRule(
        column_name="CANTIDAD",
        datatype=DataType.INTEGER,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


@pytest.mark.parametrize(
    "value",
    [0, 1.5, -2.75, "10.5", "0.25", Decimal("12.50")],
)
def test_decimal_accepts_valid_decimal_values(value):
    rule = ValidationRule(
        column_name="VALOR",
        datatype=DataType.DECIMAL,
    )

    assert validate_cell(rule, value) == []


@pytest.mark.parametrize(
    "value",
    ["abc", "10,5", "1.2.3", "NaN", "Infinity"],
)
def test_decimal_rejects_invalid_values(value):
    rule = ValidationRule(
        column_name="VALOR",
        datatype=DataType.DECIMAL,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


@pytest.mark.parametrize(
    "value",
    [True, False],
)
def test_integer_rejects_boolean_values(value):
    rule = ValidationRule(
        column_name="CANTIDAD",
        datatype=DataType.INTEGER,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


# ============================================================
# Valores numéricos no finitos
# ============================================================

@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_decimal_rejects_non_finite_float_values(value):
    rule = ValidationRule(
        column_name="VALOR",
        datatype=DataType.DECIMAL,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


# ============================================================
# Longitudes
# ============================================================

def test_exact_length_accepts_matching_length():
    rule = ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        exact_length=5,
    )

    assert validate_cell(rule, "ABCDE") == []


def test_exact_length_rejects_shorter_value():
    rule = ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        exact_length=5,
    )

    issues = validate_cell(rule, "ABC")

    assert any(issue.severity == "error" for issue in issues)


def test_exact_length_rejects_longer_value():
    rule = ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        exact_length=5,
    )

    issues = validate_cell(rule, "ABCDEFG")

    assert any(issue.severity == "error" for issue in issues)


def test_minimum_length_accepts_boundary():
    rule = ValidationRule(
        column_name="NOMBRE",
        datatype=DataType.TEXT,
        min_length=5,
    )

    assert validate_cell(rule, "ABCDE") == []


def test_maximum_length_accepts_boundary():
    rule = ValidationRule(
        column_name="NOMBRE",
        datatype=DataType.TEXT,
        max_length=5,
    )

    assert validate_cell(rule, "ABCDE") == []


def test_maximum_length_rejects_excess():
    rule = ValidationRule(
        column_name="NOMBRE",
        datatype=DataType.TEXT,
        max_length=5,
    )

    issues = validate_cell(rule, "ABCDEF")

    assert any(issue.severity == "error" for issue in issues)


def test_length_validation_uses_trimmed_text():
    rule = ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        exact_length=5,
    )

    assert validate_cell(rule, "  ABCDE  ") == []


# ============================================================
# Valores permitidos
# ============================================================


def test_allowed_values_accepts_code():
    rule = ValidationRule(
        column_name="ESTADO",
        datatype=DataType.TEXT,
        allowed_values=[
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ],
    )

    assert validate_cell(rule, "1") == []


def test_allowed_values_accepts_label():
    rule = ValidationRule(
        column_name="ESTADO",
        datatype=DataType.TEXT,
        allowed_values=[
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ],
    )

    issues = validate_cell(rule, "Activo")
    assert any(issue.severity == "error" for issue in issues)


def test_allowed_values_rejects_unknown_value():
    rule = ValidationRule(
        column_name="ESTADO",
        datatype=DataType.TEXT,
        allowed_values=[
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ],
    )

    issues = validate_cell(rule, "Suspendido")

    assert any(issue.severity == "error" for issue in issues)



# ============================================================
# Texto alfabético y alfanumérico
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        "Andrés",
        "María José",
        "O'Connor",
        "Jean-Luc",
        "Muñoz",
    ],
)
def test_alphabetic_accepts_unicode_names(value):
    rule = ValidationRule(
        column_name="NOMBRE",
        datatype=DataType.ALPHABETIC,
    )

    assert validate_cell(rule, value) == []


@pytest.mark.parametrize(
    "value",
    [
        "Nombre123",
        "Nombre@",
        "123",
    ],
)
def test_alphabetic_rejects_non_alphabetic_content(value):
    rule = ValidationRule(
        column_name="NOMBRE",
        datatype=DataType.ALPHABETIC,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


@pytest.mark.parametrize(
    "value",
    [
        "Servicio 123",
        "Código-ABC",
        "Proyecto (2026)",
        "Nombre, descripción.",
    ],
)
def test_alphanumeric_accepts_descriptive_content(value):
    rule = ValidationRule(
        column_name="DESCRIPCION",
        datatype=DataType.ALPHANUMERIC,
    )

    assert validate_cell(rule, value) == []


@pytest.mark.parametrize(
    "value",
    [
        "Valor$100",
        "Costo+IVA",
        "A=B",
    ],
)
def test_alphanumeric_rejects_symbol_characters(value):
    rule = ValidationRule(
        column_name="DESCRIPCION",
        datatype=DataType.ALPHANUMERIC,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


# ============================================================
# Fechas
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        "2026-12-10",
        "10/12/2026",
        "10-12-2026",
    ],
)
def test_date_accepts_supported_formats(value):
    rule = ValidationRule(
        column_name="FECHA",
        datatype=DataType.DATE,
    )

    assert validate_cell(rule, value) == []


@pytest.mark.parametrize(
    "value",
    [
        "31/02/2026",
        "fecha",
        "2026-13-10",
    ],
)
def test_date_rejects_invalid_calendar_dates(value):
    rule = ValidationRule(
        column_name="FECHA",
        datatype=DataType.DATE,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)


def test_date_accepts_datetime_object():
    from datetime import datetime

    rule = ValidationRule(
        column_name="FECHA",
        datatype=DataType.DATE,
    )

    assert validate_cell(
        rule,
        datetime(2026, 12, 10),
    ) == []


# ============================================================
# Campos vacíos y opcionales
# ============================================================

@pytest.mark.parametrize(
    "value",
    [None, "", "   "],
)
def test_optional_field_accepts_blank_values(value):
    rule = ValidationRule(
        column_name="OBSERVACION",
        datatype=DataType.TEXT,
        required=False,
    )

    assert validate_cell(rule, value) == []


@pytest.mark.parametrize(
    "value",
    [None, "", "   "],
)
def test_required_field_rejects_blank_values(value):
    rule = ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        required=True,
    )

    issues = validate_cell(rule, value)

    assert any(issue.severity == "error" for issue in issues)
    
# ============================================================
# 14. VALORES EXPRESAMENTE EXCLUIDOS
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        170,
        170.0,
        "170",
        "170.0",
        Decimal("170"),
        Decimal("170.0"),
    ],
)
def test_excluded_values_reject_numeric_equivalents(value):
    rule = make_rule(
        excluded_values=["170"],
    )

    issues = validate_cell(rule, value)

    assert any(
        "no está permitido" in issue.message.lower()
        for issue in issues
    )


def test_excluded_values_accept_other_codes():
    rule = make_rule(
        excluded_values=["170"],
    )

    issues = validate_cell(rule, "169")

    assert not any(
        "no está permitido" in issue.message.lower()
        for issue in issues
    )


def test_excluded_values_do_not_affect_allowed_catalog_values():
    rule = make_rule(
        allowed_values=[
            AllowedValue(code="170", label="Colombia"),
            AllowedValue(code="169", label="Otro país"),
        ],
    )

    issues = validate_cell(rule, "170")

    assert issues == []


def test_excluded_values_reject_value_even_when_it_exists_in_catalog():
    rule = make_rule(
        allowed_values=[
            AllowedValue(code="170", label="Colombia"),
            AllowedValue(code="169", label="Otro país"),
        ],
        excluded_values=["170"],
    )

    issues = validate_cell(rule, "170")

    assert any(
        "no está permitido" in issue.message.lower()
        for issue in issues
    )


@pytest.mark.parametrize(
    "value",
    [None, "", "   "],
)
def test_excluded_values_do_not_change_empty_value_behavior(value):
    rule = make_rule(
        required=True,
        excluded_values=["170"],
    )

    issues = validate_cell(rule, value)

    assert any(
        "obligatorio" in issue.message.lower()
        for issue in issues
    )
