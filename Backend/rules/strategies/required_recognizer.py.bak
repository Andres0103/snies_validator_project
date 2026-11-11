
"""
Reconocedor de obligatoriedad.

Identifica tres situaciones:

    1. Obligatorio:
       El campo debe tener un valor.

    2. Opcional:
       El campo puede quedar vacío.

    3. Obligatorio condicional:
       El campo debe tener un valor cuando se cumple
       una condición determinada.

Las condiciones se almacenan como texto original mediante
ConditionalRequirement. Este módulo no intenta evaluarlas,
porque esa responsabilidad corresponde a una capa posterior.
"""

from __future__ import annotations

import re

from backend.rules.general_model import (
    ConditionalRequirement,
    ValidationRule,
)

from rules.strategies.base import RuleRecognizer


# ============================================================
# PATRONES
# ============================================================

# Detecta expresiones como:
#
# Obligatorio para fuente internacional.
# Obligatorio si el tipo de financiación es nacional.
#
# La condición se captura hasta encontrar puntuación
# o el final de la línea.
_CONDITIONAL_PATTERN = re.compile(
    r"\bobligatorio\s+(para|si)\s+([^.;,\n]+)",
    re.IGNORECASE,
)


# Detecta expresiones negativas:
#
# No obligatorio.
# No es obligatorio.
#
# Se procesa antes del patrón de obligatoriedad para
# evitar que "no obligatorio" se interprete como obligatorio.
_NOT_REQUIRED_PATTERN = re.compile(
    r"\bno\s+(?:es\s+)?obligatorio\b",
    re.IGNORECASE,
)


# Detecta obligatoriedad explícita.
_REQUIRED_PATTERN = re.compile(
    r"\bobligatorio\b",
    re.IGNORECASE,
)


# Detecta opcionalidad explícita.
_OPTIONAL_PATTERN = re.compile(
    r"\bopcional\b",
    re.IGNORECASE,
)


# ============================================================
# RECONOCEDOR
# ============================================================

class RequiredRecognizer(RuleRecognizer):
    """
    Identifica la obligatoriedad de una columna.

    No evalúa condiciones de negocio. Únicamente interpreta
    su presencia y conserva su descripción para el motor
    de validación posterior.
    """

    def recognize(
        self,
        normalized_text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Interpreta las expresiones de obligatoriedad y devuelve
        el texto que no pertenece a ellas.

        Si encuentra instrucciones contradictorias, no elige
        una arbitrariamente: registra el conflicto para revisión.
        """

        text = normalized_text

        # ----------------------------------------------------
        # 1. DETECTAR EXPRESIONES NEGATIVAS
        # ----------------------------------------------------

        negative_matches = list(
            _NOT_REQUIRED_PATTERN.finditer(text)
        )

        # ----------------------------------------------------
        # 2. DETECTAR OBLIGATORIEDAD CONDICIONAL
        # ----------------------------------------------------

        conditional_matches = list(
            _CONDITIONAL_PATTERN.finditer(text)
        )

        # ----------------------------------------------------
        # 3. DETECTAR OPCIONALIDAD Y OBLIGATORIEDAD SIMPLE
        # ----------------------------------------------------

        optional_matches = list(
            _OPTIONAL_PATTERN.finditer(text)
        )

        # Para evitar que el término "obligatorio" dentro
        # de "no obligatorio" se interprete como positivo,
        # primero retiramos temporalmente las expresiones negativas.
        text_without_negative = _remove_matches(
            text,
            negative_matches,
        )

        required_matches = list(
            _REQUIRED_PATTERN.finditer(
                text_without_negative
            )
        )

        # ----------------------------------------------------
        # 4. DETERMINAR SI EXISTEN CONTRADICCIONES
        # ----------------------------------------------------

        has_negative = bool(negative_matches)
        has_optional = bool(optional_matches)
        has_required = bool(required_matches)
        has_conditional = bool(conditional_matches)

        has_optional_instruction = (
            has_negative or has_optional
        )

        has_required_instruction = (
            has_required or has_conditional
        )

        # Un campo no puede ser simultáneamente obligatorio
        # y opcional sin una condición que explique la diferencia.
        #
        # En lugar de elegir una interpretación, dejamos
        # constancia del conflicto.
        if (
            has_optional_instruction
            and has_required_instruction
        ):

            _add_review_fragment(
                rule,
                "Se encontraron instrucciones contradictorias "
                "de obligatoriedad y opcionalidad.",
            )

            return text

        # ----------------------------------------------------
        # 5. PROCESAR OBLIGATORIEDAD CONDICIONAL
        # ----------------------------------------------------

        if conditional_matches:

            first_match = conditional_matches[0]

            rule.required = False

            rule.conditional_requirement = ConditionalRequirement(
                raw_text=first_match.group(0).strip()
            )

            # El modelo actual solo puede almacenar una condición.
            # Si hay más de una, no descartamos silenciosamente
            # las restantes.
            for extra_match in conditional_matches[1:]:

                _add_review_fragment(
                    rule,
                    "Condición adicional de obligatoriedad "
                    f"que requiere revisión: "
                    f"'{extra_match.group(0).strip()}'.",
                )

            # Retiramos la primera condición reconocida.
            # Las adicionales permanecen en el texto para
            # que no se pierda información.
            return _remove_matches(
                text,
                [first_match],
            )

        # ----------------------------------------------------
        # 6. PROCESAR OPCIONALIDAD
        # ----------------------------------------------------

        if has_optional_instruction:

            rule.required = False

            # Retiramos todas las expresiones negativas
            # y las menciones explícitas de opcionalidad.
            matches_to_remove = (
                negative_matches
                + optional_matches
            )

            return _remove_matches(
                text,
                matches_to_remove,
            )

        # ----------------------------------------------------
        # 7. PROCESAR OBLIGATORIEDAD SIMPLE
        # ----------------------------------------------------

        if has_required:

            rule.required = True

            # Retiramos todas las menciones reconocidas.
            # No eliminamos otras instrucciones del comentario.
            return _remove_matches(
                text_without_negative,
                required_matches,
            )

        # ----------------------------------------------------
        # 8. NO SE IDENTIFICÓ OBLIGATORIEDAD
        # ----------------------------------------------------

        return text


# ============================================================
# UTILIDADES
# ============================================================

def _remove_matches(
    text: str,
    matches: list[re.Match],
) -> str:
    """
    Elimina las coincidencias de derecha a izquierda.

    Al comenzar por el final, los índices de las coincidencias
    anteriores no cambian mientras se modifica el texto.
    """

    for match in reversed(matches):

        text = (
            text[:match.start()]
            + " "
            + text[match.end():]
        )

    return text


def _add_review_fragment(
    rule: ValidationRule,
    message: str,
) -> None:
    """
    Registra un problema de interpretación sin duplicarlo.
    """

    if message not in rule.unparsed_fragments:
        rule.unparsed_fragments.append(message)
