"""
Fuente de reglas: lo que el servidor de backlog necesita saber del catálogo.

Por qué una interfaz y no una importación directa del catálogo:
    `servidor_backlog` valida los defectos y el tipo de una revisión contra el catálogo,
    pero no debe conocer cómo se carga ni dónde vive. Con esta interfaz:
      - las pruebas usan una fuente de reglas falsa, sin archivos;
      - el catálogo real (`catalogo.Catalogo`) la implementa;
      - ningún id de criterio ni tipo de HU queda escrito en el código del servidor.
"""

from __future__ import annotations

from typing import Protocol


class FuenteReglas(Protocol):
    """Consultas mínimas sobre el catálogo que hace el servidor de backlog."""

    def tipos_hu(self) -> list[str]:
        """Tipos de HU válidos (lista cerrada, definida en el catálogo)."""
        ...

    def formato_criterios_aceptacion(self) -> str:
        """Formato exigido a los criterios de aceptación: 'lista' o 'gherkin' (definido en el catálogo)."""
        ...

    def ids_defectos_aplicables(self, sistema: str) -> set[str]:
        """Ids de criterios ACTIVOS que aplican al sistema (`aplica_a` = todos o ese sistema)."""
        ...
