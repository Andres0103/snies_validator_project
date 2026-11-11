
"""
Interfaz de compatibilidad para cargar reglas de negocio.

La carga y combinación de configuraciones es responsabilidad
de config_loader.py.

Este módulo se conserva para evitar romper los componentes
que todavía importan load_business_rules().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rules.config_loader import load_rule_configuration


def load_business_rules(
    template_name: str | None = None,
    rules_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Carga las reglas de negocio mediante el cargador central.

    Parámetros:
        template_name:
            Nombre de la plantilla SNIES.

            Si se proporciona, carga las reglas comunes y
            las específicas de esa plantilla.

            Si es None, utiliza la configuración legacy.

        rules_dir:
            Directorio de configuración. Permite utilizar
            configuraciones alternativas.

    Retorna:
        Diccionario consolidado de reglas de negocio.
    """

    configuration = load_rule_configuration(
        template_name=template_name,
        rules_dir=rules_dir,
    )

    return configuration.business_rules
