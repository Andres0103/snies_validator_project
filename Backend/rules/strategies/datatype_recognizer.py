
"""
Reconocedor de tipos de datos, longitudes y formatos de fecha.

Responsabilidades:
    - Reconocer tipos alfanuméricos.
    - Reconocer tipos alfabéticos.
    - Reconocer tipos numéricos, enteros y decimales.
    - Reconocer texto.
    - Reconocer fechas.
    - Extraer longitudes máximas.
    - Extraer formatos de fecha.
    - Detectar declaraciones contradictorias.

Criterio de interpretación:

    "Numérico" se interpreta como DECIMAL porque los manuales
    del MEN utilizan esta expresión tanto para valores enteros
    como para valores que pueden contener decimales.

    "Entero" se interpreta como INTEGER.

El reconocedor no debe descartar declaraciones contradictorias:
las registra para revisión manual y deja el texto disponible
para los siguientes reconocedores.
"""

from __future__ import annotations

import re

from rules.general_model import DataType, ValidationRule
from rules.strategies.base import RuleRecognizer


# ============================================================
# PATRONES
# ============================================================

# Tipos reconocidos:
#
# alfanumérico
# alfanumérica
# alfabético
# alfabética
# numérico
# numérica
# entero
# decimal
# texto

_TYPE_PATTERN = (
    r"alfanum[eé]ric[oa]"
    r"|alfab[eé]tic[oa]"
    r"|num[eé]ric[oa]"
    r"|entero"
    r"|decimal"
    r"|texto"
)


# Reconoce declaraciones con longitud:
#
# alfanumérico (30)
# numérico (4)
# alfabético (2)
# entero (10)
#
# La longitud se captura por separado.
_TYPE_WITH_LENGTH = re.compile(
    rf"\b({_TYPE_PATTERN})\s*"
    r"\(\s*(\d+)\s*\)",
    re.IGNORECASE,
)


# Reconoce declaraciones de tipo sin longitud.
_TYPE_WITHOUT_LENGTH = re.compile(
    rf"\b({_TYPE_PATTERN})\b",
    re.IGNORECASE,
)


# Reconoce fechas con formato explícito:
#
# tipo fecha (dd/mm/aaaa)
# fecha (dd-mm-yyyy)
# tipo fecha (dd.mm.aaaa)
#
# Se permite la expresión "tipo" de forma opcional.
_DATE_WITH_FORMAT = re.compile(
    r"\b(?:tipo\s+)?fecha\s*\(([^)]*)\)",
    re.IGNORECASE,
)


# Reconoce formatos de fecha con separadores consistentes.
#
# dd/mm/aaaa
# dd-mm-yyyy
# dd.mm.aaaa
#
# Se utiliza un grupo de referencia para evitar aceptar
# formatos inconsistentes como dd/mm-aaaa.
_DATE_FORMAT_TOKEN = re.compile(
    r"\bdd(?P<sep>[/.\-])mm(?P=sep)(?P<year>aaaa|yyyy)\b",
    re.IGNORECASE,
)


# Reconoce una fecha sin formato explícito.
_DATE_BARE = re.compile(
    r"\b(?:tipo\s+)?fecha\b",
    re.IGNORECASE,
)


# ============================================================
# MAPEO DE TIPOS
# ============================================================

# Se utiliza la versión normalizada de cada palabra como clave.
# El reconocimiento se realiza sin distinguir mayúsculas
# ni minúsculas, pero sí se contemplan las variantes con tilde.

_TYPE_KEYWORD_TO_ENUM = {
    "alfanumerico": DataType.ALPHANUMERIC,
    "alfanumerica": DataType.ALPHANUMERIC,
    "alfanumérico": DataType.ALPHANUMERIC,
    "alfanumérica": DataType.ALPHANUMERIC,

    "alfabetico": DataType.ALPHABETIC,
    "alfabetica": DataType.ALPHABETIC,
    "alfabético": DataType.ALPHABETIC,
    "alfabética": DataType.ALPHABETIC,

    "numerico": DataType.DECIMAL,
    "numerica": DataType.DECIMAL,
    "numérico": DataType.DECIMAL,
    "numérica": DataType.DECIMAL,

    "entero": DataType.INTEGER,
    "decimal": DataType.DECIMAL,
    "texto": DataType.TEXT,
}


# Formatos de fecha utilizados cuando el comentario no
# especifica uno de manera explícita.
_DEFAULT_DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
]


# ============================================================
# RECONOCEDOR
# ============================================================

class DatatypeRecognizer(RuleRecognizer):
    """
    Identifica tipos de datos, longitudes y formatos de fecha.

    Si encuentra declaraciones contradictorias, no selecciona
    arbitrariamente una de ellas. Registra el problema para
    revisión manual.
    """

    def recognize(
        self,
        normalized_text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Analiza el texto normalizado y actualiza ValidationRule.

        Devuelve el texto restante para que otros reconocedores
        puedan continuar interpretándolo.
        """

        text = normalized_text

        # ----------------------------------------------------
        # 1. BUSCAR DECLARACIONES DE FECHA
        # ----------------------------------------------------

        date_matches = list(
            _DATE_WITH_FORMAT.finditer(text)
        )

        bare_date_matches = list(
            _DATE_BARE.finditer(text)
        )

        # ----------------------------------------------------
        # 2. BUSCAR DECLARACIONES DE TIPO
        # ----------------------------------------------------

        type_matches = list(
            _TYPE_WITH_LENGTH.finditer(text)
        )

        # Identificamos las posiciones ocupadas por declaraciones
        # que ya incluyen longitud.
        #
        # Así evitamos volver a interpretar la palabra del tipo
        # como una declaración independiente.
        occupied_spans = {
            match.span(1)
            for match in type_matches
        }

        type_matches_without_length = [
            match
            for match in _TYPE_WITHOUT_LENGTH.finditer(text)
            if match.span(1) not in occupied_spans
        ]

        all_type_matches = (
            type_matches
            + type_matches_without_length
        )

        # ----------------------------------------------------
        # 3. DETECTAR DECLARACIONES CONTRADICTORIAS
        # ----------------------------------------------------

        detected_types = {
            self._resolve_type(match.group(1))
            for match in all_type_matches
        }

        has_date = bool(
            date_matches or bare_date_matches
        )

        if has_date:
            detected_types.add(DataType.DATE)

        detected_types.discard(DataType.UNKNOWN)

        # Si existen dos o más tipos diferentes, no podemos
        # determinar cuál es el correcto.
        if len(detected_types) > 1:

            self._add_review_fragment(
                rule,
                "Se encontraron declaraciones contradictorias "
                "de tipo de dato en el comentario.",
            )

            return text

        # ----------------------------------------------------
        # 4. DETECTAR LONGITUDES CONTRADICTORIAS
        # ----------------------------------------------------

        detected_lengths = {
            int(match.group(2))
            for match in type_matches
        }

        if len(detected_lengths) > 1:

            self._add_review_fragment(
                rule,
                "Se encontraron diferentes longitudes máximas "
                "para el mismo campo.",
            )

            return text

        # Una longitud de cero no representa una restricción
        # válida para un campo de datos.
        if detected_lengths == {0}:

            self._add_review_fragment(
                rule,
                "Se encontró una longitud máxima igual a cero.",
            )

            return text

        # ----------------------------------------------------
        # 5. ASIGNAR EL TIPO DE DATO
        # ----------------------------------------------------

        if detected_types:

            detected_type = next(
                iter(detected_types)
            )

            # No sobrescribimos una regla que ya tenga
            # un tipo diferente.
            if (
                rule.datatype != DataType.UNKNOWN
                and rule.datatype != detected_type
            ):

                self._add_review_fragment(
                    rule,
                    "El tipo de dato del comentario entra en "
                    "conflicto con el tipo previamente asignado.",
                )

                return text

            rule.datatype = detected_type

        # ----------------------------------------------------
        # 6. ASIGNAR LONGITUD MÁXIMA
        # ----------------------------------------------------

        if detected_lengths:

            detected_length = next(
                iter(detected_lengths)
            )

            # Si ya existe una longitud proveniente de otra
            # fuente, comprobamos que no sea contradictoria.
            if (
                rule.max_length is not None
                and rule.max_length != detected_length
            ):

                self._add_review_fragment(
                    rule,
                    "La longitud máxima del comentario entra "
                    "en conflicto con la longitud previamente "
                    "configurada.",
                )

                return text

            rule.max_length = detected_length

        # ----------------------------------------------------
        # 7. PROCESAR FORMATOS DE FECHA
        # ----------------------------------------------------

        date_formats: list[str] = []

        for match in date_matches:

            formats_raw = match.group(1)

            for token in _DATE_FORMAT_TOKEN.finditer(
                formats_raw
            ):

                separator = token.group("sep")

                date_format = (
                    f"%d{separator}%m{separator}%Y"
                )

                if date_format not in date_formats:
                    date_formats.append(
                        date_format
                    )

        if has_date:

            # Si no se reconoció ningún formato explícito,
            # utilizamos los formatos generales del motor.
            if not date_formats:
                date_formats = list(
                    _DEFAULT_DATE_FORMATS
                )

            # No sobrescribimos formatos previamente definidos
            # sin comprobar que sean compatibles.
            if (
                rule.date_formats
                and set(rule.date_formats)
                != set(date_formats)
            ):

                self._add_review_fragment(
                    rule,
                    "Los formatos de fecha del comentario "
                    "entran en conflicto con los formatos "
                    "previamente configurados.",
                )

                return text

            rule.date_formats = date_formats

        # ----------------------------------------------------
        # 8. RETIRAR LAS EXPRESIONES INTERPRETADAS
        # ----------------------------------------------------

        matches_to_remove = (
            date_matches
            if date_matches
            else bare_date_matches
        )

        matches_to_remove = (
            list(matches_to_remove)
            + all_type_matches
        )

        return self._remove_matches(
            text,
            matches_to_remove,
        )

    # ========================================================
    # UTILIDADES INTERNAS
    # ========================================================

    @staticmethod
    def _resolve_type(keyword: str) -> DataType:
        """
        Convierte la palabra reconocida en DataType.
        """

        return _TYPE_KEYWORD_TO_ENUM.get(
            keyword.lower(),
            DataType.UNKNOWN,
        )

    @staticmethod
    def _remove_matches(
        text: str,
        matches: list[re.Match],
    ) -> str:
        """
        Elimina las coincidencias de derecha a izquierda.

        De esta forma los índices de las coincidencias
        anteriores no cambian al modificar el texto.
        """

        for match in sorted(
            matches,
            key=lambda item: item.start(),
            reverse=True,
        ):

            text = (
                text[:match.start()]
                + " "
                + text[match.end():]
            )

        return text

    @staticmethod
    def _add_review_fragment(
        rule: ValidationRule,
        message: str,
    ) -> None:
        """
        Registra un problema de interpretación sin duplicarlo.
        """

        if message not in rule.unparsed_fragments:
            rule.unparsed_fragments.append(
                message
            )
