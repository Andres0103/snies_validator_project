
"""
Orquesta la interpretación de un comentario de celda en una ValidationRule.

No conoce cómo funciona cada regla individual. Su responsabilidad es ejecutar
los RuleRecognizer registrados, en el orden definido, sobre el mismo texto.

También determina qué texto sobrante se conserva como descripción y aplica
información complementaria proveniente de catálogos maestros y de la
configuración de campos conocidos.
"""

from __future__ import annotations

import re

from rules.known_fields import apply_known_field_fallback
from rules.master_tables import apply_master_table_reference

from rules.general_model import ValidationRule

from rules.strategies.base import RuleRecognizer
from rules.strategies.datatype_recognizer import DatatypeRecognizer
from rules.strategies.list_recognizer import ListRecognizer
from rules.strategies.required_recognizer import RequiredRecognizer

from core.text_normalizer import normalize


# ============================================================
# RECONOCEDORES
# ============================================================

# Los reconocedores se ejecutan en un orden determinado.
#
# ListRecognizer:
#     Identifica listas de valores permitidos.
#
# RequiredRecognizer:
#     Identifica obligatoriedad y obligatoriedad condicional.
#
# DatatypeRecognizer:
#     Identifica tipos de datos y restricciones de longitud.
#
# El orden es importante porque una lista puede contener
# números que no deben confundirse con longitudes o tipos.

DEFAULT_RECOGNIZERS: list[RuleRecognizer] = [
    ListRecognizer(),
    RequiredRecognizer(),
    DatatypeRecognizer(),
]


# ============================================================
# NORMALIZACIÓN DEL TEXTO RESIDUAL
# ============================================================

# Identifica fragmentos compuestos únicamente por espacios
# o signos de puntuación.
#
# Estos fragmentos no contienen información útil para
# describir una regla.

_NOISE_ONLY = re.compile(
    r"^[\s,.*\-:;]+$"
)


# ============================================================
# INTERPRETACIÓN
# ============================================================

def interpret_comment(
    column_name: str,
    raw_comment: str,
    known_fields: dict | None = None,
    sheet_name: str | None = None,
) -> ValidationRule:
    """
    Convierte el comentario de una columna en una ValidationRule.

    Parámetros:
        column_name:
            Nombre de la columna a la que pertenece el comentario.

        raw_comment:
            Comentario original del encabezado de Excel.

        known_fields:
            Configuración de campos conocidos que puede complementar
            la interpretación del comentario.

        sheet_name:
            Nombre de la hoja a la que pertenece la columna.

    Retorna:
        ValidationRule:
            Objeto que contiene las reglas identificadas para la columna.

    Flujo:
        1. Crear la regla.
        2. Comprobar si el comentario está vacío.
        3. Normalizar el comentario.
        4. Ejecutar los reconocedores.
        5. Conservar el texto no interpretado como descripción.
        6. Resolver referencias a catálogos maestros.
        7. Completar información mediante known_fields.
    """

    # --------------------------------------------------------
    # 1. CREAR LA REGLA
    # --------------------------------------------------------

    # Conservamos el comentario original para que las capas
    # posteriores puedan consultar la fuente de información.
    rule = ValidationRule(
        column_name=column_name,
        raw_comment=raw_comment or "",
    )

    # --------------------------------------------------------
    # 2. COMPROBAR SI EL COMENTARIO ESTÁ VACÍO
    # --------------------------------------------------------

    # strip() también detecta comentarios compuestos únicamente
    # por espacios, tabulaciones o saltos de línea.
    if not raw_comment or not raw_comment.strip():

        rule.unparsed_fragments.append(
            "(sin comentario)"
        )

        # Si no existe comentario, intentamos completar
        # la regla utilizando la configuración conocida.
        return apply_known_field_fallback(
            rule,
            known_fields=known_fields,
            sheet_name=sheet_name,
        )

    # --------------------------------------------------------
    # 3. NORMALIZAR EL COMENTARIO
    # --------------------------------------------------------

    # Trabajamos con una copia normalizada.
    #
    # raw_comment permanece intacto dentro de ValidationRule.
    text = normalize(raw_comment)

    # La normalización también puede producir un texto vacío.
    # Lo tratamos como comentario sin contenido interpretable.
    if not text:

        rule.unparsed_fragments.append(
            "(sin comentario)"
        )

        return apply_known_field_fallback(
            rule,
            known_fields=known_fields,
            sheet_name=sheet_name,
        )

    # --------------------------------------------------------
    # 4. EJECUTAR LOS RECONOCEDORES
    # --------------------------------------------------------

    # Cada reconocedor analiza el texto restante, actualiza
    # los atributos de ValidationRule y devuelve el texto
    # que todavía no ha sido interpretado.
    for recognizer in DEFAULT_RECOGNIZERS:

        text = recognizer.recognize(
            text,
            rule,
        )

    # --------------------------------------------------------
    # 5. CONSERVAR EL TEXTO NO INTERPRETADO
    # --------------------------------------------------------

    # Quitamos espacios y puntuación de los extremos.
    remainder = text.strip(
        " .,\n\t"
    )

    # Si el texto restante contiene información, lo guardamos
    # como descripción de la regla.
    #
    # No lo descartamos: puede contener instrucciones
    # importantes del MEN que todavía no tienen reconocedor.
    if (
        remainder
        and not _NOISE_ONLY.fullmatch(remainder)
    ):

        rule.description = (
            remainder[0].upper()
            + remainder[1:]
        )

    # --------------------------------------------------------
    # 6. RESOLVER CATÁLOGOS MAESTROS
    # --------------------------------------------------------

    # Busca referencias reconocidas a catálogos dentro
    # del comentario original.
    #
    # Si el comentario ya produjo una lista explícita,
    # master_tables no debe sobrescribirla.
    #
    # Si se identifica una referencia y el catálogo no puede
    # cargarse, el error debe propagarse.
    rule = apply_master_table_reference(
        rule,
        raw_comment,
    )

    # --------------------------------------------------------
    # 7. COMPLETAR CON CAMPOS CONOCIDOS
    # --------------------------------------------------------

    # known_fields completa los atributos que no pudieron
    # identificarse en los pasos anteriores.
    #
    # La información explícita del comentario conserva
    # prioridad sobre la configuración complementaria.
    rule = apply_known_field_fallback(
        rule,
        known_fields=known_fields,
        sheet_name=sheet_name,
    )

    # --------------------------------------------------------
    # 8. DEVOLVER LA REGLA
    # --------------------------------------------------------

    return rule
