"""
Guías para personas (`conocimiento/*.md`), partidas en secciones para `buscar_guia`.

Por qué las guías no definen criterios:
    Los criterios viven solo en `criterios.yaml`. Las guías explican el porqué (QUS, INVEST,
    banca móvil, la DoR en borrador) y sirven de contexto, pero no son reglas. Así no hay
    dos fuentes de verdad que puedan contradecirse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from revisor.backlog.similitud import IndiceSimilitud

MAX_TEXTO_SECCION = 1500
_ENCABEZADO = re.compile(r"^#{1,3}\s+(.+?)\s*$")


@dataclass(frozen=True)
class Seccion:
    fuente: str
    titulo: str
    texto: str

    @property
    def clave(self) -> str:
        return f"{self.fuente}#{self.titulo}"


def partir_en_secciones(fuente: str, contenido: str) -> list[Seccion]:
    """Una sección por encabezado (#, ## o ###); el texto previo al primero va con el nombre del archivo."""
    secciones, titulo, lineas = [], fuente, []
    for linea in contenido.splitlines():
        m = _ENCABEZADO.match(linea)
        if m:
            if "".join(lineas).strip():
                secciones.append(Seccion(fuente, titulo, "\n".join(lineas).strip()))
            titulo, lineas = m.group(1), []
        else:
            lineas.append(linea)
    if "".join(lineas).strip():
        secciones.append(Seccion(fuente, titulo, "\n".join(lineas).strip()))
    return secciones


class IndiceGuias:
    """Índice TF-IDF de las secciones de todos los `.md` de una carpeta."""

    def __init__(self, carpeta: Path | str):
        carpeta = Path(carpeta)
        archivos = sorted(carpeta.glob("*.md"))
        if not archivos:
            raise FileNotFoundError(f"No hay guías .md en {carpeta}.")
        self.secciones: dict[str, Seccion] = {}
        for archivo in archivos:
            for s in partir_en_secciones(archivo.name, archivo.read_text(encoding="utf-8")):
                self.secciones[s.clave] = s
        self._indice = IndiceSimilitud({k: f"{s.titulo} {s.texto}" for k, s in self.secciones.items()})

    def buscar(self, texto: str, limite: int) -> list[tuple[Seccion, float]]:
        return [(self.secciones[k], s) for k, s in self._indice.buscar(texto, limite)]
