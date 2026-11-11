
"""
Reconocedor de listas de valores permitidos.

Responsabilidades:
    - Detectar listas introducidas por frases explícitas.
    - Detectar listas sin frase introductoria mediante un mecanismo
      de respaldo conservador.
    - Convertir cada elemento en AllowedValue.
    - Detectar códigos duplicados e inconsistencias.
    - Devolver el texto que no pertenece a la lista para que
      los siguientes reconocedores puedan procesarlo.

Principio importante:

    Este reconocedor solamente debe consumir las líneas que
    realmente pertenecen a una lista.

    Nunca debe descartar las instrucciones restantes del comentario.
"""

from __future__ import annotations

import re

from backend.rules.general_model import (
    AllowedValue,
    ValidationRule,
)

from rules.strategies.base import RuleRecognizer


# ============================================================
# PATRONES
# ============================================================

# Detecta frases como:
#
# Los valores válidos son:
# Los valores posibles son:
# El valor válido es:
#
# Se aceptan las formas singular y plural.
_LIST_MARKER = re.compile(
    r"\b(?:los?\s+valores?|el\s+valor)\s+"
    r"(?:v[aá]lidos?|posibles?)\s+"
    r"(?:son|es)\s*:?",
    re.IGNORECASE,
)


# Lista explícita:
#
# 1 Sector empresarial
# CC Cédula de ciudadanía
# 6. Todas las anteriores
# A01 Descripción
#
# Se permite un código alfanumérico corto.
# La interpretación está respaldada por la frase introductoria.
_LIST_ITEM = re.compile(
    r"^\s*([A-Za-z0-9]{1,4})[\.\)\s]+(.+?)\s*$"
)


# Lista detectada por respaldo:
#
# Aquí exigimos códigos numéricos, alfabéticos en mayúsculas
# o alfanuméricos que contengan al menos un número.
#
# Es más restrictivo que el patrón explícito para evitar
# interpretar palabras normales como códigos.
_FALLBACK_LIST_ITEM = re.compile(
    r"^\s*("
    r"\d{1,4}"
    r"|[A-Z]{1,4}"
    r"|(?=[A-Za-z0-9]{1,4}\b)"
    r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{1,4}"
    r")[\.\)\s]+(.+?)\s*$"
)


# Cantidad mínima de líneas consecutivas para activar
# la detección de respaldo.
_MIN_FALLBACK_RUN = 3


# ============================================================
# RECONOCEDOR
# ============================================================

class ListRecognizer(RuleRecognizer):
    """
    Extrae listas código-descripción de comentarios Excel.

    Trabaja en dos modalidades:

        1. Lista explícita:
           El comentario contiene una frase introductoria
           como "Los valores válidos son:".

        2. Lista por respaldo:
           No existe frase introductoria, pero se encuentra
           una secuencia de al menos tres líneas con formato
           código-descripción.
    """

    def recognize(
        self,
        normalized_text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Analiza el comentario y devuelve el texto restante.

        Si la regla ya tiene valores permitidos, no intenta
        reemplazarlos con otra lista.
        """

        if rule.allowed_values:
            return normalized_text

        marker_match = _LIST_MARKER.search(
            normalized_text
        )

        # ----------------------------------------------------
        # LISTA EXPLÍCITA
        # ----------------------------------------------------

        if marker_match:

            before = normalized_text[:marker_match.start()]

            block = normalized_text[marker_match.end():]

            remaining = self._extract_from_block(
                block,
                rule,
            )

            return self._join_remaining(
                before,
                remaining,
            )

        # ----------------------------------------------------
        # LISTA POR RESPALDO
        # ----------------------------------------------------

        return self._extract_fallback(
            normalized_text,
            rule,
        )

    # ========================================================
    # EXTRACCIÓN DE LISTA EXPLÍCITA
    # ========================================================

    def _extract_from_block(
        self,
        block: str,
        rule: ValidationRule,
    ) -> str:
        """
        Extrae una lista explícita sin consumir las instrucciones
        que aparezcan antes o después de ella.

        La lista comienza en la primera línea que coincide
        con el patrón código-descripción.

        Una vez iniciada, se aceptan líneas vacías entre
        elementos.

        Cuando aparece una línea que no corresponde a un
        elemento de lista, se considera que terminó el bloque.
        Esa línea y las siguientes se conservan.
        """

        lines = block.split("\n")

        values: list[AllowedValue] = []

        remaining: list[str] = []

        list_started = False

        # Conserva temporalmente los saltos de línea entre
        # elementos para poder devolverlos si no pertenecen
        # finalmente a la lista.
        pending_blank_lines: list[str] = []

        for index, line in enumerate(lines):

            stripped_line = line.strip()

            # Antes de encontrar la lista, conservamos
            # cualquier texto que no sea un elemento.
            if not list_started:

                if not stripped_line:
                    remaining.append(line)
                    continue

                item_match = _LIST_ITEM.match(line)

                if not item_match:
                    remaining.append(line)
                    continue

                list_started = True

            # Una vez iniciada la lista, permitimos líneas
            # vacías entre sus elementos.
            if not stripped_line:

                pending_blank_lines.append(line)
                continue

            item_match = _LIST_ITEM.match(line)

            if not item_match:

                # La línea no pertenece a la lista.
                # Recuperamos los saltos de línea pendientes.
                remaining.extend(
                    pending_blank_lines
                )

                pending_blank_lines.clear()

                # Conservamos esta línea y todo lo posterior.
                remaining.extend(
                    lines[index:]
                )

                break

            code = item_match.group(1).strip()
            label = item_match.group(2).strip()

            values.append(
                AllowedValue(
                    code=code,
                    label=label,
                )
            )

            pending_blank_lines.clear()

        else:

            # Si llegamos al final, las líneas vacías pendientes
            # no pertenecen a ningún elemento.
            remaining.extend(
                pending_blank_lines
            )

        if values:
            rule.allowed_values = _dedupe(
                values,
                rule,
            )

        return "\n".join(remaining)

    # ========================================================
    # DETECCIÓN DE RESPALDO
    # ========================================================

    def _extract_fallback(
        self,
        text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Detecta una lista sin frase introductoria.

        Requiere al menos tres líneas consecutivas que cumplan
        el patrón más estricto de código-descripción.

        Si existen varias secuencias, selecciona la más larga.

        El texto anterior y posterior a la lista se conserva
        para los demás reconocedores.
        """

        lines = text.split("\n")

        best_start: int | None = None
        best_end: int | None = None

        run_start: int | None = None

        # Se agrega un centinela para cerrar una secuencia
        # que llegue hasta la última línea.
        for index, line in enumerate(lines + [""]):

            matches = bool(
                _FALLBACK_LIST_ITEM.fullmatch(line.strip())
            )

            if matches:

                if run_start is None:
                    run_start = index

                continue

            if run_start is not None:

                run_length = index - run_start

                if (
                    run_length >= _MIN_FALLBACK_RUN
                    and (
                        best_start is None
                        or run_length > best_end - best_start
                    )
                ):

                    best_start = run_start
                    best_end = index

                run_start = None

        # No se encontró ninguna secuencia suficientemente larga.
        if best_start is None:
            return text

        # ----------------------------------------------------
        # CONSTRUIR VALORES
        # ----------------------------------------------------

        values: list[AllowedValue] = []

        for line in lines[best_start:best_end]:

            item_match = _FALLBACK_LIST_ITEM.fullmatch(
                line.strip()
            )

            # Esta comprobación protege el código frente a
            # cambios futuros en el patrón.
            if item_match is None:
                continue

            code = item_match.group(1).strip()
            label = item_match.group(2).strip()

            values.append(
                AllowedValue(
                    code=code,
                    label=label,
                )
            )

        if not values:
            return text

        rule.allowed_values = _dedupe(
            values,
            rule,
        )

        # ----------------------------------------------------
        # CONSERVAR EL TEXTO RESTANTE
        # ----------------------------------------------------

        remaining = (
            lines[:best_start]
            + lines[best_end:]
        )

        return "\n".join(remaining)

    # ========================================================
    # UTILIDAD PARA UNIR TEXTO RESTANTE
    # ========================================================

    @staticmethod
    def _join_remaining(
        before: str,
        after: str,
    ) -> str:
        """
        Une el texto anterior y posterior a la lista.

        Evita generar separadores innecesarios cuando uno
        de los fragmentos está vacío.
        """

        parts = [
            part.strip()
            for part in (before, after)
            if part and part.strip()
        ]

        return "\n".join(parts)


# ============================================================
# ELIMINACIÓN DE DUPLICADOS
# ============================================================

def _dedupe(
    values: list[AllowedValue],
    rule: ValidationRule,
) -> list[AllowedValue]:
    """
    Elimina códigos duplicados conservando la primera aparición.

    Casos:

        Código repetido con misma descripción:
            Se elimina silenciosamente.

        Código repetido con descripción diferente:
            Se conserva la primera definición y se registra
            la inconsistencia para revisión manual.
    """

    seen: dict[str, str] = {}

    deduped: list[AllowedValue] = []

    for value in values:

        code = value.code.strip()
        label = value.label.strip()

        previous_label = seen.get(code)

        # Primera aparición del código.
        if previous_label is None:

            seen[code] = label

            deduped.append(
                AllowedValue(
                    code=code,
                    label=label,
                )
            )

            continue

        # Duplicado exacto: no es necesario repetirlo.
        if previous_label == label:
            continue

        # Mismo código con descripción diferente.
        fragment = (
            f"Código '{code}' con descripciones diferentes: "
            f"'{previous_label}' y '{label}'."
        )

        if fragment not in rule.unparsed_fragments:
            rule.unparsed_fragments.append(
                fragment
            )

    return deduped
