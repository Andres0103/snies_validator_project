import pytest
import yaml

from datetime import date, datetime
from pathlib import Path

from rules.catalog_loader import (
    _read_yaml,
    _resolve_records,
    _parse_date,
    _is_active,
    _validate_catalog_config,
    _append_additional_values,
    _load_catalog_cached,
    load_catalog,
)
from rules.general_model import AllowedValue


@pytest.fixture
def catalog_environment(tmp_path, monkeypatch):
    import rules.catalog_loader as loader

    monkeypatch.setattr(loader, "PROJECT_DIR", tmp_path)
    loader._load_catalog_cached.cache_clear()

    yield tmp_path

    loader._load_catalog_cached.cache_clear()


def create_catalog(base_path, relative_path, data):
    path = base_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True),
        encoding="utf-8",
    )

    return path


def valid_config(file="catalogos/estados.yaml"):
    return {
        "file": file,
        "key_column": "codigo",
        "description_column": "nombre",
    }


# ============================================================
# _read_yaml
# ============================================================

def test_read_yaml_returns_dictionary(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("nombre: Colombia\n", encoding="utf-8")

    assert _read_yaml(path) == {"nombre": "Colombia"}


def test_read_yaml_returns_list(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("- Colombia\n- Perú\n", encoding="utf-8")

    assert _read_yaml(path) == ["Colombia", "Perú"]


def test_read_yaml_returns_none_for_empty_file(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("", encoding="utf-8")

    assert _read_yaml(path) is None


def test_read_yaml_raises_when_file_does_not_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        _read_yaml(tmp_path / "missing.yaml")


def test_read_yaml_raises_when_path_is_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        _read_yaml(tmp_path)


def test_read_yaml_raises_for_invalid_yaml(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("nombre: [Colombia\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML inválido"):
        _read_yaml(path)


# ============================================================
# _resolve_records
# ============================================================

def test_resolve_records_accepts_direct_list():
    records = [{"codigo": "1", "nombre": "Activo"}]

    assert _resolve_records(records, None) == records


def test_resolve_records_uses_records_key():
    data = {
        "records": [{"codigo": "1", "nombre": "Activo"}]
    }

    assert _resolve_records(data, None) == data["records"]


def test_resolve_records_uses_values_key():
    data = {
        "values": [{"codigo": "1", "nombre": "Activo"}]
    }

    assert _resolve_records(data, None) == data["values"]


def test_resolve_records_uses_data_key():
    data = {
        "data": [{"codigo": "1", "nombre": "Activo"}]
    }

    assert _resolve_records(data, None) == data["data"]


def test_resolve_records_prioritizes_records_key():
    data = {
        "records": [{"codigo": "1", "nombre": "Activo"}],
        "values": [{"codigo": "2", "nombre": "Inactivo"}],
    }

    assert _resolve_records(data, None) == data["records"]


def test_resolve_records_supports_nested_path():
    data = {
        "master_tables": {
            "paises": {
                "records": [
                    {"codigo": "CO", "nombre": "Colombia"}
                ]
            }
        }
    }

    result = _resolve_records(
        data,
        "master_tables.paises.records",
    )

    assert result == [
        {"codigo": "CO", "nombre": "Colombia"}
    ]


def test_resolve_records_rejects_non_string_path():
    with pytest.raises(ValueError, match="records_path"):
        _resolve_records({}, 123)


def test_resolve_records_rejects_missing_path_key():
    with pytest.raises(ValueError, match="No existe la clave"):
        _resolve_records(
            {"records": []},
            "master_tables.paises",
        )


def test_resolve_records_rejects_invalid_intermediate_path():
    with pytest.raises(ValueError, match="No se puede resolver"):
        _resolve_records(
            {"master_tables": []},
            "master_tables.paises.records",
        )


@pytest.mark.parametrize(
    "data",
    [
        None,
        "texto",
        123,
        {},
        {"records": "no es una lista"},
    ],
)
def test_resolve_records_rejects_invalid_records_location(data):
    with pytest.raises(ValueError, match="lista de registros"):
        _resolve_records(data, None)


# ============================================================
# _parse_date
# ============================================================

def test_parse_date_accepts_date():
    value = date(2025, 1, 15)

    assert _parse_date(value, "catalogo", 1) == value


def test_parse_date_accepts_datetime():
    value = datetime(2025, 1, 15, 10, 30)

    assert _parse_date(value, "catalogo", 1) == date(2025, 1, 15)


@pytest.mark.parametrize(
    "value",
    [
        "15/01/2025",
        "2025-01-15",
        "15-01-2025",
    ],
)
def test_parse_date_accepts_supported_formats(value):
    assert _parse_date(
        value,
        "catalogo",
        1,
    ) == date(2025, 1, 15)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_parse_date_returns_none_for_empty_values(value):
    assert _parse_date(value, "catalogo", 1) is None


def test_parse_date_rejects_invalid_format():
    with pytest.raises(ValueError, match="formato reconocido"):
        _parse_date("2025/01/15", "catalogo", 1)


def test_parse_date_rejects_impossible_date():
    with pytest.raises(ValueError, match="formato reconocido"):
        _parse_date("31/02/2025", "catalogo", 1)


@pytest.mark.parametrize("value", [123, True, 12.5])
def test_parse_date_rejects_non_string_non_date_values(value):
    with pytest.raises(ValueError, match="Fecha inválida"):
        _parse_date(value, "catalogo", 1)


# ============================================================
# _is_active
# ============================================================

def test_is_active_returns_true_without_date_column():
    assert _is_active(
        {"fecha_fin": "2020-01-01"},
        None,
        date(2025, 1, 1),
        "catalogo",
        1,
    ) is True


def test_is_active_returns_true_when_end_date_is_empty():
    assert _is_active(
        {"fecha_fin": None},
        "fecha_fin",
        date(2025, 1, 1),
        "catalogo",
        1,
    ) is True


def test_is_active_returns_true_when_end_date_is_future():
    assert _is_active(
        {"fecha_fin": "2025-12-31"},
        "fecha_fin",
        date(2025, 1, 1),
        "catalogo",
        1,
    ) is True


def test_is_active_returns_true_when_end_date_equals_query_date():
    assert _is_active(
        {"fecha_fin": "2025-01-01"},
        "fecha_fin",
        date(2025, 1, 1),
        "catalogo",
        1,
    ) is True


def test_is_active_returns_false_when_end_date_is_past():
    assert _is_active(
        {"fecha_fin": "2024-12-31"},
        "fecha_fin",
        date(2025, 1, 1),
        "catalogo",
        1,
    ) is False


def test_is_active_rejects_invalid_end_date():
    with pytest.raises(ValueError):
        _is_active(
            {"fecha_fin": "fecha incorrecta"},
            "fecha_fin",
            date(2025, 1, 1),
            "catalogo",
            1,
        )


# ============================================================
# _validate_catalog_config
# ============================================================

def test_validate_catalog_config_accepts_valid_configuration():
    _validate_catalog_config(valid_config(), "estados")


@pytest.mark.parametrize(
    "config",
    [
        None,
        [],
        "texto",
        123,
    ],
)
def test_validate_catalog_config_rejects_non_dictionary(config):
    with pytest.raises(ValueError, match="diccionario"):
        _validate_catalog_config(config, "estados")


@pytest.mark.parametrize(
    "key",
    ["file", "key_column", "description_column"],
)
def test_validate_catalog_config_requires_mandatory_keys(key):
    config = valid_config()
    del config[key]

    with pytest.raises(ValueError, match=key):
        _validate_catalog_config(config, "estados")


@pytest.mark.parametrize(
    "key",
    ["file", "key_column", "description_column"],
)
def test_validate_catalog_config_rejects_empty_mandatory_values(key):
    config = valid_config()
    config[key] = "   "

    with pytest.raises(ValueError, match=key):
        _validate_catalog_config(config, "estados")


@pytest.mark.parametrize(
    "value",
    [123, [], {}, ""],
)
def test_validate_catalog_config_rejects_invalid_records_path(value):
    config = valid_config()
    config["records_path"] = value

    with pytest.raises(ValueError, match="records_path"):
        _validate_catalog_config(config, "estados")


@pytest.mark.parametrize(
    "value",
    [123, [], {}, ""],
)
def test_validate_catalog_config_rejects_invalid_active_date_column(value):
    config = valid_config()
    config["active_date_column"] = value

    with pytest.raises(ValueError, match="active_date_column"):
        _validate_catalog_config(config, "estados")


# ============================================================
# _append_additional_values
# ============================================================

def test_append_additional_values_adds_valid_values():
    values = [
        AllowedValue(code="1", label="Activo")
    ]

    _append_additional_values(
        values,
        [{"code": "2", "label": "Inactivo"}],
        "estados",
    )

    assert values == [
        AllowedValue(code="1", label="Activo"),
        AllowedValue(code="2", label="Inactivo"),
    ]


def test_append_additional_values_accepts_none():
    values = [AllowedValue(code="1", label="Activo")]

    _append_additional_values(values, None, "estados")

    assert len(values) == 1


def test_append_additional_values_rejects_non_list():
    with pytest.raises(ValueError, match="debe ser una lista"):
        _append_additional_values([], {}, "estados")


def test_append_additional_values_rejects_non_dictionary_item():
    values = [
        AllowedValue(code="1", label="Activo")
    ]

    with pytest.raises(ValueError, match="debe ser un diccionario"):
        _append_additional_values(
            values,
            ["invalido"],
            "estados",
        )


@pytest.mark.parametrize(
    "item",
    [
        {"code": "2"},
        {"label": "Inactivo"},
        {},
    ],
)
def test_append_additional_values_requires_code_and_label(item):
    with pytest.raises(ValueError, match="code"):
        _append_additional_values([], [item], "estados")


@pytest.mark.parametrize(
    "item",
    [
        {"code": "", "label": "Inactivo"},
        {"code": "2", "label": ""},
        {"code": " ", "label": "Inactivo"},
        {"code": "2", "label": "   "},
    ],
)
def test_append_additional_values_rejects_empty_fields(item):
    with pytest.raises(ValueError, match="vacíos"):
        _append_additional_values([], [item], "estados")


def test_append_additional_values_rejects_duplicate_existing_code():
    values = [AllowedValue(code="1", label="Activo")]

    with pytest.raises(ValueError, match="duplicado"):
        _append_additional_values(
            values,
            [{"code": "1", "label": "Otro"}],
            "estados",
        )


def test_append_additional_values_rejects_duplicate_additional_codes():
    values = []

    with pytest.raises(ValueError, match="duplicado"):
        _append_additional_values(
            values,
            [
                {"code": "2", "label": "Inactivo"},
                {"code": "2", "label": "Otro"},
            ],
            "estados",
        )


def test_append_additional_values_trims_code_and_label():
    values = []

    _append_additional_values(
        values,
        [{"code": " 2 ", "label": " Inactivo "}],
        "estados",
    )

    assert values == [
        AllowedValue(code="2", label="Inactivo")
    ]


# ============================================================
# load_catalog
# ============================================================

def test_load_catalog_returns_allowed_values(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {"codigo": "1", "nombre": "Activo"},
            {"codigo": "2", "nombre": "Inactivo"},
        ],
    )

    result = load_catalog(
        valid_config(),
        "estados",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="1", label="Activo"),
        AllowedValue(code="2", label="Inactivo"),
    ]


def test_load_catalog_supports_nested_records_path(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/paises.yaml",
        {
            "master_tables": {
                "paises": {
                    "records": [
                        {"codigo": "CO", "nombre": "Colombia"}
                    ]
                }
            }
        },
    )

    config = valid_config("catalogos/paises.yaml")
    config["records_path"] = "master_tables.paises.records"

    result = load_catalog(
        config,
        "paises",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="CO", label="Colombia")
    ]


def test_load_catalog_filters_inactive_records(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {
                "codigo": "1",
                "nombre": "Activo",
                "fecha_fin": "2025-12-31",
            },
            {
                "codigo": "2",
                "nombre": "Vencido",
                "fecha_fin": "2024-12-31",
            },
        ],
    )

    config = valid_config()
    config["active_date_column"] = "fecha_fin"

    result = load_catalog(
        config,
        "estados",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="1", label="Activo")
    ]


def test_load_catalog_keeps_records_without_end_date(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {
                "codigo": "1",
                "nombre": "Activo",
                "fecha_fin": None,
            }
        ],
    )

    config = valid_config()
    config["active_date_column"] = "fecha_fin"

    result = load_catalog(
        config,
        "estados",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="1", label="Activo")
    ]


def test_load_catalog_adds_additional_values(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": "Activo"}],
    )

    config = valid_config()
    config["additional_values"] = [
        {"code": "2", "label": "No aplica"}
    ]

    result = load_catalog(
        config,
        "estados",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="1", label="Activo"),
        AllowedValue(code="2", label="No aplica"),
    ]


def test_load_catalog_rejects_duplicate_codes(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {"codigo": "1", "nombre": "Activo"},
            {"codigo": "1", "nombre": "Otro"},
        ],
    )

    with pytest.raises(ValueError, match="duplicado"):
        load_catalog(
            valid_config(),
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_rejects_incomplete_active_record(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": None}],
    )

    with pytest.raises(ValueError, match="no contiene"):
        load_catalog(
            valid_config(),
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_ignores_incomplete_inactive_record(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {
                "codigo": None,
                "nombre": None,
                "fecha_fin": "2024-01-01",
            },
            {
                "codigo": "1",
                "nombre": "Activo",
                "fecha_fin": None,
            },
        ],
    )

    config = valid_config()
    config["active_date_column"] = "fecha_fin"

    result = load_catalog(
        config,
        "estados",
        date(2025, 1, 1),
    )

    assert result == [
        AllowedValue(code="1", label="Activo")
    ]


def test_load_catalog_rejects_empty_code_or_label(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": " ", "nombre": "Activo"}],
    )

    with pytest.raises(ValueError, match="vacíos"):
        load_catalog(
            valid_config(),
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_rejects_empty_catalog(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [],
    )

    with pytest.raises(ValueError, match="no contiene"):
        load_catalog(
            valid_config(),
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_rejects_invalid_record_type(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        ["registro inválido"],
    )

    with pytest.raises(ValueError, match="debe ser un diccionario"):
        load_catalog(
            valid_config(),
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_rejects_invalid_as_of_date_type(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": "Activo"}],
    )

    with pytest.raises(ValueError, match="as_of_date"):
        load_catalog(
            valid_config(),
            "estados",
            "2025-01-01",
        )


def test_load_catalog_accepts_datetime_as_of_date(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": "Activo"}],
    )

    result = load_catalog(
        valid_config(),
        "estados",
        datetime(2025, 1, 1, 10, 30),
    )

    assert result == [
        AllowedValue(code="1", label="Activo")
    ]


def test_load_catalog_rejects_path_outside_project(catalog_environment):
    outside_file = catalog_environment.parent / "outside.yaml"
    outside_file.write_text(
        "- codigo: '1'\n  nombre: Activo\n",
        encoding="utf-8",
    )

    config = valid_config("../outside.yaml")

    with pytest.raises(ValueError, match="dentro del proyecto"):
        load_catalog(
            config,
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_rejects_duplicate_additional_code(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": "Activo"}],
    )

    config = valid_config()
    config["additional_values"] = [
        {"code": "1", "label": "Otro"}
    ]

    with pytest.raises(ValueError, match="duplicado"):
        load_catalog(
            config,
            "estados",
            date(2025, 1, 1),
        )


def test_load_catalog_does_not_expose_cached_tuple(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [{"codigo": "1", "nombre": "Activo"}],
    )

    first = load_catalog(
        valid_config(),
        "estados",
        date(2025, 1, 1),
    )

    first.append(AllowedValue(code="2", label="Temporal"))

    second = load_catalog(
        valid_config(),
        "estados",
        date(2025, 1, 1),
    )

    assert second == [
        AllowedValue(code="1", label="Activo")
    ]


def test_load_catalog_cache_is_separated_by_query_date(catalog_environment):
    create_catalog(
        catalog_environment,
        "catalogos/estados.yaml",
        [
            {
                "codigo": "1",
                "nombre": "Activo",
                "fecha_fin": "2025-06-30",
            }
        ],
    )

    config = valid_config()
    config["active_date_column"] = "fecha_fin"

    active = load_catalog(
        config,
        "estados",
        date(2025, 1, 1),
    )

    expired = None

    with pytest.raises(ValueError, match="no contiene"):
        expired = load_catalog(
            config,
            "estados",
            date(2025, 7, 1),
        )

    assert active == [
        AllowedValue(code="1", label="Activo")
    ]
    assert expired is None