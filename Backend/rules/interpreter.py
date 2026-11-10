
"""Orquesta la interpretación de un comentario de celda en una ValidationRule.

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
from backend.rules.general_model import ValidationRule
from rules.strategies.base import RuleRecognizer
from rules.strategies.datatype_recognizer import DatatypeRecognizer
from rules.strategies.list_recognizer import ListRecognizer
from rules.strategies.required_recognizer import RequiredRecognizer
from core.text_normalizer import normalize


# Orden de ejecución de los reconocedores.
#
# ListRecognizer debe ejecutarse primero porque una lista de valores permitidos
# puede contener números que podrían confundirse con longitudes o restricciones
# de otros tipos de reglas.
#
# Cada reconocedor interpreta una parte del comentario y devuelve el texto
# restante para que pueda ser procesado por el siguiente.
DEFAULT_RECOGNIZERS: list[RuleRecognizer] = [
    ListRecognizer(),
    RequiredRecognizer(),
    DatatypeRecognizer(),
]


# Identifica fragmentos residuales que contienen únicamente espacios
# o signos de puntuación. Estos fragmentos no representan información
# relevante y no necesitan conservarse como descripción.
_NOISE_ONLY = re.compile(r"^[\s,.**\-**:;]*$")


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
    """

    # Creamos el objeto que almacenará todas las reglas interpretadas.
    # También conservamos el comentario original para disponer de la
    # información de origen durante las etapas posteriores.
    rule = ValidationRule(
        column_name=column_name,
        raw_comment=raw_comment or "",
    )

    # Si la columna no tiene comentario, registramos esta situación.
    #
    # Posteriormente intentamos completar la información utilizando
    # la configuración de campos conocidos.
    if not raw_comment:
        rule.unparsed_fragments.append("(sin comentario)")

        rule = apply_known_field_fallback(
            rule,
            known_fields=known_fields,
            sheet_name=sheet_name,
        )

        return rule

    # Normalizamos el comentario para facilitar su interpretación.
    # Esta operación trabaja sobre el texto utilizado por los reconocedores;
    # raw_comment conserva el comentario original.
    text = normalize(raw_comment)

    # Ejecutamos los reconocedores en el orden establecido.
    #
    # Cada reconocedor:
    # 1. Examina el texto recibido.
    # 2. Identifica la información correspondiente a su responsabilidad.
    # 3. Actualiza los atributos necesarios de ValidationRule.
    # 4. Devuelve el texto que todavía no ha sido interpretado.
    for recognizer in DEFAULT_RECOGNIZERS:
        text = recognizer.recognize(text, rule)

    # Eliminamos espacios y signos de puntuación de los extremos
    # del texto que quedó después de ejecutar los reconocedores.
    remainder = text.strip(" .,\n")

    # Si todavía existe texto relevante, lo conservamos como descripción.
    #
    # No guardamos fragmentos compuestos únicamente por puntuación,
    # porque no aportan información útil para explicar la regla.
    if remainder and not _NOISE_ONLY.match(remainder):
        rule.description = remainder[0].upper() + remainder[1:]

    # Buscamos referencias a catálogos maestros mencionados en el comentario.
    #
    # Si se identifica una referencia reconocida, master_tables puede cargar
    # los valores permitidos correspondientes.
    #
    # Sin embargo, si rule.allowed_values ya contiene información,
    # apply_master_table_reference evita sobrescribirla.
    rule = apply_master_table_reference(rule, raw_comment)

    # Aplicamos la configuración de campos conocidos como complemento.
    #
    # Esta etapa permite completar información que no se obtuvo del comentario
    # ni de las referencias a catálogos maestros.
    #
    # El fallback completa información faltante sin reemplazar las reglas
    # explícitas que ya fueron interpretadas.
    rule = apply_known_field_fallback(
        rule,
        known_fields=known_fields,
        sheet_name=sheet_name,
    )

    # Devolvemos la regla construida con la información disponible.
    return rule
