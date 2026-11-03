"""Orquesta la interpretación de un comentario de celda en una ValidationRule.

No conoce el "cómo" de ninguna regla individual: solo ejecuta la lista de
`RuleRecognizer` registrados, en orden, sobre el mismo texto, y decide qué
sobrante del comentario se guarda como descripción legible para el usuario
vs. qué sobrante indica que algo no fue interpretado (revisión manual).
"""

from __future__ import annotations

import re

from rules.known_fields import apply_known_field_fallback
from rules.master_tables import apply_master_table_reference
from rules.models import ValidationRule
from rules.strategies.base import RuleRecognizer
from rules.strategies.datatype_recognizer import DatatypeRecognizer
from rules.strategies.list_recognizer import ListRecognizer
from rules.strategies.required_recognizer import RequiredRecognizer
from utils.text_normalizer import normalize

# El orden importa: ListRecognizer debe ir primero porque el bloque de
# valores permitidos puede contener texto que confundiría a los demás
# reconocedores (ej. números que parecen longitudes).
DEFAULT_RECOGNIZERS: list[RuleRecognizer] = [
    ListRecognizer(),
    RequiredRecognizer(),
    DatatypeRecognizer(),
]

# Fragmentos residuales que son ruido de puntuación, no información real.
_NOISE_ONLY = re.compile(r"^[\s,.\-:;]*$")


def interpret_comment(column_name: str, raw_comment: str) -> ValidationRule:
    """Convierte el comentario en lenguaje natural de una columna en una ValidationRule."""
    rule = ValidationRule(column_name=column_name, raw_comment=raw_comment or "")

    if not raw_comment:
        rule.unparsed_fragments.append("(sin comentario)")
        return apply_known_field_fallback(rule)

    text = normalize(raw_comment)

    for recognizer in DEFAULT_RECOGNIZERS:
        text = recognizer.recognize(text, rule)

    remainder = text.strip(" .,\n")
    if remainder and not _NOISE_ONLY.match(remainder):
        # Lo que sobra tras quitar obligatoriedad/tipo/lista es, casi
        # siempre, la descripción humana del campo (ej. "código de la
        # consultoria"). Se capitaliza para presentación.
        rule.description = remainder[0].upper() + remainder[1:] if remainder else ""

    rule = apply_master_table_reference(rule, raw_comment)
    return apply_known_field_fallback(rule)
