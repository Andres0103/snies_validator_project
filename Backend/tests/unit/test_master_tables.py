import pytest
import yaml

from pathlib import Path

from backend.rules.general_model import (
    AllowedValue,
    DataType,
    ValidationRule,
)

import backend.rules.master_tables as master_tables


@pytest.fixture
def catalogs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        master_tables,
        "CATALOGS_DIR",
        tmp_path,
    )
    return tmp_path


def write_yaml(directory, filename, data):
    path = directory / filename
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def make_rule(allowed_values=None):
    return ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
        allowed_values=allowed_values or [],
    )


# ============================================================
# _read_yaml
# ============================================================

def test_read_yaml_returns_dictionary(tmp_path):
    path = write_yaml(
        tmp_path,
        "catalogo.yaml",
        {"nombre": "Colombia"},
    )

    assert master_tables._read_yaml(path) == {
        "nombre": "Colombia"
    }


def test_read_yaml_preserves_unicode(tmp_path):
    path = write_yaml(
        tmp_path,
        "catalogo.yaml",
        {"nombre": "Clasificación académica"},
    )

    result = master_tables._read_yaml(path)

    assert result["nombre"] == "Clasificación académica"


def test_read_yaml_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="No se encontró"):
        master_tables._read_yaml(tmp_path / "missing.yaml")


def test_read_yaml_rejects_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="No se encontró"):
        master_tables._read_yaml(tmp_path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "- Colombia",
        "texto",
        "123",
        "null",
    ],
)
def test_read_yaml_rejects_non_dictionary_yaml(tmp_path, content):
    path = tmp_path / "catalogo.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="diccionario YAML"):
        master_tables._read_yaml(path)


def test_read_yaml_rejects_malformed_yaml(tmp_path):
    path = tmp_path / "catalogo.yaml"
    path.write_text("nombre: [Colombia\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        master_tables._read_yaml(path)


# ============================================================
# _build_allowed_values
# ============================================================

def test_build_allowed_values_converts_records():
    records = [
        {"codigo": "1", "nombre": "Activo"},
        {"codigo": "2", "nombre": "Inactivo"},
    ]

    result = master_tables._build_allowed_values(
        records,
        "codigo",
        "nombre",
        "estados",
    )

    assert result == [
        AllowedValue(code="1", label="Activo"),
        AllowedValue(code="2", label="Inactivo"),
    ]


def test_build_allowed_values_trims_code_and_label():
    result = master_tables._build_allowed_values(
        [{"codigo": " 1 ", "nombre": " Activo "}],
        "codigo",
        "nombre",
        "estados",
    )

    assert result == [
        AllowedValue(code="1", label="Activo")
    ]


def test_build_allowed_values_preserves_leading_zeros():
    result = master_tables._build_allowed_values(
        [{"codigo": "001", "nombre": "Activo"}],
        "codigo",
        "nombre",
        "estados",
    )

    assert result[0].code == "001"


def test_build_allowed_values_accepts_numeric_codes():
    result = master_tables._build_allowed_values(
        [{"codigo": 10, "nombre": "Activo"}],
        "codigo",
        "nombre",
        "estados",
    )

    assert result[0].code == "10"


def test_build_allowed_values_adds_additional_values_first():
    additional = [
        AllowedValue(code="0", label="No aplica")
    ]

    result = master_tables._build_allowed_values(
        [{"codigo": "1", "nombre": "Activo"}],
        "codigo",
        "nombre",
        "estados",
        additional,
    )

    assert result == [
        AllowedValue(code="0", label="No aplica"),
        AllowedValue(code="1", label="Activo"),
    ]


def test_build_allowed_values_rejects_non_dictionary_record():
    with pytest.raises(ValueError, match="Registro 1 inválido"):
        master_tables._build_allowed_values(
            ["registro inválido"],
            "codigo",
            "nombre",
            "estados",
        )


@pytest.mark.parametrize(
    "record",
    [
        {"codigo": None, "nombre": "Activo"},
        {"codigo": "1", "nombre": None},
        {},
    ],
)
def test_build_allowed_values_rejects_missing_fields(record):
    with pytest.raises(ValueError, match="no contiene"):
        master_tables._build_allowed_values(
            [record],
            "codigo",
            "nombre",
            "estados",
        )


@pytest.mark.parametrize(
    "record",
    [
        {"codigo": "", "nombre": "Activo"},
        {"codigo": " ", "nombre": "Activo"},
        {"codigo": "1", "nombre": ""},
        {"codigo": "1", "nombre": "   "},
    ],
)
def test_build_allowed_values_rejects_empty_fields(record):
    with pytest.raises(ValueError, match="vacíos"):
        master_tables._build_allowed_values(
            [record],
            "codigo",
            "nombre",
            "estados",
        )


def test_build_allowed_values_rejects_duplicate_codes():
    records = [
        {"codigo": "1", "nombre": "Activo"},
        {"codigo": "1", "nombre": "Otro"},
    ]

    with pytest.raises(ValueError, match="duplicado"):
        master_tables._build_allowed_values(
            records,
            "codigo",
            "nombre",
            "estados",
        )


def test_build_allowed_values_rejects_duplicate_additional_codes():
    additional = [
        AllowedValue(code="0", label="No aplica"),
        AllowedValue(code="0", label="Otro"),
    ]

    with pytest.raises(ValueError, match="duplicado"):
        master_tables._build_allowed_values(
            [],
            "codigo",
            "nombre",
            "estados",
            additional,
        )


def test_build_allowed_values_rejects_duplicate_between_additional_and_records():
    additional = [
        AllowedValue(code="1", label="No aplica")
    ]

    records = [
        {"codigo": "1", "nombre": "Activo"}
    ]

    with pytest.raises(ValueError, match="duplicado"):
        master_tables._build_allowed_values(
            records,
            "codigo",
            "nombre",
            "estados",
            additional,
        )


def test_build_allowed_values_rejects_empty_catalog():
    with pytest.raises(ValueError, match="no contiene valores permitidos"):
        master_tables._build_allowed_values(
            [],
            "codigo",
            "nombre",
            "estados",
        )


def test_build_allowed_values_rejects_empty_additional_value():
    additional = [
        AllowedValue(code=" ", label="No aplica")
    ]

    with pytest.raises(ValueError, match="Valor adicional inválido"):
        master_tables._build_allowed_values(
            [],
            "codigo",
            "nombre",
            "estados",
            additional,
        )


# ============================================================
# _load_paises
# ============================================================

def test_load_paises_returns_allowed_values(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "Tabla_paises_SNIES.yaml",
        {
            "master_tables": {
                "paises": {
                    "records": [
                        {
                            "ID_PAIS": "170",
                            "DESC_PAIS": "Colombia",
                        },
                        {
                            "ID_PAIS": "840",
                            "DESC_PAIS": "Estados Unidos",
                        },
                    ]
                }
            }
        },
    )

    result = master_tables._load_paises()

    assert result == [
        AllowedValue(
            code="0",
            label="No Aplica (Organismo Multilateral)",
        ),
        AllowedValue(code="170", label="Colombia"),
        AllowedValue(code="840", label="Estados Unidos"),
    ]


def test_load_paises_requires_master_tables_section(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "Tabla_paises_SNIES.yaml",
        {"paises": {}},
    )

    with pytest.raises(ValueError, match="master_tables"):
        master_tables._load_paises()


def test_load_paises_requires_paises_table(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "Tabla_paises_SNIES.yaml",
        {"master_tables": {}},
    )

    with pytest.raises(ValueError, match="tabla 'paises'"):
        master_tables._load_paises()


def test_load_paises_requires_records_list(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "Tabla_paises_SNIES.yaml",
        {
            "master_tables": {
                "paises": {
                    "records": {}
                }
            }
        },
    )

    with pytest.raises(ValueError, match="lista de registros"):
        master_tables._load_paises()


def test_load_paises_rejects_duplicate_reserved_code(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "Tabla_paises_SNIES.yaml",
        {
            "master_tables": {
                "paises": {
                    "records": [
                        {
                            "ID_PAIS": "0",
                            "DESC_PAIS": "Otro",
                        }
                    ]
                }
            }
        },
    )

    with pytest.raises(ValueError, match="duplicado"):
        master_tables._load_paises()


# ============================================================
# _load_cine_campo_detallado
# ============================================================

def test_load_cine_campo_detallado_returns_allowed_values(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "cine_campo_detallado.yaml",
        {
            "records": [
                {
                    "codigo": "0111",
                    "descripcion": "Ciencias naturales",
                },
                {
                    "codigo": "0112",
                    "descripcion": "Matemáticas",
                },
            ]
        },
    )

    result = master_tables._load_cine_campo_detallado()

    assert result == [
        AllowedValue(
            code="0111",
            label="Ciencias naturales",
        ),
        AllowedValue(
            code="0112",
            label="Matemáticas",
        ),
    ]


def test_load_cine_requires_records_list(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "cine_campo_detallado.yaml",
        {"records": {}},
    )

    with pytest.raises(ValueError, match="lista de registros"):
        master_tables._load_cine_campo_detallado()


def test_load_cine_rejects_missing_records(catalogs_dir):
    write_yaml(
        catalogs_dir,
        "cine_campo_detallado.yaml",
        {"catalogo": []},
    )

    with pytest.raises(ValueError, match="lista de registros"):
        master_tables._load_cine_campo_detallado()


# ============================================================
# apply_master_table_reference
# ============================================================

# ============================================================
# apply_master_table_reference
# ============================================================

@pytest.mark.parametrize(
    "comment",
    [
        "Lista de países según el estándar.",
        "Seleccione un país de la lista de paises.",
        "Código según ISO 3166.",
        "Código ISO3166.",
    ],
)
def test_apply_reference_detects_country_catalog(comment, monkeypatch):
    expected = [
        AllowedValue(code="170", label="Colombia")
    ]

    monkeypatch.setitem(
        master_tables._LOADERS,
        "paises",
        lambda: expected,
    )

    rule = make_rule()

    result = master_tables.apply_master_table_reference(
        rule,
        comment,
    )

    assert result is rule
    assert rule.allowed_values == expected


@pytest.mark.parametrize(
    "comment",
    [
        "Clasificación CINE Campo Detallado.",
        "Clasificacion CINE para el programa.",
    ],
)
def test_apply_reference_detects_cine_catalog(comment, monkeypatch):
    expected = [
        AllowedValue(
            code="0111",
            label="Ciencias naturales",
        )
    ]

    monkeypatch.setitem(
        master_tables._LOADERS,
        "cine_campo_detallado",
        lambda: expected,
    )

    rule = make_rule()

    result = master_tables.apply_master_table_reference(
        rule,
        comment,
    )

    assert result is rule
    assert rule.allowed_values == expected


def test_apply_reference_does_not_change_rule_without_match():
    rule = make_rule()

    result = master_tables.apply_master_table_reference(
        rule,
        "Ingrese el nombre de la institución.",
    )

    assert result is rule
    assert rule.allowed_values == []


@pytest.mark.parametrize(
    "comment",
    [None, ""],
)
def test_apply_reference_accepts_empty_comment(comment):
    rule = make_rule()

    result = master_tables.apply_master_table_reference(
        rule,
        comment,
    )

    assert result is rule
    assert rule.allowed_values == []


def test_apply_reference_preserves_existing_allowed_values(monkeypatch):
    existing = [
        AllowedValue(code="X", label="Valor propio")
    ]

    def loader_must_not_run():
        raise AssertionError("El catálogo no debería cargarse")

    monkeypatch.setitem(
        master_tables._LOADERS,
        "paises",
        loader_must_not_run,
    )

    rule = make_rule(existing)

    result = master_tables.apply_master_table_reference(
        rule,
        "Lista de países ISO 3166.",
    )

    assert result is rule
    assert rule.allowed_values == existing


def test_apply_reference_propagates_catalog_loading_error(monkeypatch):
    def failing_loader():
        raise FileNotFoundError("Catálogo no encontrado")

    monkeypatch.setitem(
        master_tables._LOADERS,
        "paises",
        failing_loader,
    )

    rule = make_rule()

    with pytest.raises(
        FileNotFoundError,
        match="Catálogo no encontrado",
    ):
        master_tables.apply_master_table_reference(
            rule,
            "Lista de países ISO 3166.",
        )


def test_apply_reference_raises_when_loader_is_missing(monkeypatch):
    monkeypatch.setattr(
        master_tables,
        "_TRIGGER_PATTERNS",
        [
            (
                master_tables.re.compile(
                    r"referencia especial",
                    master_tables.re.IGNORECASE,
                ),
                "catalogo_inexistente",
            )
        ],
    )

    rule = make_rule()

    with pytest.raises(ValueError, match="No existe un cargador"):
        master_tables.apply_master_table_reference(
            rule,
            "Referencia especial.",
        )


def test_apply_reference_stops_after_first_matching_pattern(monkeypatch):
    paises = [
        AllowedValue(code="170", label="Colombia")
    ]

    def paises_loader():
        return paises

    def cine_loader_must_not_run():
        raise AssertionError("Solo debe cargarse el primer catálogo")

    monkeypatch.setitem(
        master_tables._LOADERS,
        "paises",
        paises_loader,
    )

    monkeypatch.setitem(
        master_tables._LOADERS,
        "cine_campo_detallado",
        cine_loader_must_not_run,
    )

    rule = make_rule()

    master_tables.apply_master_table_reference(
        rule,
        "Lista de países e información de clasificación CINE.",
    )

    assert rule.allowed_values == paises