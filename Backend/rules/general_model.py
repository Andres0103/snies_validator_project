
"""
Estructuras de datos centrales del motor de validación.

Todo el sistema trabaja sobre ValidationRule: la representación
normalizada de las restricciones identificadas para un campo.

Los módulos de interpretación, validación, generación de Excel
y reportes deben utilizar estas estructuras como contrato común.

Este módulo no interpreta comentarios ni ejecuta validaciones.
Únicamente define las estructuras de información.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DataType(str, Enum):
    """
    Tipos de datos reconocidos por el motor.

    TEXT:
        Texto sin una clasificación más específica.

    ALPHANUMERIC:
        Texto que puede contener letras y números.

    ALPHABETIC:
        Texto compuesto por caracteres alfabéticos.

    INTEGER:
        Número entero.

    DECIMAL:
        Número que admite parte decimal.

    DATE:
        Fecha.

    UNKNOWN:
        Tipo de dato que todavía no pudo determinarse.
    """

    TEXT = "text"
    ALPHANUMERIC = "alphanumeric"
    ALPHABETIC = "alphabetic"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    UNKNOWN = "unknown"


@dataclass
class AllowedValue:
    """
    Representa un valor permitido dentro de un catálogo.

    Ejemplo:

        Código: 1
        Descripción: Sector empresarial

        code = "1"
        label = "Sector empresarial"

    El código y la descripción se almacenan como texto
    para conservar ceros iniciales y evitar conversiones
    numéricas que puedan alterar los identificadores.
    """

    code: str
    label: str

    @property
    def display(self) -> str:
        """
        Representación legible del valor permitido.

        Ejemplo:
            "1 Sector empresarial"
        """

        return f"{self.code} {self.label}".strip()


@dataclass
class ConditionalRequirement:
    """
    Representa una condición de obligatoriedad.

    Ejemplo:

        Obligatorio para fuente internacional.

    Actualmente se conserva el texto original porque el motor
    todavía necesita identificar las columnas relacionadas
    y determinar cómo evaluar la condición.

    Este objeto representa una condición identificada,
    no una condición ejecutable.
    """

    raw_text: str


@dataclass
class ValidationRule:
    """
    Representación canónica de las reglas de una columna.

    Es la salida del intérprete de comentarios y la entrada
    para los validadores y el constructor de validaciones Excel.

    Importante:

        required=False significa que la regla no está marcada
        como obligatoria.

        No significa necesariamente que el comentario haya
        declarado explícitamente que el campo es opcional.
    """

    # Nombre de la columna en la plantilla.
    column_name: str

    # Indica si el campo está marcado como obligatorio.
    required: bool = False

    # Condición que determina cuándo debe diligenciarse.
    conditional_requirement: Optional[
        ConditionalRequirement
    ] = None

    # Tipo de dato reconocido.
    datatype: DataType = DataType.UNKNOWN

    # Longitud máxima permitida.
    max_length: Optional[int] = None

    # Longitud mínima permitida.
    min_length: Optional[int] = None

    # Longitud exacta requerida.
    exact_length: Optional[int] = None

    # Valores permitidos, cuando existe una lista o catálogo.
    allowed_values: list[AllowedValue] = field(
        default_factory=list
    )
    
    # Valores expresamente excluidos para esta columna.
    excluded_values: list[str] = field(
        default_factory=list
    )

    # Formatos de fecha aceptados.
    date_formats: list[str] = field(
        default_factory=list
    )

    # Descripción o instrucciones que no fueron interpretadas
    # como restricciones estructuradas.
    description: str = ""

    # Comentario original del encabezado Excel.
    raw_comment: str = ""

    # Fragmentos que necesitan revisión manual.
    unparsed_fragments: list[str] = field(
        default_factory=list
    )

    @property
    def has_allowed_values(self) -> bool:
        """
        Indica si la regla tiene valores permitidos.
        """

        return bool(self.allowed_values)

    @property
    def needs_manual_review(self) -> bool:
        """
        Indica si existen elementos que requieren revisión.

        Se consideran dos situaciones:

            1. Hay fragmentos que ningún reconocedor pudo
               interpretar.

            2. No se pudo determinar un tipo de dato ni
               una lista de valores permitidos.

        Esta propiedad es una señal general de revisión,
        no una garantía de que todas las restricciones hayan
        sido interpretadas correctamente.
        """

        if self.unparsed_fragments:
            return True

        if (
            self.datatype == DataType.UNKNOWN
            and not self.allowed_values
        ):
            return True

        return False
