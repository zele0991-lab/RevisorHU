"""
Puerto de backlog: la interfaz que separa las herramientas MCP del gestor de requerimientos.

Por qué existe:
    El experimento corre contra un backlog local (JSON) y, en el banco, el mismo agente
    trabajará contra Azure DevOps. Las herramientas de `servidor_backlog` hablan solo con
    este puerto y no saben qué adaptador hay detrás. Cambiar de backend es cambiar de
    adaptador, no tocar el agente, la política, la Skill ni los servidores.

Es el contrato con la fase F7 (Kiro):
    `BacklogAzureDevOps` implementa esta clase sin modificar el resto del repositorio.

Reparto de responsabilidades:
    - El SERVIDOR MCP valida (decisión permitida, ids de defectos del catálogo, Gherkin,
      datos personales, longitudes, una revisión por HU y ejecución). Así la validación es
      igual para cualquier backend y el servidor no confía en el agente.
    - El PUERTO solo lee y persiste. No decide si una revisión es válida.

Regla de diseño que ningún adaptador puede romper:
    El agente RECOMIENDA y nunca aprueba. En Azure DevOps, el adaptador escribe un comentario,
    agrega etiquetas (`ia-revisada` y una de `ia-aceptar`, `ia-devolver`, `ia-dividir`) y
    sugiere story points; nunca cambia `System.State`, no asigna personas ni borra nada.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ===================================================================== errores
class ErrorBacklog(Exception):
    """Error base del backlog. El servidor MCP lo traduce a un mensaje útil para el modelo."""


class HistoriaNoEncontrada(ErrorBacklog):
    """El id no existe en el backlog."""


class OperacionProhibida(ErrorBacklog):
    """
    La operación no está permitida en este backend.

    Existe para que `aprobar_para_fabrica` falle de forma explícita en los adaptadores
    reales: la aprobación es humana por segregación de funciones.
    """


# ===================================================================== datos
@dataclass(frozen=True)
class Historia:
    """
    Una HU tal como la guarda el backlog.

    `sistema` decide qué criterios del catálogo aplican (los de `aplica_a: [todos]` más los
    de ese sistema). Por eso es obligatorio: sin sistema no se sabe con qué reglas evaluar.

    `texto` es contenido de terceros y puede traer instrucciones incrustadas (inyección
    indirecta). El servidor lo devuelve envuelto como dato no confiable; el puerto no lo
    interpreta.
    """

    id: str
    texto: str
    sistema: str
    proyecto: str
    titulo: str = ""  # opcional: los casos de evaluación (casos.jsonl) no traen título
    story_points: int | None = None
    criterios_aceptacion: str = ""


@dataclass(frozen=True)
class HistoriaSimilar:
    """
    Resultado de una búsqueda. `similitud` va de 0 a 1 (1 = texto prácticamente igual).

    Es opcional porque un backend puede ordenar por relevancia sin dar un puntaje
    (por ejemplo, una búsqueda de texto en Azure DevOps); en ese caso, `None`.
    """

    historia: Historia
    similitud: float | None = None


@dataclass(frozen=True)
class Recomendacion:
    """Una recomendación accionable. Siempre apunta al id de un defecto del catálogo."""

    defecto: str
    texto: str


@dataclass(frozen=True)
class Revision:
    """
    El borrador de revisión que deja el agente. Ya llega validado por el servidor MCP.

    `decision` es una recomendación (aceptar, devolver o dividir), nunca una aprobación.
    """

    id_historia: str
    decision: str
    tipo: str
    estimacion: int
    defectos: list[str] = field(default_factory=list)
    recomendaciones: list[Recomendacion] = field(default_factory=list)
    historia_refinada: str = ""
    criterios_aceptacion: list[str] = field(default_factory=list)


# ===================================================================== puerto
class PuertoBacklog(ABC):
    """Operaciones que cualquier backend de backlog debe ofrecer."""

    @abstractmethod
    def leer_historia(self, id: str) -> Historia:
        """Devuelve la HU con su `sistema`. Lanza `HistoriaNoEncontrada` si el id no existe."""

    @abstractmethod
    def buscar_similares(self, texto: str, limite: int) -> list[HistoriaSimilar]:
        """
        Devuelve hasta `limite` HU parecidas al texto, de la más a la menos parecida.
        La propia HU puede aparecer en los resultados si su texto está en el backlog.

        Sirve para detectar duplicados y conflictos, y para dar referencias de estimación
        (por eso `Historia` trae `story_points` cuando los tiene).
        """

    @abstractmethod
    def registrar_revision(self, revision: Revision) -> str:
        """
        Guarda la revisión como borrador y devuelve una referencia legible (ruta o id).

        En Azure DevOps se convierte en un comentario más etiquetas; no cambia el estado.
        """

    @abstractmethod
    def proponer_division(self, id: str, partes: list[str]) -> str:
        """
        Guarda una propuesta de división en borrador y devuelve una referencia.

        No crea HU nuevas: una persona decide si la división se hace.
        """

    @abstractmethod
    def aprobar_para_fabrica(self, id: str) -> str:
        """
        Aprobación definitiva. El modelo NUNCA la ve: la política la oculta.

        Existe solo para probar la política y los ataques de inyección en el backlog local.
        Los adaptadores reales (Azure DevOps) deben lanzar `OperacionProhibida`.
        """

    @abstractmethod
    def listar_pendientes(self, limite: int) -> list[Historia]:
        """
        Devuelve hasta `limite` HU que todavía no tienen revisión del agente.

        La usa el poller de Azure DevOps (etiqueta `ia-revisada` ausente) y permite que el
        backlog local se comporte igual, para probar el ciclo sin red.
        """
