
"""
Reconocedor de listas de valores permitidos.

Responsabilidades:
    - Detectar listas introducidas por frases explÃ­citas.
    - Detectar listas sin frase introductoria mediante un mecanismo
      de respaldo conservador.
    - Convertir cada elemento en AllowedValue.
    - Detectar cÃ³digos duplicados e inconsistencias.
    - Devolver el texto que no pertenece a la lista para que
      los siguientes reconocedores puedan procesarlo.

Principio importante:

    Este reconocedor solamente debe consumir las lÃ­neas que
    realmente pertenecen a una lista.

    Nunca debe descartar las instrucciones restantes del comentario.
"""

from __future__ import annotations

import re

from rules.general_model import (
    AllowedValue,
    ValidationRule,
)

from rules.strategies.base import RuleRecognizer


# ============================================================
# PATRONES
# ============================================================

# Detecta frases como:
#
# Los valores vÃ¡lidos son:
# Los valores posibles son:
# El valor vÃ¡lido es:
#
# Se aceptan las formas singular y plural.
_LIST_MARKER = re.compile(
    r"\b(?:los?\s+valores?|el\s+valor)\s+"
    r"(?:v[aÃ¡]lidos?|posibles?)\s+"
    r"(?:son|es)\s*:?",
    re.IGNORECASE,
)


# Lista explÃ­cita:
#
# 1 Sector empresarial
# CC CÃ©dula de ciudadanÃ­a
# 6. Todas las anteriores
# A01 DescripciÃ³n
#
# Se permite un cÃ³digo alfanumÃ©rico corto.
# La interpretaciÃ³n estÃ¡ respaldada por la frase introductoria.
_LIST_ITEM = re.compile(
    r"^\s*([A-Za-z0-9]{1,4})[\.\)\s]+(.+?)\s*$"
)


# Lista detectada por respaldo:
#
# AquÃ­ exigimos cÃ³digos numÃ©ricos, alfabÃ©ticos en mayÃºsculas
# o alfanumÃ©ricos que contengan al menos un nÃºmero.
#
# Es mÃ¡s restrictivo que el patrÃ³n explÃ­cito para evitar
# interpretar palabras normales como cÃ³digos.
_FALLBACK_LIST_ITEM = re.compile(
    r"^\s*("
    r"\d{1,4}"
    r"|[A-Z]{1,4}"
    r"|(?=[A-Za-z0-9]{1,4}\b)"
    r"(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{1,4}"
    r")[\.\)\s]+(.+?)\s*$"
)


# Cantidad mÃ­nima de lÃ­neas consecutivas para activar
# la detecciÃ³n de respaldo.
_MIN_FALLBACK_RUN = 3


# ============================================================
# RECONOCEDOR
# ============================================================

class ListRecognizer(RuleRecognizer):
    """
    Extrae listas cÃ³digo-descripciÃ³n de comentarios Excel.

    Trabaja en dos modalidades:

        1. Lista explÃ­cita:
           El comentario contiene una frase introductoria
           como "Los valores vÃ¡lidos son:".

        2. Lista por respaldo:
           No existe frase introductoria, pero se encuentra
           una secuencia de al menos tres lÃ­neas con formato
           cÃ³digo-descripciÃ³n.
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
        # LISTA EXPLÃCITA
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
    # EXTRACCIÃ“N DE LISTA EXPLÃCITA
    # ========================================================

    def _extract_from_block(
        self,
        block: str,
        rule: ValidationRule,
    ) -> str:
        """
        Extrae una lista explÃ­cita sin consumir las instrucciones
        que aparezcan antes o despuÃ©s de ella.

        La lista comienza en la primera lÃ­nea que coincide
        con el patrÃ³n cÃ³digo-descripciÃ³n.

        Una vez iniciada, se aceptan lÃ­neas vacÃ­as entre
        elementos.

        Cuando aparece una lÃ­nea que no corresponde a un
        elemento de lista, se considera que terminÃ³ el bloque.
        Esa lÃ­nea y las siguientes se conservan.
        """

        lines = block.split("\n")

        values: list[AllowedValue] = []

        remaining: list[str] = []

        list_started = False

        # Conserva temporalmente los saltos de lÃ­nea entre
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

            # Una vez iniciada la lista, permitimos lÃ­neas
            # vacÃ­as entre sus elementos.
            if not stripped_line:

                pending_blank_lines.append(line)
                continue

            item_match = _LIST_ITEM.match(line)

            if not item_match:

                # La lÃ­nea no pertenece a la lista.
                # Recuperamos los saltos de lÃ­nea pendientes.
                remaining.extend(
                    pending_blank_lines
                )

                pending_blank_lines.clear()

                # Conservamos esta lÃ­nea y todo lo posterior.
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

            # Si llegamos al final, las lÃ­neas vacÃ­as pendientes
            # no pertenecen a ningÃºn elemento.
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
    # DETECCIÃ“N DE RESPALDO
    # ========================================================

    def _extract_fallback(
        self,
        text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Detecta una lista sin frase introductoria.

        Requiere al menos tres lÃ­neas consecutivas que cumplan
        el patrÃ³n mÃ¡s estricto de cÃ³digo-descripciÃ³n.

        Si existen varias secuencias, selecciona la mÃ¡s larga.

        El texto anterior y posterior a la lista se conserva
        para los demÃ¡s reconocedores.
        """

        lines = text.split("\n")

        best_start: int | None = None
        best_end: int | None = None

        run_start: int | None = None

        # Se agrega un centinela para cerrar una secuencia
        # que llegue hasta la Ãºltima lÃ­nea.
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

        # No se encontrÃ³ ninguna secuencia suficientemente larga.
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

            # Esta comprobaciÃ³n protege el cÃ³digo frente a
            # cambios futuros en el patrÃ³n.
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
        de los fragmentos estÃ¡ vacÃ­o.
        """

        parts = [
            part.strip()
            for part in (before, after)
            if part and part.strip()
        ]

        return "\n".join(parts)


# ============================================================
# ELIMINACIÃ“N DE DUPLICADOS
# ============================================================

def _dedupe(
    values: list[AllowedValue],
    rule: ValidationRule,
) -> list[AllowedValue]:
    """
    Elimina cÃ³digos duplicados conservando la primera apariciÃ³n.

    Casos:

        CÃ³digo repetido con misma descripciÃ³n:
            Se elimina silenciosamente.

        CÃ³digo repetido con descripciÃ³n diferente:
            Se conserva la primera definiciÃ³n y se registra
            la inconsistencia para revisiÃ³n manual.
    """

    seen: dict[str, str] = {}

    deduped: list[AllowedValue] = []

    for value in values:

        code = value.code.strip()
        label = value.label.strip()

        previous_label = seen.get(code)

        # Primera apariciÃ³n del cÃ³digo.
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

        # Mismo cÃ³digo con descripciÃ³n diferente.
        fragment = (
            f"CÃ³digo '{code}' con descripciones diferentes: "
            f"'{previous_label}' y '{label}'."
        )

        if fragment not in rule.unparsed_fragments:
            rule.unparsed_fragments.append(
                fragment
            )

    return deduped

