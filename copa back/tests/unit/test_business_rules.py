from validators.row_validator import validate_business_rule

def test_non_negative_does_not_validate_numeric_type():
    issues = validate_business_rule(
        "non_negative", {}, "texto", {}
    )
    assert issues == []


def test_non_negative_with_min_length_does_not_validate_numeric_type():
    issues = validate_business_rule(
        "non_negative_with_min_length",
        {"min_length": 1},
        "abc",
        {},
    )
    assert issues == []


def test_date_within_past_years_does_not_validate_date_format():
    issues = validate_business_rule(
        "date_within_past_years",
        {"years": 80},
        "fecha incorrecta",
        {},
    )
    assert issues == []


def test_date_after_column_does_not_validate_current_date_format():
    issues = validate_business_rule(
        "date_after_column",
        {"after_column": "FECHA_INICIO"},
        "fecha incorrecta",
        {"FECHA_INICIO": "2025-12-08"},
    )
    assert issues == []


def test_date_after_column_does_not_validate_reference_date_format():
    issues = validate_business_rule(
        "date_after_column",
        {"after_column": "FECHA_INICIO"},
        "2025-12-10",
        {"FECHA_INICIO": "fecha incorrecta"},
    )
    assert issues == []


def test_date_after_column_with_missing_reference_column():
    issues = validate_business_rule(
        "date_after_column",
        {"after_column": "FECHA_INICIO"},
        "2025-12-10",
        {},
    )
    assert issues == []
