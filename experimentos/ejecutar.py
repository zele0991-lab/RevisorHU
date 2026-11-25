"""
Corre el experimento de la F6: Skill frente a línea base, varias repeticiones por caso.

Uso (desde la raíz del repositorio):
    python experimentos/ejecutar.py --conjunto generico                      # solo muestra el plan y el costo
    python experimentos/ejecutar.py --conjunto generico --casos EV-01,EV-02 --repeticiones 1 --ejecutar
    python experimentos/ejecutar.py --conjunto generico --repeticiones 3 --ejecutar
    python experimentos/ejecutar.py --conjunto banca --simulado --ejecutar   # sin clave ni costo

Por qué no gasta nada sin `--ejecutar`:
    Cada ejecución real cuesta dinero (CLAUDE.md: avisar antes del costo). Sin la bandera, el
    script solo cuenta las ejecuciones pendientes y estima el costo con el perfil de tokens de
    las trazas que ya existen.

Por qué se puede interrumpir y volver a lanzar:
    Antes de cada ejecución se mira la carpeta de trazas del conjunto. Una ejecución (config,
    repetición, caso) que ya terminó no se repite. Solo se repiten las que quedaron
    `contaminadas` (respondió otro modelo) o con `motivo_cierre: error` (por ejemplo, la API
    caída): esas no dicen nada del agente. Que el agente no registre revisión o se quede sin
    pasos SÍ es un resultado y no se repite, para no elegir las ejecuciones que convienen.

Orden de las ejecuciones:
    Repetición por repetición; dentro de cada una, los casos en un orden barajado con semilla fija
    y las dos configuraciones alternando cuál va primero. Así un cambio de la API durante la
    corrida no cae entero sobre una sola configuración.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "experimento.json"
CONFIGURACIONES = ("skill", "base")
SEMILLA = 20261125
ERRORES_SEGUIDOS_MAX = 3

# Perfil de tokens por ejecución mientras no haya trazas del experimento: el promedio de las 19
# ejecuciones reales de F3, F4 y F7 (Opus 5.5, 6 pasos), redondeado hacia arriba.
PERFIL_INICIAL = {"entrada": 20, "salida": 5000, "cache_lectura": 75000, "cache_escritura": 20000}
MARGEN = 1.5  # Haiku puede dar más pasos y su tokenizador puede contar más tokens


@dataclass(frozen=True)
class Ejecucion:
    config: str
    repeticion: int
    caso: str


def cargar_config(ruta: Path = CONFIG) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def ids_de_casos(ruta: Path) -> list[str]:
    return [json.loads(l)["id"] for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def plan(casos: list[str], repeticiones: int, configuraciones=CONFIGURACIONES, semilla: int = SEMILLA) -> list[Ejecucion]:
    """Todas las ejecuciones, en el orden en que se corren (ver docstring del módulo)."""
    orden = []
    for r in range(1, repeticiones + 1):
        barajados = list(casos)
        random.Random(semilla + r).shuffle(barajados)
        for i, caso in enumerate(barajados):
            cfgs = list(configuraciones)
            if i % 2:
                cfgs.reverse()
            orden += [Ejecucion(c, r, caso) for c in cfgs]
    return orden


def leer_resumen(ruta: Path) -> dict | None:
    """Datos de una traza para decidir si se repite y para estimar costos. None si está incompleta."""
    inicio = fin = None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        e = json.loads(linea)
        if e.get("tipo") == "inicio":
            inicio = e
        elif e.get("tipo") == "fin":
            fin = e
    if not inicio or not fin:
        return None
    return {"config": inicio["config"], "repeticion": inicio["repeticion"], "caso": inicio["caso"],
            "modelo": inicio["modelo"], "valida": not fin.get("contaminada") and fin.get("motivo_cierre") != "error",
            "tokens": {"entrada": fin.get("tokens_entrada", 0), "salida": fin.get("tokens_salida", 0),
                       "cache_lectura": fin.get("tokens_cache_lectura", 0),
                       "cache_escritura": fin.get("tokens_cache_escritura", 0)}}


def resumenes(carpeta: Path) -> list[dict]:
    if not carpeta.exists():
        return []
    return [r for r in (leer_resumen(p) for p in sorted(carpeta.glob("*.jsonl"))) if r]


def hechas(carpeta: Path, modelo: str) -> set[Ejecucion]:
    """Ejecuciones con una traza válida del mismo modelo (las simuladas no cuentan para el real)."""
    return {Ejecucion(r["config"], r["repeticion"], r["caso"])
            for r in resumenes(carpeta) if r["valida"] and r["modelo"] == modelo}


def perfil_tokens(carpeta: Path, modelo: str) -> tuple[dict, str]:
    """Promedio de tokens de las trazas reales del conjunto; si no hay, el perfil inicial con margen."""
    reales = [r["tokens"] for r in resumenes(carpeta) if r["modelo"] == modelo]
    if not reales:
        return {k: v * MARGEN for k, v in PERFIL_INICIAL.items()}, \
            f"perfil de las ejecuciones con Opus de F3-F7 x{MARGEN} (aún no hay trazas de {modelo})"
    n = len(reales)
    return {k: sum(t[k] for t in reales) / n for k in PERFIL_INICIAL}, f"promedio de {n} trazas reales de {modelo}"


def costo(tokens: dict, precios: dict) -> float:
    return sum(tokens[k] * precios[k] for k in PERFIL_INICIAL) / 1_000_000


def cambios_sin_confirmar(raiz: Path = RAIZ) -> list[str]:
    """Archivos modificados, sin contar las trazas del experimento (se van agregando mientras corre)."""
    try:
        salida = subprocess.run(["git", "status", "--porcelain"], cwd=raiz, capture_output=True,
                                text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ["(no se pudo consultar git)"]
    lineas = [l[3:] for l in salida.splitlines() if l.strip()]
    return [l for l in lineas if not l.strip('"').startswith("trazas/experimento/")]


def denegar_siempre(nombre: str, argumentos: dict) -> tuple[bool, str]:
    """En el experimento no hay persona que confirme: una escritura que pida confirmación se deniega."""
    return False, "denegada: el experimento corre sin una persona que confirme"


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description="Experimento F6: Skill frente a línea base")
    ap.add_argument("--conjunto", choices=("generico", "banca", "ataques"), default="generico")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--casos", default=None, help="ids separados por coma (piloto); por defecto, todos")
    ap.add_argument("--config", choices=("ambas",) + CONFIGURACIONES, default="ambas")
    ap.add_argument("--simulado", action="store_true", help="modelo simulado: sin clave ni costo")
    ap.add_argument("--ejecutar", action="store_true", help="sin esta bandera solo muestra el plan y el costo")
    ap.add_argument("--permitir-cambios", action="store_true",
                    help="correr aunque haya cambios sin commit (la ejecución no sería reproducible)")
    ap.add_argument("--archivo-config", type=Path, default=CONFIG)
    args = ap.parse_args(argv)

    cfg = cargar_config(args.archivo_config)
    conjunto = cfg["conjuntos"][args.conjunto]
    todos = ids_de_casos(RAIZ / conjunto["casos"])
    if args.casos:
        pedidos = [c.strip() for c in args.casos.split(",") if c.strip()]
        desconocidos = [c for c in pedidos if c not in todos]
        if desconocidos:
            print(f"Casos que no están en {conjunto['casos']}: {', '.join(desconocidos)}", file=sys.stderr)
            return 2
        casos = pedidos
    else:
        casos = todos
    configuraciones = CONFIGURACIONES if args.config == "ambas" else (args.config,)

    # Las simuladas van a trazas/desarrollo/ (no se versiona): no son evidencia del experimento.
    carpeta = RAIZ / ("trazas/desarrollo/experimento/" + args.conjunto if args.simulado else conjunto["carpeta_trazas"])
    modelo = "simulado" if args.simulado else cfg["modelo"]
    ya = hechas(carpeta, modelo)
    pendientes = [e for e in plan(casos, args.repeticiones, configuraciones) if e not in ya]

    perfil, origen = perfil_tokens(carpeta, modelo)
    por_ejecucion = 0.0 if args.simulado else costo(perfil, cfg["precios_usd_por_millon"])
    print(f"Conjunto {args.conjunto} · {len(casos)} casos × {len(configuraciones)} config × {args.repeticiones} rep "
          f"= {len(casos) * len(configuraciones) * args.repeticiones} ejecuciones; ya hechas {len(ya)}; "
          f"pendientes {len(pendientes)}")
    print(f"Modelo {modelo} · trazas en {carpeta.relative_to(RAIZ).as_posix()}")
    if not args.simulado:
        print(f"Costo estimado: US${por_ejecucion:.4f} por ejecución, US${por_ejecucion * len(pendientes):.2f} "
              f"en total ({origen}). La factura real manda.")
    if not args.ejecutar:
        print("\nNo se ejecutó nada. Para correrlo, agrega --ejecutar.")
        return 0
    if not pendientes:
        print("Nada pendiente.")
        return 0

    cambios = cambios_sin_confirmar()
    if cambios and not args.simulado and not args.permitir_cambios:
        print("Hay cambios sin commit; la ejecución no sería reproducible:\n  " + "\n  ".join(cambios[:10]),
              file=sys.stderr)
        return 2

    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")  # la clave nunca se imprime ni se escribe en la traza
    if not args.simulado and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("Falta ANTHROPIC_API_KEY en .env. Sin clave, usa --simulado.", file=sys.stderr)
        return 2

    from revisor.agente.bucle import Opciones, ejecutar

    ajustes = {"historias": conjunto["historias"], "carpeta_trazas": str(carpeta), "conjunto": args.conjunto}
    gastado, errores_seguidos, fallidas = 0.0, 0, 0
    for n, e in enumerate(pendientes, start=1):
        for intento in (1, 2):  # una ejecución contaminada o con error se repite una vez
            op = Opciones(caso=e.caso, config=e.config, repeticion=e.repeticion, simulado=args.simulado,
                          archivo_config=args.archivo_config, raiz=RAIZ, ajustes=ajustes,
                          aprobador=denegar_siempre, salida=lambda _: None)
            r = asyncio.run(ejecutar(op))
            valida = not r.contaminada and r.motivo_cierre != "error"
            if not args.simulado:
                gastado += costo(r.tokens, cfg["precios_usd_por_millon"])
            if valida:
                break
        print(f"[{n}/{len(pendientes)}] {e.config:5} r{e.repeticion} {e.caso:8} -> "
              f"{r.decision or 'sin decisión'} · {r.motivo_cierre} · {r.pasos} pasos · {r.tokens['totales']} tokens"
              + ("" if valida else f" · NO VÁLIDA ({r.error or 'contaminada'})")
              + ("" if args.simulado else f" · acumulado US${gastado:.3f}"))
        if valida:
            errores_seguidos = 0
        else:
            fallidas += 1
            errores_seguidos += 1
            if errores_seguidos >= ERRORES_SEGUIDOS_MAX:
                print(f"\n{ERRORES_SEGUIDOS_MAX} ejecuciones seguidas no válidas: se detiene. Revisa la última "
                      "traza (¿crédito, clave, red?) y vuelve a lanzar: retoma donde quedó.", file=sys.stderr)
                return 1

    print(f"\nListo. {len(pendientes) - fallidas} válidas, {fallidas} no válidas"
          + ("" if args.simulado else f", US${gastado:.3f} estimados") + ".")
    print(f"Métricas: python experimentos/metricas.py --conjunto {args.conjunto}"
          + (" --simulado" if args.simulado else ""))
    return 0 if fallidas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
