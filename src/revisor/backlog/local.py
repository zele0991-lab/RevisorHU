"""
BacklogLocal: el adaptador del puerto que usa el experimento.

Lee las HU de archivos JSON o JSONL (casos de evaluación, backlog de contexto, ejemplos) y
escribe los borradores como archivos JSON en una carpeta de estado.

Por qué archivos y no una base de datos:
    El experimento tiene que poder repetirse en cualquier máquina sin instalar nada.
    Los borradores quedan como evidencia legible; la fuente de las métricas son las trazas.

Por qué solo se exponen los campos de `Historia`:
    Los casos de evaluación traen metadatos para los investigadores (`es_dificil`,
    `motivo_dificultad`). Si llegaran al modelo, le darían pistas sobre la respuesta.
    Al construir `Historia` campo por campo, todo lo demás se descarta.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from revisor.backlog.puerto import (
    ErrorBacklog,
    Historia,
    HistoriaNoEncontrada,
    HistoriaSimilar,
    PuertoBacklog,
    Revision,
)
from revisor.backlog.similitud import IndiceSimilitud

CAMPOS_OBLIGATORIOS = ("id", "texto", "sistema", "proyecto")


def _nombre_seguro(texto: str) -> str:
    """Convierte un id en un nombre de archivo seguro (sin rutas ni caracteres raros)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", texto)


def _leer_registros(ruta: Path) -> list[tuple[str, dict]]:
    """Devuelve pares (ubicación legible, registro) para dar errores que digan dónde está el problema."""
    if not ruta.exists():
        raise ErrorBacklog(f"No existe el archivo de historias: {ruta}")
    contenido = ruta.read_text(encoding="utf-8")
    if ruta.suffix == ".jsonl":
        registros = []
        for n, linea in enumerate(contenido.splitlines(), start=1):
            if linea.strip():
                try:
                    registros.append((f"{ruta.name}:{n}", json.loads(linea)))
                except json.JSONDecodeError as e:
                    raise ErrorBacklog(f"{ruta.name}:{n}: JSON inválido ({e.msg})") from e
        return registros
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as e:
        raise ErrorBacklog(f"{ruta.name}: JSON inválido ({e.msg}, línea {e.lineno})") from e
    lista = datos.get("historias") if isinstance(datos, dict) else datos
    if not isinstance(lista, list):
        raise ErrorBacklog(f"{ruta.name}: se esperaba una lista de historias o {{'historias': [...]}}")
    return [(f"{ruta.name}[{i}]", r) for i, r in enumerate(lista)]


def _a_historia(ubicacion: str, r: object) -> Historia:
    if not isinstance(r, dict):
        raise ErrorBacklog(f"{ubicacion}: cada historia debe ser un objeto JSON")
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not str(r.get(c) or "").strip()]
    if faltan:
        raise ErrorBacklog(f"{ubicacion}: faltan campos obligatorios: {', '.join(faltan)}")
    puntos = r.get("story_points")
    if puntos is not None and not isinstance(puntos, int):
        raise ErrorBacklog(f"{ubicacion}: story_points debe ser un entero o null")
    return Historia(
        id=str(r["id"]).strip(),
        texto=str(r["texto"]),
        sistema=str(r["sistema"]).strip(),
        proyecto=str(r["proyecto"]).strip(),
        titulo=str(r.get("titulo") or ""),
        story_points=puntos,
        criterios_aceptacion=str(r.get("criterios_aceptacion") or ""),
    )


class BacklogLocal(PuertoBacklog):
    """Backlog en archivos. Carga todo al iniciar y falla de inmediato si un archivo es inválido."""

    def __init__(self, rutas: Iterable[Path | str], carpeta_estado: Path | str, marca: str | None = None):
        """
        `marca` distingue los borradores de cada ejecución (por ejemplo, el run_id del
        experimento). Sin marca se usa la fecha y hora.
        """
        self._historias: dict[str, Historia] = {}
        for ruta in rutas:
            for ubicacion, registro in _leer_registros(Path(ruta)):
                h = _a_historia(ubicacion, registro)
                if h.id in self._historias:
                    raise ErrorBacklog(f"{ubicacion}: id duplicado '{h.id}'")
                self._historias[h.id] = h
        if not self._historias:
            raise ErrorBacklog("El backlog está vacío: no se cargó ninguna historia.")
        self._indice = IndiceSimilitud({i: f"{h.titulo} {h.texto}" for i, h in self._historias.items()})
        self._estado = Path(carpeta_estado)
        self._marca = _nombre_seguro(marca or datetime.now().strftime("%Y%m%d_%H%M%S_%f"))

    # ------------------------------------------------------------------ lectura
    @property
    def ids(self) -> list[str]:
        return sorted(self._historias)

    def leer_historia(self, id: str) -> Historia:
        try:
            return self._historias[id]
        except KeyError:
            raise HistoriaNoEncontrada(id) from None

    def buscar_similares(self, texto: str, limite: int) -> list[HistoriaSimilar]:
        return [HistoriaSimilar(self._historias[i], s) for i, s in self._indice.buscar(texto, limite)]

    def listar_pendientes(self, limite: int) -> list[Historia]:
        carpeta = self._estado / "revisiones"
        pendientes = [
            h for i, h in sorted(self._historias.items())
            if not any(carpeta.glob(f"{_nombre_seguro(i)}__*.json"))
        ]
        return pendientes[:limite]

    # ------------------------------------------------------------------ escritura
    def _guardar(self, subcarpeta: str, id: str, datos: dict) -> str:
        carpeta = self._estado / subcarpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{_nombre_seguro(id)}__{self._marca}.json"
        datos = {"registrado_en": datetime.now().isoformat(timespec="seconds"), **datos}
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        return ruta.as_posix()

    def registrar_revision(self, revision: Revision) -> str:
        self.leer_historia(revision.id_historia)
        return self._guardar("revisiones", revision.id_historia, {"estado": "borrador", **asdict(revision)})

    def proponer_division(self, id: str, partes: list[str]) -> str:
        self.leer_historia(id)
        return self._guardar("divisiones", id, {"estado": "borrador", "historia_original": id, "partes": partes})

    def aprobar_para_fabrica(self, id: str) -> str:
        """
        En el backlog local la aprobación sí se escribe. Por qué: así un ataque que lograra
        saltarse la política dejaría evidencia en `estado/aprobaciones/`, y la tasa de éxito
        de los ataques se puede medir. Que nunca ocurra es trabajo de la política (oculta).
        """
        self.leer_historia(id)
        return self._guardar("aprobaciones", id, {"estado": "aprobada_para_fabrica", "historia": id})
