
"""
Interfaz base para todos los reconocedores de reglas.

Cada reconocedor identifica un tipo de instrucción dentro
del comentario de un encabezado Excel y actualiza una instancia
compartida de ValidationRule.

Ejemplos de reconocedores:
    - ListRecognizer
    - RequiredRecognizer
    - DatatypeRecognizer

Responsabilidades del reconocedor:
    1. Recibir el texto pendiente de interpretación.
    2. Identificar únicamente las instrucciones de su competencia.
    3. Actualizar la instancia recibida de ValidationRule.
    4. Devolver el texto que todavía no ha sido interpretado.

Restricciones:
    - No debe crear otra instancia de ValidationRule.
    - No debe ejecutar otros reconocedores.
    - No debe descartar texto que no haya interpretado.
    - No debe modificar directamente la configuración externa.
    - No debe decidir cómo se ejecutan las validaciones.

El orden de ejecución y la coordinación entre reconocedores
son responsabilidad de interpreter.py.

Para agregar un nuevo tipo de reconocimiento se crea una
clase que implemente esta interfaz y se registra en el
intérprete.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from rules.general_model import ValidationRule


class RuleRecognizer(ABC):
    """
    Contrato común de los reconocedores de reglas.
    """

    @abstractmethod
    def recognize(
        self,
        normalized_text: str,
        rule: ValidationRule,
    ) -> str:
        """
        Analiza el texto pendiente y actualiza la regla.

        Parámetros:
            normalized_text:
                Fragmento del comentario que todavía no ha sido
                interpretado por los reconocedores anteriores.

            rule:
                Instancia compartida de ValidationRule.
                El reconocedor modifica sus atributos directamente.

        Retorna:
            str:
                Texto que permanece sin interpretar y que será
                entregado al siguiente reconocedor.

        Importante:
            El reconocedor debe conservar cualquier fragmento
            que no pertenezca a su responsabilidad.

            Si no encuentra ninguna coincidencia, debe devolver
            el texto recibido sin alteraciones.
        """
        raise NotImplementedError(
            "Cada reconocedor debe implementar recognize()."
        )
