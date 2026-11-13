from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from excel import writer
from excel.reader import HeaderCell
from rules.general_model import (
    AllowedValue,
    DataType,
    ValidationRule,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def rule():
    return ValidationRule(
        column_name="CODIGO",
        datatype=DataType.TEXT,
    )


@pytest.fixture
def workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "CONSULTORIA"
    ws.append(["CODIGO", "NOMBRE"])
    return wb


@pytest.fixture
def configuration():
    return SimpleNamespace(
        known_fields={},
        sheet_configurations={},
        validation_config={},
    )


def make_header(
    sheet_name="CONSULTORIA",
    column_name="CODIGO",
    column_letter="A",
):
    return HeaderCell(
        sheet_name=sheet_name,
        column_name=column_name,
        column_letter=column_letter,
        comment_text=None,
        cell=Mock(),
    )


# ============================================================
# CONFIGURACIÓN DE ARQUITECTURA
# ============================================================



# ============================================================
# CONFIGURACIÓN POR HOJA
# ============================================================

class TestGetSheetConfiguration:

    def test_returns_matching_sheet_configuration(self):
        config = SimpleNamespace(
            sheet_configurations={
                "CONSULTORIA": {
                    "rules": {"CODIGO": {}},
                    "validations": {"CODIGO": {"pattern": ".*"}},
                    "catalogs": {},
                },
                "PROYECTOS": {
                    "rules": {},
                    "validations": {},
                    "catalogs": {},
                },
            },
            validation_config={},
        )

        result = writer._get_sheet_configuration(
            config,
            "CONSULTORIA",
        )

        assert result["validations"]["CODIGO"]["pattern"] == ".*"

    def test_matches_sheet_name_without_case_sensitivity(self):
        config = SimpleNamespace(
            sheet_configurations={
                "Consultoria": {"rules": {"A": {}}},
            },
            validation_config={},
        )

        result = writer._get_sheet_configuration(
            config,
            "CONSULTORIA",
        )

        assert result["rules"] == {"A": {}}

    def test_matches_sheet_name_ignoring_outer_whitespace(self):
        config = SimpleNamespace(
            sheet_configurations={
                " CONSULTORIA ": {"rules": {"A": {}}},
            },
            validation_config={},
        )

        result = writer._get_sheet_configuration(
            config,
            "CONSULTORIA",
        )

        assert result["rules"] == {"A": {}}

    def test_raises_when_sheet_configuration_is_not_found(self):
        config = SimpleNamespace(
            sheet_configurations={
                "PROYECTOS": {
                    "rules": {},
                    "validations": {},
                    "catalogs": {},
                },
            },
        )

        with pytest.raises(
            ValueError,
            match="No existe una configuración para la hoja 'CONSULTORIA'",
        ):
            writer._get_sheet_configuration(
                config,
                "CONSULTORIA",
            )

    def test_raises_when_configuration_is_missing(self):
        config = SimpleNamespace()

        with pytest.raises(
            ValueError,
            match="No existe una configuración para la hoja 'CONSULTORIA'",
        ):
            writer._get_sheet_configuration(
                config,
                "CONSULTORIA",
            )



# ============================================================
# CATÁLOGOS CONFIGURADOS
# ============================================================

class TestApplyConfiguredCatalog:

    def test_does_nothing_when_validation_is_not_configured(self, rule):
        rule.allowed_values = []

        writer._apply_configured_catalog(
            rule,
            "CONSULTORIA",
            {},
            {},
        )

        assert rule.allowed_values == []

    def test_preserves_values_interpreted_from_comment(self, rule):
        original = [
            AllowedValue(code="1", label="Activo"),
        ]
        rule.allowed_values = original

        writer._apply_configured_catalog(
            rule,
            "CONSULTORIA",
            {"CODIGO": {}},
            {},
        )

        assert rule.allowed_values is original

    def test_does_nothing_when_catalog_is_not_declared(self, rule):
        writer._apply_configured_catalog(
            rule,
            "CONSULTORIA",
            {"CODIGO": {}},
            {},
        )

        assert rule.allowed_values == []

    def test_loads_configured_catalog(self, monkeypatch, rule):
        expected = [
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ]

        loader = Mock(return_value=expected)
        monkeypatch.setattr(writer, "load_catalog", loader)

        catalog_config = {"file": "estados.yaml"}

        writer._apply_configured_catalog(
            rule,
            "CONSULTORIA",
            {"CODIGO": {"catalog": "estados"}},
            {"estados": catalog_config},
        )

        loader.assert_called_once_with(
            catalog_config,
            "estados",
        )
        assert rule.allowed_values == expected

    def test_raises_when_validation_configuration_is_not_dict(self, rule):
        with pytest.raises(ValueError, match="debe ser un diccionario"):
            writer._apply_configured_catalog(
                rule,
                "CONSULTORIA",
                {"CODIGO": "incorrecto"},
                {},
            )

    def test_raises_when_catalog_is_not_defined(self, rule):
        with pytest.raises(ValueError, match="no está definido"):
            writer._apply_configured_catalog(
                rule,
                "CONSULTORIA",
                {"CODIGO": {"catalog": "inexistente"}},
                {},
            )


# ============================================================
# DEDUPLICACIÓN DE LISTAS
# ============================================================

class TestDedupRulesWithLists:

    def test_returns_empty_list_when_there_are_no_catalogs(self):
        header = make_header()
        rule = ValidationRule(column_name="CODIGO")

        result = writer._dedup_rules_with_lists(
            [header],
            {("CONSULTORIA", "CODIGO"): rule},
        )

        assert result == []

    def test_returns_rule_with_allowed_values(self):
        header = make_header()
        rule = ValidationRule(
            column_name="CODIGO",
            allowed_values=[
                AllowedValue(code="1", label="Activo"),
            ],
        )

        result = writer._dedup_rules_with_lists(
            [header],
            {("CONSULTORIA", "CODIGO"): rule},
        )

        assert result == [rule]

    def test_deduplicates_same_column_with_same_catalog(self):
        header1 = make_header("CONSULTORIA", "CODIGO", "A")
        header2 = make_header("PROYECTOS", "CODIGO", "B")

        values = [
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ]

        rule1 = ValidationRule(
            column_name="CODIGO",
            allowed_values=values.copy(),
        )
        rule2 = ValidationRule(
            column_name="CODIGO",
            allowed_values=values.copy(),
        )

        result = writer._dedup_rules_with_lists(
            [header1, header2],
            {
                ("CONSULTORIA", "CODIGO"): rule1,
                ("PROYECTOS", "CODIGO"): rule2,
            },
        )

        assert result == [rule1]

    def test_raises_when_same_column_has_different_catalogs(self):
        header1 = make_header("CONSULTORIA", "CODIGO", "A")
        header2 = make_header("PROYECTOS", "CODIGO", "B")

        rule1 = ValidationRule(
            column_name="CODIGO",
            allowed_values=[
                AllowedValue(code="1", label="Activo"),
            ],
        )
        rule2 = ValidationRule(
            column_name="CODIGO",
            allowed_values=[
                AllowedValue(code="2", label="Inactivo"),
            ],
        )

        with pytest.raises(ValueError, match="catálogos diferentes"):
            writer._dedup_rules_with_lists(
                [header1, header2],
                {
                    ("CONSULTORIA", "CODIGO"): rule1,
                    ("PROYECTOS", "CODIGO"): rule2,
                },
            )

    def test_preserves_different_columns(self):
        header1 = make_header("CONSULTORIA", "CODIGO", "A")
        header2 = make_header("CONSULTORIA", "ESTADO", "B")

        rule1 = ValidationRule(
            column_name="CODIGO",
            allowed_values=[
                AllowedValue(code="1", label="Uno"),
            ],
        )
        rule2 = ValidationRule(
            column_name="ESTADO",
            allowed_values=[
                AllowedValue(code="A", label="Activo"),
            ],
        )

        result = writer._dedup_rules_with_lists(
            [header1, header2],
            {
                ("CONSULTORIA", "CODIGO"): rule1,
                ("CONSULTORIA", "ESTADO"): rule2,
            },
        )

        assert result == [rule1, rule2]


# ============================================================
# DETECCIÓN DE VALIDACIONES DE TIPO
# ============================================================

class TestTypeValidation:

    @pytest.mark.parametrize(
        "datatype",
        [
            DataType.INTEGER,
            DataType.DECIMAL,
            DataType.DATE,
        ],
    )
    def test_detects_numeric_and_date_types(self, datatype):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=datatype,
        )

        assert writer._has_type_validation(rule) is True

    @pytest.mark.parametrize(
        "datatype",
        [
            DataType.ALPHANUMERIC,
            DataType.ALPHABETIC,
            DataType.TEXT,
        ],
    )
    def test_detects_text_types_with_length_constraints(self, datatype):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=datatype,
            min_length=2,
        )

        assert writer._has_type_validation(rule) is True

    def test_does_not_detect_text_type_without_length_constraints(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
        )

        assert writer._has_type_validation(rule) is False

    def test_does_not_detect_unknown_type_without_constraints(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.UNKNOWN,
        )

        assert writer._has_type_validation(rule) is False

    def test_detects_exact_length_constraint(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            exact_length=10,
        )

        assert writer._has_type_validation(rule) is True

    def test_detects_max_length_constraint(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            max_length=50,
        )

        assert writer._has_type_validation(rule) is True


class TestTypeValidationDescription:

    @pytest.mark.parametrize(
        "datatype, expected",
        [
            (DataType.INTEGER, "tipo:INTEGER"),
            (DataType.DECIMAL, "tipo:DECIMAL"),
            (DataType.DATE, "tipo:DATE"),
        ],
    )
    def test_describes_basic_types(self, datatype, expected):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=datatype,
        )

        assert writer._get_type_validation_description(rule) == expected

    def test_describes_exact_length(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            exact_length=10,
        )

        assert writer._get_type_validation_description(rule) == (
            "longitud:exacta_10"
        )

    def test_describes_minimum_and_maximum_length(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            min_length=5,
            max_length=20,
        )

        assert writer._get_type_validation_description(rule) == (
            "longitud:entre_5_y_20"
        )

    def test_describes_minimum_length(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            min_length=5,
        )

        assert writer._get_type_validation_description(rule) == (
            "longitud:minima_5"
        )

    def test_describes_maximum_length(self):
        rule = ValidationRule(
            column_name="CAMPO",
            datatype=DataType.TEXT,
            max_length=20,
        )

        assert writer._get_type_validation_description(rule) == (
            "longitud:maxima_20"
        )


# ============================================================
# RESTRICCIONES POST-HOC
# ============================================================

class TestConfiguredPostHocConstraints:

    def test_returns_empty_list_without_configured_constraints(self):
        assert writer._get_configured_post_hoc_constraints({}) == []

    @pytest.mark.parametrize(
        "key",
        sorted(writer.POST_HOC_VALIDATION_KEYS),
    )
    def test_detects_each_post_hoc_constraint(self, key):
        result = writer._get_configured_post_hoc_constraints(
            {key: "valor"}
        )

        assert result == [
            f"post_hoc:validacion_configurada:{key}"
        ]

    def test_detects_multiple_constraints(self):
        result = writer._get_configured_post_hoc_constraints(
            {
                "pattern": ".*",
                "min_value": 0,
                "format": "email",
            }
        )

        assert set(result) == {
            "post_hoc:validacion_configurada:pattern",
            "post_hoc:validacion_configurada:min_value",
            "post_hoc:validacion_configurada:format",
        }

    def test_ignores_catalog_configuration(self):
        result = writer._get_configured_post_hoc_constraints(
            {"catalog": "estados"}
        )

        assert result == []

    def test_ignores_unknown_configuration_keys(self):
        result = writer._get_configured_post_hoc_constraints(
            {"unknown": "value"}
        )

        assert result == []

    @pytest.mark.parametrize(
        "invalid",
        [None, [], "texto", 123],
    )
    def test_raises_when_configuration_is_not_dict(self, invalid):
        with pytest.raises(ValueError, match="debe ser un diccionario"):
            writer._get_configured_post_hoc_constraints(invalid)


# ============================================================
# CONSTRUCCIÓN DE REGLAS DE NEGOCIO
# ============================================================

class TestBuildBusinessValidation:

    def test_returns_none_for_unsupported_business_rule(self, rule):
        result = writer._build_business_validation(
            business_rule={"kind": "unsupported"},
            rule=rule,
            column_letter="A",
            column_letters_by_sheet={},
            sheet_name="CONSULTORIA",
        )

        assert result is None

    def test_builds_date_after_column_validation(
        self, monkeypatch, rule
    ):
        expected = DataValidation(type="custom")

        builder = Mock(return_value=expected)
        monkeypatch.setattr(
            writer,
            "build_date_after_column_validation",
            builder,
        )

        result = writer._build_business_validation(
            business_rule={
                "kind": "date_after_column",
                "after_column": "FECHA_INICIO",
                "strict": True,
            },
            rule=rule,
            column_letter="B",
            column_letters_by_sheet={
                "CONSULTORIA": {"FECHA_INICIO": "A"},
            },
            sheet_name="CONSULTORIA",
        )

        assert result is expected
        builder.assert_called_once_with(
            own_column_letter="B",
            after_column_letter="A",
            after_column_name="FECHA_INICIO",
            strict=True,
        )

    def test_raises_when_date_after_column_is_missing(self, rule):
        with pytest.raises(ValueError, match="no define after_column"):
            writer._build_business_validation(
                business_rule={"kind": "date_after_column"},
                rule=rule,
                column_letter="B",
                column_letters_by_sheet={},
                sheet_name="CONSULTORIA",
            )

    def test_raises_when_referenced_column_does_not_exist(self, rule):
        with pytest.raises(ValueError, match="no existe en la hoja"):
            writer._build_business_validation(
                business_rule={
                    "kind": "date_after_column",
                    "after_column": "FECHA_INICIO",
                },
                rule=rule,
                column_letter="B",
                column_letters_by_sheet={"CONSULTORIA": {}},
                sheet_name="CONSULTORIA",
            )

    @pytest.mark.parametrize(
        "kind",
        sorted(writer.SUPPORTED_BUSINESS_RULES - {"date_after_column"}),
    )
    def test_delegates_supported_business_rules(
        self, monkeypatch, rule, kind
    ):
        expected = DataValidation(type="custom")
        builder = Mock(return_value=expected)

        monkeypatch.setattr(
            writer,
            "build_business_rule_validation",
            builder,
        )

        params = {"kind": kind, "years": 80}

        result = writer._build_business_validation(
            business_rule=params,
            rule=rule,
            column_letter="A",
            column_letters_by_sheet={},
            sheet_name="CONSULTORIA",
        )

        assert result is expected
        builder.assert_called_once_with(
            kind=kind,
            params=params,
            column_letter="A",
            rule=rule,
        )


# ============================================================
# APLICACIÓN DE VALIDACIONES
# ============================================================

class TestApplyValidation:

    def test_adds_validation_to_worksheet(self):
        workbook = Workbook()
        worksheet = workbook.active
        validation = DataValidation(type="whole")

        writer._apply_validation(
            worksheet,
            validation,
            "A2:A2000",
        )

        assert validation in worksheet.data_validations.dataValidation

    def test_applies_validation_to_requested_range(self):
        workbook = Workbook()
        worksheet = workbook.active
        validation = DataValidation(type="whole")

        writer._apply_validation(
            worksheet,
            validation,
            "B2:B2000",
        )

        assert "B2:B2000" in str(validation.sqref)


# ============================================================
# PROCESAMIENTO COMPLETO DEL WORKBOOK
# ============================================================

class TestProcessWorkbook:

    def configure_minimal_workbook(
    self,
    monkeypatch,
    workbook,
    rules_by_column,
    validations=None,
    business_rules=None,
):
        validations = validations or {}
        business_rules = business_rules or {}

        configuration = SimpleNamespace(
            known_fields={},
            sheet_configurations={
                ws.title: {
                    "rules": {},
                    "validations": validations,
                    "catalogs": {},
                }
                for ws in workbook.worksheets
            },
            validation_config={},
        )

        def interpret(
            column_name,
            comment_text,
            known_fields,
            sheet_name,
        ):
            return rules_by_column[(sheet_name, column_name)]

        
        monkeypatch.setattr(
            writer,
            "detect_templates",
            lambda names: ["consultoria"],
        )
        monkeypatch.setattr(
            writer,
            "load_rule_configuration",
            lambda template_name: configuration,
        )

        monkeypatch.setattr(
            writer,
            "build_helper_sheet",
            lambda wb, rules: {
                rule.column_name: f"LISTA_{rule.column_name}"
                for rule in rules
            },
        )
        monkeypatch.setattr(
            writer,
            "resolve_business_rule",
            lambda config, column_name, sheet_name: (
                business_rules.get((sheet_name, column_name))
            ),
        )
        monkeypatch.setattr(
            writer,
            "interpret_comment",
            interpret,
        )

        return configuration

    def test_processes_workbook_and_returns_one_report_per_header(
        self, monkeypatch, workbook
    ):
        ws = workbook["CONSULTORIA"]

        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        reports = writer.process_workbook(workbook)

        assert len(reports) == 2
        assert all(report.sheet_name == ws.title for report in reports)
        assert [report.column_name for report in reports] == [
            "CODIGO",
            "NOMBRE",
        ]

    def test_report_contains_original_validation_rule(
        self, monkeypatch, workbook
    ):
        expected_rule = ValidationRule(
            column_name="CODIGO",
            datatype=DataType.INTEGER,
        )

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            {
                ("CONSULTORIA", "CODIGO"): expected_rule,
                ("CONSULTORIA", "NOMBRE"): ValidationRule(
                    column_name="NOMBRE",
                    datatype=DataType.TEXT,
                ),
            },
        )

        reports = writer.process_workbook(workbook)

        assert reports[0].rule is expected_rule

    def test_applies_type_validation_to_integer_column(
        self, monkeypatch, workbook
    ):
        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.INTEGER,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        writer.process_workbook(workbook)

        validations = workbook["CONSULTORIA"].data_validations.dataValidation

        assert len(validations) == 1
        assert "A2:A1048576" in str(validations[0].sqref)

    def test_skips_control_sheets(self, monkeypatch):
        wb = Workbook()
        wb.active.title = "INFO"
        wb["INFO"].append(["CONTROL"])

        ws = wb.create_sheet("CONSULTORIA")
        ws.append(["CODIGO"])

        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            wb,
            rules,
        )

        reports = writer.process_workbook(wb)

        assert len(reports) == 1
        assert reports[0].sheet_name == "CONSULTORIA"

    def test_skips_auxiliary_sheets(self, monkeypatch):
        wb = Workbook()
        wb.active.title = "CONSULTORIA"
        wb["CONSULTORIA"].append(["CODIGO"])

        auxiliary = wb.create_sheet("_AUXILIAR")
        auxiliary.append(["CAMPO_INTERNO"])

        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            wb,
            rules,
        )

        reports = writer.process_workbook(wb)

        assert len(reports) == 1
        assert reports[0].sheet_name == "CONSULTORIA"

    def test_raises_when_multiple_templates_are_detected(
        self, monkeypatch, workbook
    ):
        monkeypatch.setattr(
            writer,
            "detect_templates",
            lambda names: ["consultoria", "proyectos"],
        )

        with pytest.raises(ValueError, match="varias plantillas SNIES"):
            writer.process_workbook(workbook)

    
    def test_loads_configuration_for_detected_template(
        self, monkeypatch, workbook
    ):
        configuration = SimpleNamespace(
            known_fields={},
            sheet_configurations={
                "CONSULTORIA": {
                    "rules": {},
                    "validations": {},
                    "catalogs": {},
                },
            },
        )

        loader = Mock(return_value=configuration)

        monkeypatch.setattr(
            writer,
            "detect_templates",
            lambda names: ["consultoria"],
        )
        monkeypatch.setattr(
            writer,
            "load_rule_configuration",
            loader,
        )
        monkeypatch.setattr(
            writer,
            "build_helper_sheet",
            lambda wb, rules: {},
        )
        monkeypatch.setattr(
            writer,
            "interpret_comment",
            lambda column_name, comment_text, known_fields, sheet_name: (
                ValidationRule(
                    column_name=column_name,
                    datatype=DataType.TEXT,
                )
            ),
        )
        monkeypatch.setattr(
            writer,
            "resolve_business_rule",
            lambda *args, **kwargs: None,
        )

        writer.process_workbook(workbook)

        loader.assert_called_once_with(
            template_name="consultoria",
        )


    def test_applies_list_validation_with_priority_over_type(
        self, monkeypatch, workbook
    ):
        values = [
            AllowedValue(code="1", label="Activo"),
            AllowedValue(code="2", label="Inactivo"),
        ]

        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.INTEGER,
                allowed_values=values,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        monkeypatch.setattr(
            writer,
            "build_list_validation",
            lambda rule, name: DataValidation(type="list"),
        )

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        reports = writer.process_workbook(workbook)

        validations = workbook["CONSULTORIA"].data_validations.dataValidation

        assert len(validations) == 1
        assert validations[0].type == "list"
        assert "lista_desplegable" in reports[0].validations_applied
        assert "post_hoc:tipo:INTEGER" in reports[0].validations_applied

    def test_registers_post_hoc_review_for_manual_rule(
        self, monkeypatch, workbook
    ):
        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
                unparsed_fragments=["restricción no interpretada"],
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        reports = writer.process_workbook(workbook)

        assert reports[0].needs_review is True

    def test_registers_configured_post_hoc_constraints(
        self, monkeypatch, workbook
    ):
        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
            validations={
                "CODIGO": {"pattern": "^[A-Z]+$"},
            },
        )

        reports = writer.process_workbook(workbook)

        assert (
            "post_hoc:validacion_configurada:pattern"
            in reports[0].validations_applied
        )
        assert reports[0].needs_review is True

    def test_preserves_original_cell_values(self, monkeypatch, workbook):
        worksheet = workbook["CONSULTORIA"]
        worksheet["A2"] = "001"
        worksheet["B2"] = "Texto original"

        original_values = [
            worksheet["A2"].value,
            worksheet["B2"].value,
        ]

        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.TEXT,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        writer.process_workbook(workbook)

        assert [
            worksheet["A2"].value,
            worksheet["B2"].value,
        ] == original_values

    def test_does_not_apply_validation_to_header_row(
        self, monkeypatch, workbook
    ):
        rules = {
            ("CONSULTORIA", "CODIGO"): ValidationRule(
                column_name="CODIGO",
                datatype=DataType.INTEGER,
            ),
            ("CONSULTORIA", "NOMBRE"): ValidationRule(
                column_name="NOMBRE",
                datatype=DataType.TEXT,
            ),
        }

        self.configure_minimal_workbook(
            monkeypatch,
            workbook,
            rules,
        )

        writer.process_workbook(workbook)

        validation = (
            workbook["CONSULTORIA"]
            .data_validations.dataValidation[0]
        )

        assert str(validation.sqref) == "A2:A1048576"

    def test_returns_empty_report_when_workbook_has_no_data_headers(
        self, monkeypatch
    ):
        wb = Workbook()
        wb.active.title = "INFO"

        self.configure_minimal_workbook(
            monkeypatch,
            wb,
            {},
        )

        reports = writer.process_workbook(wb)

        assert reports == []