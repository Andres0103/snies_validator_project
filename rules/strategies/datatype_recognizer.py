from __future__ import annotations

import re

from rules.models import DataType, ValidationRule
from rules.strategies.base import RuleRecognizer

# Ej.: "alfanumérico (30)", "numérico (4)", "alfabético (2)", "numerico(15)"
# (acepta variantes con y sin tilde, ambas aparecen en plantillas reales)
_TYPE_WITH_LENGTH = re.compile(
    r"\b(alfanum[eé]ric[oa]|alfab[eé]tic[oa]|num[eé]ric[oa]|entero|decimal|texto)\s*"
    r"\(\s*(\d+)\s*\)",
    re.IGNORECASE,
)

# Fecha con formato explícito entre paréntesis, ej.:
# "tipo fecha (dd/mm/aaaa o dd-mm-aaaa)"
_DATE_WITH_FORMAT = re.compile(
    r"\btipo\s+fecha\s*\(([^)]*)\)", re.IGNORECASE
)
_DATE_BARE = re.compile(r"\btipo\s+fecha\b|\bfecha\b", re.IGNORECASE)

_TYPE_KEYWORD_TO_ENUM = {
    "alfanumerico": DataType.ALPHANUMERIC,
    "alfanumerica": DataType.ALPHANUMERIC,
    "alfanumérico": DataType.ALPHANUMERIC,
    "alfanumérica": DataType.ALPHANUMERIC,
    "alfabetico": DataType.ALPHABETIC,
    "alfabetica": DataType.ALPHABETIC,
    "alfabético": DataType.ALPHABETIC,
    "alfabética": DataType.ALPHABETIC,
    "numerico": DataType.DECIMAL,   # ver nota de diseño en el docstring del módulo
    "numerica": DataType.DECIMAL,
    "numérico": DataType.DECIMAL,
    "numérica": DataType.DECIMAL,
    "entero": DataType.INTEGER,
    "decimal": DataType.DECIMAL,
    "texto": DataType.TEXT,
}

_DDMMYYYY_TOKEN = re.compile(r"dd[/\-.]mm[/\-.]aaaa|dd[/\-.]mm[/\-.]yyyy", re.IGNORECASE)


class DatatypeRecognizer(RuleRecognizer):
    """Detecta tipo de dato y, cuando viene junto entre paréntesis, la longitud máxima.

    Nota de diseño: el manual del MEN usa "numérico" indistintamente para
    enteros (AÑO, SEMESTRE) y para valores monetarios que en la práctica
    pueden traer decimales (VALOR, VLR_FINANCIACION_*). Para no rechazar
    datos válidos, "numérico" se interpreta como DECIMAL (más permisivo,
    también acepta enteros) salvo que el comentario diga explícitamente
    "entero".
    """

    def recognize(self, normalized_text: str, rule: ValidationRule) -> str:
        text = normalized_text

        date_fmt_match = _DATE_WITH_FORMAT.search(text)
        if date_fmt_match:
            rule.datatype = DataType.DATE
            formats_raw = date_fmt_match.group(1)
            formats = []
            for token in re.split(r"\bo\b|,", formats_raw):
                token = token.strip()
                if _DDMMYYYY_TOKEN.search(token):
                    sep = "/" if "/" in token else "-"
                    formats.append(f"%d{sep}%m{sep}%Y")
            rule.date_formats = formats or ["%d-%m-%Y", "%d/%m/%Y"]
            return text[: date_fmt_match.start()] + text[date_fmt_match.end():]

        type_len_match = _TYPE_WITH_LENGTH.search(text)
        if type_len_match:
            keyword = type_len_match.group(1).lower()
            length = int(type_len_match.group(2))
            rule.datatype = _TYPE_KEYWORD_TO_ENUM.get(keyword, DataType.UNKNOWN)
            rule.max_length = length
            return text[: type_len_match.start()] + text[type_len_match.end():]

        if _DATE_BARE.search(text):
            rule.datatype = DataType.DATE
            rule.date_formats = ["%d-%m-%Y", "%d/%m/%Y"]
            text = _DATE_BARE.sub("", text, count=1)

        return text
