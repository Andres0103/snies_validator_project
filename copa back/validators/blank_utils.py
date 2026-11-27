from typing import Any


def is_blank(value: Any) -> bool:
    """
    Determina si un valor debe considerarse vacío.

    Reconoce:
    - None
    - Cadenas vacías
    - Cadenas compuestas por espacios
    - El marcador literal '(en blanco)'
    """

    if value is None:
        return True

    if isinstance(value, str):
        normalized_value = value.strip().casefold()

        return normalized_value == "" or normalized_value == "(en blanco)"

    return False