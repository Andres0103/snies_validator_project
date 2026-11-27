"""Normalización de texto de comentarios antes de aplicar reconocedores.

Los comentarios del MEN tienen inconsistencias reales observadas en las
plantillas (ej. el typo sistemático "Obligatario" en vez de "Obligatorio",
espacios dobles, saltos de línea irregulares). Este módulo centraliza esas
correcciones para que los reconocedores de reglas trabajen sobre texto
predecible.
"""

from __future__ import annotations

import re
import unicodedata

# Typos y variantes conocidas observadas en plantillas reales del MEN.
# Se mantienen aquí (no en el core) para que sea fácil ampliar la lista.
KNOWN_TYPOS = {
    r"\bobligatario\b": "obligatorio",
    r"\bobligatorios\b": "obligatorio",
}


def normalize(raw_text: str) -> str:
    """Normaliza un comentario de celda para el análisis de patrones.

    Importante: NO convierte a minúsculas. Todos los reconocedores usan
    `re.IGNORECASE`, así que no lo necesitan para hacer match; y preservar
    mayúsculas/tildes originales es lo que permite que las descripciones y
    las etiquetas de listas desplegables se muestren bien formadas al
    usuario final, en vez de "sector empresarial" en minúscula.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Colapsar espacios múltiples (pero conservar saltos de línea, que
    # delimitan secciones como listas de valores válidos).
    text = re.sub(r"[ \t]+", " ", text)

    # Corregir typos conocidos (insensible a mayúsculas, pero el resultado
    # de la sustitución queda en minúscula solo para esa palabra puntual;
    # es aceptable porque estas palabras clave se eliminan del texto y
    # nunca llegan a mostrarse al usuario).
    for pattern, replacement in KNOWN_TYPOS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text.strip()


def strip_accents(text: str) -> str:
    """Quita tildes, útil para comparar contra listas de palabras clave."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))
