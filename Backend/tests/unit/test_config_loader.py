
from pathlib import Path

import pytest
import yaml

from rules.config_loader import (
    RuleConfiguration,
    _merge_dicts,
    load_yaml_file,
    load_rule_configuration,
    load_config,
)


def write_yaml(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            content,
            file,
            allow_unicode=True,
            sort_keys=False,
        )


def create_template_configuration(tmp_path):
    rules_dir = tmp_path / "patterns"
    template_dir = rules_dir / "templates" / "consultoria"

    write_yaml(
        rules_dir / "known_fields.yaml",
        {"CAMPO_GLOBAL": {"datatype": "TEXT"}},
    )

    write_yaml(
        rules_dir / "template_profiles.yaml",
        {
            "templates": {
                "consultoria": {
                    "main_sheet": "CONSULTORIA",
                    "sheets": ["CONSULTORIA", "DETALLE"],
                }
            }
        },
    )

    write_yaml(
        rules_dir / "common" / "rules.yaml",
        {
            "sheets": {
                "CONSULTORIA": {
                    "CAMPO_COMUN": {"required": True}
                }
            }
        },
    )

    write_yaml(
        rules_dir / "common" / "validations.yaml",
        {},
    )

    write_yaml(
        rules_dir / "common" / "catalogs.yaml",
        {},
    )

    write_yaml(
        rules_dir / "common" / "business_rules.yaml",
        {
            "CAMPO_GLOBAL": {
                "kind": "non_negative"
            }
        },
    )

    write_yaml(
        template_dir / "rules.yaml",
        {
            "sheets": {
                "CONSULTORIA": {
                    "CAMPO_ESPECIFICO": {"required": False}
                }
            }
        },
    )

    write_yaml(template_dir / "validations.yaml", {})
    write_yaml(template_dir / "catalogs.yaml", {})
    write_yaml(template_dir / "business_rules.yaml", {})

    return rules_dir


# ============================================================
# load_yaml_file
# ============================================================

def test_load_yaml_file_returns_empty_dict_when_file_does_not_exist(
    tmp_path,
):
    result = load_yaml_file(tmp_path / "inexistente.yaml")

    assert result == {}


def test_load_yaml_file_returns_empty_dict_when_file_is_empty(
    tmp_path,
):
    file_path = tmp_path / "empty.yaml"
    file_path.write_text("", encoding="utf-8")

    result = load_yaml_file(file_path)

    assert result == {}


def test_load_yaml_file_loads_valid_dictionary(tmp_path):
    file_path = tmp_path / "valid.yaml"

    write_yaml(
        file_path,
        {"campo": {"required": True}},
    )

    result = load_yaml_file(file_path)

    assert result == {"campo": {"required": True}}


def test_load_yaml_file_supports_unicode_content(tmp_path):
    file_path = tmp_path / "unicode.yaml"

    write_yaml(
        file_path,
        {"descripción": "Validación de información académica"},
    )

    result = load_yaml_file(file_path)

    assert result["descripción"] == (
        "Validación de información académica"
    )


def test_load_yaml_file_rejects_invalid_yaml(tmp_path):
    file_path = tmp_path / "invalid.yaml"
    file_path.write_text(
        "campo: [valor1, valor2",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="YAML inválido"):
        load_yaml_file(file_path)


@pytest.mark.parametrize(
    "content",
    [
        ["uno", "dos"],
        "texto",
        123,
        True,
    ],
)
def test_load_yaml_file_rejects_non_dictionary_content(
    tmp_path,
    content,
):
    file_path = tmp_path / "invalid_structure.yaml"

    file_path.write_text(
        yaml.safe_dump(content),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="diccionario"):
        load_yaml_file(file_path)


def test_load_yaml_file_rejects_directory_instead_of_file(
    tmp_path,
):
    directory = tmp_path / "config.yaml"
    directory.mkdir()

    with pytest.raises(ValueError, match="no es un archivo"):
        load_yaml_file(directory)


# ============================================================
# _merge_dicts
# ============================================================

def test_merge_dicts_combines_nested_dictionaries():
    base = {
        "campo": {
            "required": True,
            "datatype": "TEXT",
        }
    }

    override = {
        "campo": {
            "datatype": "INTEGER",
        }
    }

    result = _merge_dicts(base, override)

    assert result == {
        "campo": {
            "required": True,
            "datatype": "INTEGER",
        }
    }


def test_merge_dicts_override_has_priority():
    base = {"campo": "valor_comun"}
    override = {"campo": "valor_especifico"}

    result = _merge_dicts(base, override)

    assert result["campo"] == "valor_especifico"


def test_merge_dicts_replaces_lists_completely():
    base = {"campos": ["A", "B"]}
    override = {"campos": ["C"]}

    result = _merge_dicts(base, override)

    assert result["campos"] == ["C"]


def test_merge_dicts_does_not_modify_original_dictionaries():
    base = {
        "campo": {
            "required": True,
        }
    }

    override = {
        "campo": {
            "datatype": "TEXT",
        }
    }

    original_base = {
        "campo": {
            "required": True,
        }
    }

    original_override = {
        "campo": {
            "datatype": "TEXT",
        }
    }

    _merge_dicts(base, override)

    assert base == original_base
    assert override == original_override


# ============================================================
# load_rule_configuration: arquitectura anterior
# ============================================================

def test_load_rule_configuration_without_template_uses_legacy(
    tmp_path,
):
    write_yaml(
        tmp_path / "known_fields.yaml",
        {"CODIGO": {"datatype": "TEXT"}},
    )

    write_yaml(
        tmp_path / "business_rules.yaml",
        {"VALOR": {"kind": "non_negative"}},
    )

    write_yaml(
        tmp_path / "validation_rules.yaml",
        {"validation_config": {"enabled": True}},
    )

    result = load_rule_configuration(rules_dir=tmp_path)

    assert isinstance(result, RuleConfiguration)
    assert result.known_fields["CODIGO"]["datatype"] == "TEXT"
    assert result.business_rules["VALOR"]["kind"] == "non_negative"
    assert result.validation_config["enabled"] is True


def test_load_config_is_compatibility_alias(tmp_path):
    write_yaml(
        tmp_path / "known_fields.yaml",
        {"CODIGO": {"datatype": "TEXT"}},
    )

    result = load_config(rules_dir=tmp_path)

    assert isinstance(result, RuleConfiguration)
    assert result.known_fields["CODIGO"]["datatype"] == "TEXT"


# ============================================================
# load_rule_configuration: arquitectura nueva
# ============================================================

def test_load_rule_configuration_loads_template_successfully(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    result = load_rule_configuration(
        template_name="consultoria",
        rules_dir=rules_dir,
    )

    assert isinstance(result, RuleConfiguration)
    assert result.template_name == "consultoria"
    assert result.template_profile["main_sheet"] == "CONSULTORIA"

    assert "CONSULTORIA" in result.sheet_configurations
    assert "DETALLE" in result.sheet_configurations


def test_template_specific_rules_override_common_rules(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    result = load_rule_configuration(
        template_name="consultoria",
        rules_dir=rules_dir,
    )

    sheet_rules = result.sheet_configurations[
        "CONSULTORIA"
    ]["rules"]

    assert "CAMPO_COMUN" in sheet_rules
    assert "CAMPO_ESPECIFICO" in sheet_rules


def test_template_specific_business_rules_override_common(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    write_yaml(
        rules_dir / "common" / "business_rules.yaml",
        {
            "CAMPO": {
                "kind": "non_negative",
                "message": "Regla común",
            }
        },
    )

    write_yaml(
        rules_dir
        / "templates"
        / "consultoria"
        / "business_rules.yaml",
        {
            "CAMPO": {
                "message": "Regla específica",
            }
        },
    )

    result = load_rule_configuration(
        template_name="consultoria",
        rules_dir=rules_dir,
    )

    assert result.business_rules["CAMPO"] == {
        "kind": "non_negative",
        "message": "Regla específica",
    }


def test_load_rule_configuration_rejects_empty_template_name(
    tmp_path,
):
    with pytest.raises(ValueError, match="template_name"):
        load_rule_configuration(
            template_name=" ",
            rules_dir=tmp_path,
        )


def test_load_rule_configuration_rejects_non_string_template_name(
    tmp_path,
):
    with pytest.raises(ValueError, match="template_name"):
        load_rule_configuration(
            template_name=123,
            rules_dir=tmp_path,
        )


def test_load_rule_configuration_rejects_missing_template_directory(
    tmp_path,
):
    with pytest.raises(ValueError, match="No existe el directorio"):
        load_rule_configuration(
            template_name="inexistente",
            rules_dir=tmp_path,
        )


def test_load_rule_configuration_rejects_missing_template_profile(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    write_yaml(
        rules_dir / "template_profiles.yaml",
        {"templates": {}},
    )

    with pytest.raises(ValueError, match="No existe un perfil"):
        load_rule_configuration(
            template_name="consultoria",
            rules_dir=rules_dir,
        )


def test_load_rule_configuration_rejects_invalid_main_sheet(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    write_yaml(
        rules_dir / "template_profiles.yaml",
        {
            "templates": {
                "consultoria": {
                    "main_sheet": "",
                    "sheets": ["CONSULTORIA"],
                }
            }
        },
    )

    with pytest.raises(ValueError, match="hoja principal"):
        load_rule_configuration(
            template_name="consultoria",
            rules_dir=rules_dir,
        )


def test_load_rule_configuration_rejects_catalog_not_defined(
    tmp_path,
):
    rules_dir = create_template_configuration(tmp_path)

    write_yaml(
        rules_dir
        / "templates"
        / "consultoria"
        / "validations.yaml",
        {
            "sheets": {
                "CONSULTORIA": {
                    "CODIGO": {
                        "catalog": "CATALOGO_INEXISTENTE"
                    }
                }
            }
        },
    )

    with pytest.raises(ValueError, match="no está definido"):
        load_rule_configuration(
            template_name="consultoria",
            rules_dir=rules_dir,
        )
