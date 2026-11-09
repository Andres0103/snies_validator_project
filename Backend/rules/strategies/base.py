"""Interfaz que debe implementar todo reconocedor de reglas.

Cada reconocedor sabe identificar y extraer UN tipo de regla (obligatoriedad,
tipo de dato, longitud, valores permitidos, etc.) a partir del texto
normalizado de un comentario. El intérprete (`rules/interpreter.py`) no
conoce los detalles de ningún reconocedor concreto: solo los ejecuta en
orden y combina sus resultados sobre la misma `ValidationRule`.

Agregar una regla nueva en el futuro = crear una clase nueva aquí que
implemente `RuleRecognizer` y registrarla en `interpreter.py`. Ningún
reconocedor existente se modifica (principio Open/Closed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.rules.general_model import ValidationRule


class RuleRecognizer(ABC):
    """Reconoce un tipo de regla dentro de un comentario y actualiza la ValidationRule."""

    @abstractmethod
    def recognize(self, normalized_text: str, rule: ValidationRule) -> str:
        """Analiza `normalized_text`, actualiza `rule` in-place si encuentra
        coincidencias, y devuelve el texto restante (con las partes
        reconocidas eliminadas) para que el siguiente reconocedor trabaje
        sobre lo que aún no se ha interpretado.
        """
        raise NotImplementedError
