"""
Estructuras de datos centrales del motor de validación.

Todo el sistema gira alrededor de `ValidationRule`: la representación
normalizada de lo que un comentario en lenguaje natural (o una regla de
negocio del manual del MEN) significa para un campo determinado.

Ningún módulo de negocio (parser, escritor de Excel, reportes) debe
saber "cómo se ve" un comentario; solo trabajan sobre esta estructura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DataType(str, Enum):
    TEXT = "text"                # alfabético / alfanumérico sin más precisión
    ALPHANUMERIC = "alphanumeric"
    ALPHABETIC = "alphabetic"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    UNKNOWN = "unknown"


@dataclass
class AllowedValue:
    """Un par código/descripción de una lista de valores válidos.

    Ej.: '1 Sector Empresarial' -> code='1', label='Sector Empresarial'
    """
    code: str
    label: str

    @property
    def display(self) -> str:
        return f"{self.code} {self.label}".strip()


@dataclass
class ConditionalRequirement:
    """Representa reglas como 'Obligatorio para fuente internacional'.

    No podemos resolver automáticamente a qué columna exacta se refiere
    ('fuente internacional') sin contexto de la hoja completa, así que
    se guarda el texto original para que una capa posterior (o el propio
    generador de reportes) pueda mostrarlo como advertencia al usuario.
    """
    raw_text: str


@dataclass
class ValidationRule:
    """Estructura interna de reglas para una columna.

    Es la salida canónica del intérprete de comentarios y la entrada
    canónica del constructor de validaciones de Excel.
    """
    column_name: str
    required: bool = False
    conditional_requirement: Optional[ConditionalRequirement] = None
    datatype: DataType = DataType.UNKNOWN
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    exact_length: Optional[int] = None
    allowed_values: list[AllowedValue] = field(default_factory=list)
    date_formats: list[str] = field(default_factory=list)
    description: str = ""
    raw_comment: str = ""
    unparsed_fragments: list[str] = field(default_factory=list)

    @property
    def has_allowed_values(self) -> bool:
        return len(self.allowed_values) > 0

    @property
    def needs_manual_review(self) -> bool:
        """True si algo del comentario quedó sin poder interpretarse.

        Dos casos: (a) quedó un fragmento de texto que ningún reconocedor
        entendió, o (b) no se logró determinar NINGÚN tipo de dato ni
        lista de valores (columna efectivamente sin restricciones), lo
        cual casi siempre significa que el comentario tiene una redacción
        que el catálogo de patrones todavía no cubre, no que el campo en
        verdad no tenga reglas.
        """
        if self.unparsed_fragments:
            return True
        if self.datatype == DataType.UNKNOWN and not self.allowed_values:
            return True
        return False
