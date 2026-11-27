
import pytest

from rules.template_profiles import (
    _validate_profiles,
    load_template_profiles,
    detect_templates,
)


def valid_profile():
    return {
        "main_sheet": "PRINCIPAL",
        "sheets": ["PRINCIPAL", "DETALLE"],
        "record_key": ["CODIGO"],
        "references": [
            {
                "child_sheet": "DETALLE",
                "parent_sheet": "PRINCIPAL",
                "key": ["CODIGO"],
            }
        ],
    }


def valid_configuration():
    return {
        "templates": {
            "plantilla_a": valid_profile()
        }
    }


def test_load_template_profiles_returns_valid_configuration():
    profiles = load_template_profiles()

    assert "templates" in profiles
    assert isinstance(profiles["templates"], dict)
    assert profiles["templates"]


def test_valid_profile_is_accepted():
    _validate_profiles(valid_configuration())


def test_missing_main_sheet_is_rejected():
    profile = valid_profile()
    profile.pop("main_sheet")

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_main_sheet_not_declared_in_sheets_is_rejected():
    profile = valid_profile()
    profile["main_sheet"] = "INEXISTENTE"

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_empty_sheets_list_is_rejected():
    profile = valid_profile()
    profile["sheets"] = []

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_duplicate_sheet_names_are_rejected():
    profile = valid_profile()
    profile["sheets"] = [
        "PRINCIPAL",
        "principal",
    ]

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_empty_record_key_is_rejected():
    profile = valid_profile()
    profile["record_key"] = []

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_reference_to_undeclared_child_sheet_is_rejected():
    profile = valid_profile()
    profile["references"][0]["child_sheet"] = "INEXISTENTE"

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_reference_to_undeclared_parent_sheet_is_rejected():
    profile = valid_profile()
    profile["references"][0]["parent_sheet"] = "INEXISTENTE"

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_reference_between_same_sheet_is_rejected():
    profile = valid_profile()
    profile["references"][0]["parent_sheet"] = "DETALLE"

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_duplicate_references_are_rejected():
    profile = valid_profile()
    profile["references"].append(
        profile["references"][0].copy()
    )

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {"plantilla_a": profile}
        })


def test_duplicate_main_sheets_between_templates_are_rejected():
    profile_a = valid_profile()
    profile_b = valid_profile()
    profile_b["sheets"] = ["PRINCIPAL", "OTRA"]
    profile_b["main_sheet"] = "PRINCIPAL"

    with pytest.raises(ValueError):
        _validate_profiles({
            "templates": {
                "plantilla_a": profile_a,
                "plantilla_b": profile_b,
            }
        })


def test_empty_templates_configuration_is_rejected():
    with pytest.raises(ValueError):
        _validate_profiles({"templates": {}})


def test_detect_templates_rejects_non_list_argument():
    with pytest.raises(TypeError):
        detect_templates("CONSULTORIA")


def test_detect_templates_rejects_non_string_sheet_names():
    with pytest.raises(ValueError):
        detect_templates(["CONSULTORIA", 123])
