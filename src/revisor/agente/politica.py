"""
Política de permisos del host.

Por qué vive en el HOST y no en el servidor ni en el modelo:
    El servidor expone una herramienta destructiva (`aprobar_para_fabrica`) y el modelo
    podría querer usarla si una HU envenenada se lo pide. Ninguno de los dos decide: decide
    la política, que es código y configuración que el modelo no puede cambiar.

Orden de evaluación (igual que el kit): ocultar > denegar > confirmar > permitir > por_defecto.

Perfiles por backend:
    En el experimento (backlog local) las escrituras en borrador van en permitir: hay
    cientos de ejecuciones sin una persona delante y el backlog es desechable. Con Azure
    DevOps van en confirmar (D-008). El perfil se elige en la configuración, no en el prompt.

Topes por herramienta (D-019):
    Se cuentan solo las llamadas que el servidor ACEPTÓ. Si se contaran también los rechazos
    de validación, un primer `registrar_revision` con un error dejaría al agente sin poder
    corregirlo, y el tope dejaría de significar "una revisión por ejecución".
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

LISTAS = ("ocultar", "denegar", "confirmar", "permitir")
DECISIONES = ("permitir", "confirmar", "denegar")


class PoliticaInvalida(Exception):
    pass


class Politica:
    def __init__(self, datos: dict, backend: str):
        perfiles = datos.get("por_backend", {})
        if backend not in perfiles:
            raise PoliticaInvalida(f"backend '{backend}' sin perfil en la política; perfiles: {', '.join(perfiles)}")
        if datos.get("por_defecto") not in DECISIONES:
            raise PoliticaInvalida("por_defecto debe ser permitir, confirmar o denegar")
        self.backend = backend
        self.por_defecto = datos["por_defecto"]
        perfil = perfiles[backend]
        # El perfil del backend SUMA patrones a cada lista; no reemplaza las reglas generales.
        self.reglas = {lista: [*datos.get(lista, []), *perfil.get(lista, [])] for lista in LISTAS}
        self.topes: dict[str, int] = dict(datos.get("max_llamadas_por_herramienta", {}))
        self.aceptadas: dict[str, int] = {}

    @classmethod
    def desde_archivo(cls, ruta: Path | str, backend: str) -> "Politica":
        return cls(json.loads(Path(ruta).read_text(encoding="utf-8")), backend)

    def _coincide(self, nombre: str, lista: str) -> bool:
        return any(fnmatch.fnmatch(nombre, patron) for patron in self.reglas[lista])

    def visible(self, nombre: str) -> bool:
        """Una herramienta oculta ni siquiera se le muestra al modelo: se reduce la superficie de ataque."""
        return not self._coincide(nombre, "ocultar")

    def decidir(self, nombre: str, catalogo_visible: set[str] | None = None) -> tuple[str, str]:
        """Devuelve (decisión, razón). La razón queda en la traza: explica cada bloqueo."""
        if not self.visible(nombre):
            return "denegar", "herramienta oculta por la política"
        if catalogo_visible is not None and nombre not in catalogo_visible:
            return "denegar", "herramienta desconocida: no está en el catálogo visible"
        tope = self.topes.get(nombre)
        if tope is not None and self.aceptadas.get(nombre, 0) >= tope:
            return "denegar", f"se alcanzó el máximo de {tope} llamada(s) aceptada(s) a {nombre} en esta ejecución"
        if self._coincide(nombre, "denegar"):
            return "denegar", "herramienta prohibida por la política"
        if self._coincide(nombre, "confirmar"):
            return "confirmar", f"requiere aprobación humana (backend {self.backend})"
        if self._coincide(nombre, "permitir"):
            return "permitir", f"permitida por la política (backend {self.backend})"
        return self.por_defecto, f"regla por defecto: {self.por_defecto}"

    def registrar_aceptada(self, nombre: str) -> None:
        """Llamar solo cuando el servidor aceptó la llamada (es_error = false)."""
        self.aceptadas[nombre] = self.aceptadas.get(nombre, 0) + 1
