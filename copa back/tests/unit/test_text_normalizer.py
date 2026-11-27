import pytest

from backend.core.text_normalizer import normalize, strip_accents, KNOWN_TYPOS


class TestNormalize:

    @pytest.mark.parametrize(
        "raw_text, expected",
        [
            ("", ""),
            (None, ""),
            ("Obligatorio", "Obligatorio"),
            ("  texto con espacios  ", "texto con espacios"),
            ("texto   con    espacios", "texto con espacios"),
            ("texto\t\tcon\t\tespacios", "texto con espacios"),
            ("texto\r\nsegunda línea", "texto\nsegunda línea"),
            ("texto\rsegunda línea", "texto\nsegunda línea"),
        ],
    )
    def test_normalize_basic_whitespace(self, raw_text, expected):
        assert normalize(raw_text) == expected

    @pytest.mark.parametrize(
        "raw_text, expected",
        [
            ("Obligatario", "obligatorio"),
            ("obligatario", "obligatorio"),
            ("OBLIGATARIO", "obligatorio"),
            ("Obligatorios", "obligatorio"),
            ("OBLIGATORIOS", "obligatorio"),
            ("Campo Obligatario requerido", "Campo obligatorio requerido"),
            ("Campo OBLIGATARIO requerido", "Campo obligatorio requerido"),
        ],
    )
    def test_normalize_known_typos(self, raw_text, expected):
        assert normalize(raw_text) == expected

    def test_normalize_preserves_accents(self):
        text = "Código de institución y descripción académica"

        assert normalize(text) == text

    def test_normalize_preserves_original_case(self):
        text = "Nombre del Sector Empresarial"

        assert normalize(text) == text

    def test_normalize_preserves_line_breaks(self):
        text = "Valores permitidos:\n1. Activo\n2. Inactivo"

        assert normalize(text) == text

    def test_normalize_preserves_multiple_line_breaks(self):
        text = "Primera sección\n\nSegunda sección"

        assert normalize(text) == text

    def test_normalize_does_not_collapse_spaces_inside_line_breaks(self):
        text = "Primera línea\n   Segunda línea"

        assert normalize(text) == "Primera línea\n Segunda línea"

    def test_normalize_does_not_modify_unknown_words(self):
        text = "Obligatario y otro error desconocido"

        assert normalize(text) == "obligatorio y otro error desconocido"

    def test_normalize_is_idempotent(self):
        text = "  Campo OBLIGATARIO   requerido\r\n Segunda línea  "

        normalized = normalize(text)

        assert normalize(normalized) == normalized

    def test_normalize_does_not_mutate_input(self):
        text = "  Campo   obligatorio  "
        original = text

        normalize(text)

        assert text == original

    def test_known_typos_contains_expected_patterns(self):
        assert r"\bobligatario\b" in KNOWN_TYPOS
        assert r"\bobligatorios\b" in KNOWN_TYPOS


class TestStripAccents:

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("áéíóú", "aeiou"),
            ("ÁÉÍÓÚ", "AEIOU"),
            ("ñ", "n"),
            ("Ñ", "N"),
            ("Código", "Codigo"),
            ("Institución académica", "Institucion academica"),
            ("Universidad", "Universidad"),
            ("", ""),
        ],
    )
    def test_strip_accents(self, text, expected):
        assert strip_accents(text) == expected

    def test_strip_accents_preserves_case(self):
        assert strip_accents("Árbol") == "Arbol"

    def test_strip_accents_preserves_non_accented_characters(self):
        text = "ABC-123_@"
        assert strip_accents(text) == text

    def test_strip_accents_does_not_modify_input(self):
        text = "Información"
        original = text

        strip_accents(text)

        assert text == original

    def test_strip_accents_is_idempotent(self):
        text = "Información académica"

        result = strip_accents(text)

        assert strip_accents(result) == result