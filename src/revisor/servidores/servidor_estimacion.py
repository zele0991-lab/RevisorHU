"""
servidor_estimacion: referencias para estimar en story points. Solo lectura.

Herramientas:
    historias_referencia  historias con story points reales parecidas al texto
    escala_estimacion     escala permitida y regla para dividir

Las referencias salen de TAWOS (Tawosi et al., 2022), con story points reales. El archivo de
referencias NO debe contener las 30 HU de TAWOS reservadas para medir la estimación
(D-012): si las contuviera, el agente vería la respuesta.

Uso (stdio, desde la raíz del repositorio):
    python -m revisor.servidores.servidor_estimacion --referencias datos/ejemplo/referencias_ejemplo.jsonl
"""

# Sin `from __future__ import annotations` (ver servidor_backlog): MCPServer evalúa las anotaciones.
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import Field

from mcp.server.mcpserver import MCPServer

from revisor import dominio
from revisor.backlog.similitud import IndiceSimilitud
from revisor.servidores.comun import (
    AVISO_NO_CONFIABLE,
    endurecer_esquemas,
    envolver_no_confiable,
    errores_busqueda,
    rechazo,
)

LIMITE_REFERENCIAS = (1, 10)
UMBRAL_DIVISION = 8


class ReferenciasInvalidas(Exception):
    """El archivo de referencias no se puede usar; el servidor no arranca."""


@dataclass(frozen=True)
class Referencia:
    id: str
    texto: str
    story_points: int
    proyecto: str
    fuente: str


def a_escala(puntos: int) -> int:
    """
    Valor de la escala más cercano a un story point real. Con empate, el mayor.

    Por qué: en TAWOS hay puntos fuera de Fibonacci (4, 20, 40…). El agente estima en la
    escala del proyecto, así que la referencia trae los dos valores.
    """
    return min(dominio.ESCALA_FIBONACCI, key=lambda e: (abs(e - puntos), -e))


def cargar_referencias(ruta: Path | str) -> list[Referencia]:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ReferenciasInvalidas(f"No existe el archivo de referencias: {ruta}")
    referencias, ids = [], set()
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if not linea.strip():
            continue
        donde = f"{ruta.name}:{n}"
        try:
            r = json.loads(linea)
        except json.JSONDecodeError as e:
            raise ReferenciasInvalidas(f"{donde}: JSON inválido ({e.msg})") from e
        faltan = [c for c in ("id", "texto", "story_points") if c not in r]
        if faltan:
            raise ReferenciasInvalidas(f"{donde}: faltan campos: {', '.join(faltan)}")
        sp = r["story_points"]
        if not isinstance(sp, int) or isinstance(sp, bool) or sp <= 0:
            raise ReferenciasInvalidas(f"{donde}: story_points debe ser un entero positivo (vino {sp!r})")
        if r["id"] in ids:
            raise ReferenciasInvalidas(f"{donde}: id duplicado '{r['id']}'")
        ids.add(r["id"])
        referencias.append(Referencia(str(r["id"]), str(r["texto"]), sp,
                                      str(r.get("proyecto", "")), str(r.get("fuente", ""))))
    if not referencias:
        raise ReferenciasInvalidas(f"{ruta.name}: no hay referencias.")
    return referencias


def _json(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


def crear_servidor(referencias: list[Referencia]) -> MCPServer:
    servidor = MCPServer(
        "servidor_estimacion",
        instructions="Historias de referencia con story points reales y la escala de estimación. Solo lectura.",
    )
    por_id = {r.id: r for r in referencias}
    indice = IndiceSimilitud({r.id: r.texto for r in referencias})

    @servidor.tool(
        structured_output=False,
        description=(
            "Devuelve historias de otros proyectos con story points REALES, parecidas al texto dado. Úsala "
            "para estimar la HU por analogía, después de entender su alcance. Cada resultado trae los puntos "
            "reales y su equivalente en la escala del proyecto. 'limite' entre 1 y 10."
        ),
    )
    def historias_referencia(
        texto: Annotated[str, Field(description="Texto de la HU a estimar (o su parte principal).")],
        limite: Annotated[int, Field(description="Cuántas referencias devolver, entre 1 y 10.")],
    ) -> str:
        errores = errores_busqueda(texto, limite, LIMITE_REFERENCIAS)
        if errores:
            raise rechazo("historias_referencia", errores)
        resultados = indice.buscar(texto, limite)
        return _json({
            "resultados": [
                {
                    "id": por_id[i].id,
                    "proyecto": por_id[i].proyecto,
                    "similitud": s,
                    "story_points_reales": por_id[i].story_points,
                    "equivalente_escala": a_escala(por_id[i].story_points),
                    "texto": envolver_no_confiable(por_id[i].texto),
                }
                for i, s in resultados
            ],
            "nota": "Sin referencias parecidas: estima con escala_estimacion y el alcance de la HU."
                    if not resultados else AVISO_NO_CONFIABLE,
        })

    @servidor.tool(
        structured_output=False,
        description=(
            "Devuelve la escala de estimación permitida (Fibonacci) y la regla para dividir. Úsala antes de "
            "fijar la estimación de registrar_revision, o si dudas de si la HU es demasiado grande."
        ),
    )
    def escala_estimacion() -> str:
        return _json({
            "escala": list(dominio.ESCALA_FIBONACCI),
            "umbral_division": UMBRAL_DIVISION,
            "regla_division": (
                f"Una HU de más de {UMBRAL_DIVISION} puntos, o con más de un objetivo, es demasiado grande. "
                f"Se divide (decisión 'dividir', con las partes en proponer_division) solo si el tamaño es su "
                f"único problema; si además tiene otros defectos, la decisión es 'devolver'."
            ),
        })

    endurecer_esquemas(servidor)
    return servidor


def construir(argv: list[str] | None = None) -> MCPServer:
    ap = argparse.ArgumentParser(description="Servidor MCP de estimación (stdio)")
    ap.add_argument("--referencias", required=True, help="archivo .jsonl con historias de referencia")
    args = ap.parse_args(argv)
    return crear_servidor(cargar_referencias(args.referencias))


def main(argv: list[str] | None = None) -> int:
    try:
        servidor = construir(argv)
    except ReferenciasInvalidas as e:
        print(f"servidor_estimacion no arranca: {e}", file=sys.stderr)
        return 2
    servidor.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
