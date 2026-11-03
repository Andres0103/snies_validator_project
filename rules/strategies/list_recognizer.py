from __future__ import annotations

import re

from rules.models import AllowedValue, ValidationRule
from rules.strategies.base import RuleRecognizer

# Marca el inicio del bloque de valores permitidos. Se han visto ambas
# variantes en plantillas reales: "valores válidos son" y "valores posibles son".
_LIST_MARKER = re.compile(
    r"los?\s+valores?\s+(v[aá]lidos|posibles)\s+son\s*:?", re.IGNORECASE
)

# Una línea de la forma "1 Sector Empresarial", "CC  Cédula de ciudadanía",
# "6.Todas las anteriores", "9\t Formación...". El código es corto
# (números o siglas de máx. 4 caracteres); el resto de la línea es la
# etiqueta.
_LIST_ITEM = re.compile(r"^\s*([A-Za-z0-9]{1,4})[\.\)\s]+(.+?)\s*$")


class ListRecognizer(RuleRecognizer):
    """Extrae la lista código→descripción de un bloque 'Los valores válidos son:'.

    Además, como respaldo, detecta bloques de lista SIN esa frase exacta
    (ej. "Registrar la información para cada una de las 7 IES:\n1201
    Medellín\n..."), buscando una racha de al menos 2 líneas consecutivas
    que calcen con el patrón código+etiqueta. El MEN no siempre usa la
    misma redacción para introducir una lista, y una lista no detectada
    no debe pasar como si el campo no tuviera restricciones.
    """

    def recognize(self, normalized_text: str, rule: ValidationRule) -> str:
        marker_match = _LIST_MARKER.search(normalized_text)
        if marker_match:
            before = normalized_text[: marker_match.start()]
            block = normalized_text[marker_match.end():]
            return self._extract_from_block(before, block, rule)

        return self._extract_fallback(normalized_text, rule)

    def _extract_from_block(self, before: str, block: str, rule: ValidationRule) -> str:
        values: list[AllowedValue] = []
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            item_match = _LIST_ITEM.match(line)
            if item_match:
                code, label = item_match.group(1), item_match.group(2).strip()
                values.append(AllowedValue(code=code, label=label))
            else:
                # Línea que no calza con el patrón código+etiqueta: se
                # conserva sin interpretar para revisión manual, en vez de
                # descartarla silenciosamente.
                rule.unparsed_fragments.append(line)

        rule.allowed_values = _dedupe(values)
        return before

    def _extract_fallback(self, text: str, rule: ValidationRule) -> str:
        """Detecta listas sin la frase marcadora explícita.

        Exige una racha de al menos 3 líneas consecutivas (no 2), porque
        con solo 2 es fácil que dos oraciones normales coincidan por
        accidente (ej. "El código 170 es para Colombia." + "Si desea otro
        país..." calzan como código="El"/código="Si" si el umbral fuera
        más bajo). Las listas reales observadas en las plantillas del MEN
        siempre tienen 3 o más valores.
        """
        lines = text.split("\n")
        MIN_RUN = 3
        best_start, best_end = None, None
        run_start = None
        for i, line in enumerate(lines + [""]):  # centinela final para cerrar la última racha
            matches = bool(_LIST_ITEM.match(line.strip())) and line.strip()
            if matches:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    run_len = i - run_start
                    if run_len >= MIN_RUN and (best_start is None or run_len > (best_end - best_start)):
                        best_start, best_end = run_start, i
                run_start = None

        if best_start is None:
            return text

        values = []
        for line in lines[best_start:best_end]:
            item_match = _LIST_ITEM.match(line.strip())
            code, label = item_match.group(1), item_match.group(2).strip()
            values.append(AllowedValue(code=code, label=label))
        rule.allowed_values = _dedupe(values)

        remaining = lines[:best_start] + lines[best_end:]
        return "\n".join(remaining)


def _dedupe(values: list[AllowedValue]) -> list[AllowedValue]:
    seen = set()
    deduped = []
    for v in values:
        if v.code not in seen:
            seen.add(v.code)
            deduped.append(v)
    return deduped
